#!/usr/bin/env python3
"""Fix WAN config in Controller to static IP, then provision."""
import paramiko
import json
import time
import socket

nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.129", username="admin", password="examplepass", timeout=5)
print("Connected to NAS")

# Login
_, out, _ = nas.exec_command(
    'docker exec unifi curl -sk -X POST https://localhost:8443/api/login '
    '-H "Content-Type: application/json" '
    "-d '{\"username\":\"mllab\",\"password\":\"examplepass\"}' "
    "-c /tmp/uc 2>&1",
    timeout=15,
)
print(f"Login: {out.read().decode().strip()[:50]}")

# Get WAN network config ID
_, out, _ = nas.exec_command(
    "docker exec unifi curl -sk -b /tmp/uc "
    "'https://localhost:8443/api/s/default/rest/networkconf' 2>&1",
    timeout=15,
)
nets = json.loads(out.read().decode().strip()).get("data", [])
wan_id = None
for n in nets:
    if n.get("purpose") == "wan" and "WAN1" in n.get("name", ""):
        wan_id = n["_id"]
        print(f"WAN network: id={wan_id} name={n.get('name')} wan_type={n.get('wan_type')}")
        break

if wan_id:
    # Update WAN to static IP
    wan_update = json.dumps({
        "wan_type": "static",
        "wan_ip": "203.0.113.10",
        "wan_netmask": "255.255.255.0",
        "wan_gateway": "203.0.113.1",
        "wan_dns1": "1.1.1.1",
        "wan_dns2": "8.8.8.8",
    })

    sftp = nas.open_sftp()
    with sftp.open("/tmp/wan_update.json", "w") as f:
        f.write(wan_update)
    sftp.close()
    time.sleep(1)

    _, out, _ = nas.exec_command(
        f"docker exec unifi curl -sk -b /tmp/uc -X PUT "
        f"'https://localhost:8443/api/s/default/rest/networkconf/{wan_id}' "
        f'-H "Content-Type: application/json" '
        f'-d "$(cat /tmp/wan_update.json)" 2>&1',
        timeout=15,
    )
    result = out.read().decode().strip()
    if '"ok"' in result:
        print("WAN config updated to static!")
    else:
        print(f"Update result: {result[:200]}")

    # Force provision
    print("\nForce provisioning USG...")
    prov = json.dumps({"cmd": "force-provision", "mac": "00:00:5e:00:53:01"})
    with sftp.open("/tmp/prov.json", "w") as f:
        f.write(prov)
    sftp.close()
    time.sleep(1)

    _, out, _ = nas.exec_command(
        "docker exec unifi curl -sk -b /tmp/uc -X POST "
        "'https://localhost:8443/api/s/default/cmd/devmgr' "
        '-H "Content-Type: application/json" '
        '-d "$(cat /tmp/prov.json)" 2>&1',
        timeout=15,
    )
    print(f"Provision: {out.read().decode().strip()[:150]}")

    print("\nWaiting 60s for USG to apply WAN config...")
    time.sleep(60)

    # Check
    print("\nChecking WAN...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    r = s.connect_ex(("203.0.113.10", 22))
    print(f"WAN .34:22: {'OPEN' if r == 0 else 'CLOSED'}")
    s.close()

    for port, name in [(12200, "srv20"), (12230, "Pro6000")]:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(4)
        r = s.connect_ex(("203.0.113.10", port))
        print(f":{port} {name}: {'OPEN' if r == 0 else 'CLOSED'}")
        s.close()

nas.close()
print("\n=== DONE ===")
