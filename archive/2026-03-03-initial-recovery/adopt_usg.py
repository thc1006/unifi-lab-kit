#!/usr/bin/env python3
"""Adopt USG into Controller."""
import paramiko
import json
import time

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

# Check devices
_, out, _ = nas.exec_command(
    "docker exec unifi curl -sk -b /tmp/uc "
    "'https://localhost:8443/api/s/default/stat/device' 2>&1",
    timeout=15,
)
result = out.read().decode().strip()
devices = json.loads(result).get("data", [])
print(f"Devices: {len(devices)}")

for d in devices:
    name = d.get("name", "?")
    dtype = d.get("type", "?")
    state = d.get("state", "?")
    ip = d.get("ip", "?")
    adopted = d.get("adopted", False)
    state_map = {0: "DISCONNECTED", 1: "CONNECTED", 2: "PENDING", 4: "UPGRADING", 5: "PROVISIONING"}
    print(f"  {name}: type={dtype} state={state_map.get(state, state)} ip={ip} adopted={adopted}")

# If USG not found, try adopt by MAC
usg_found = any(d.get("type") == "ugw" for d in devices)
if not usg_found:
    print("\nUSG not in device list. Trying adopt by MAC...")
    adopt_payload = json.dumps({"cmd": "adopt", "mac": "00:00:5e:00:53:01"})

    sftp = nas.open_sftp()
    with sftp.open("/tmp/adopt_usg.json", "w") as f:
        f.write(adopt_payload)
    sftp.close()

    _, out, _ = nas.exec_command(
        "docker exec unifi curl -sk -b /tmp/uc -X POST "
        "'https://localhost:8443/api/s/default/cmd/devmgr' "
        '-H "Content-Type: application/json" '
        '-d "$(cat /tmp/adopt_usg.json)" 2>&1',
        timeout=15,
    )
    print(f"  {out.read().decode().strip()[:200]}")

# Also try: tell USG again to inform
print("\nSending set-inform to USG again...")
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(3)
if s.connect_ex(("192.168.1.1", 22)) == 0:
    usg = paramiko.SSHClient()
    usg.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        usg.connect("192.168.1.1", username="ubnt", password="ubnt", timeout=8)
        _, out2, _ = usg.exec_command(
            "mca-cli-op set-inform http://192.168.1.129:8080/inform", timeout=10
        )
        print(f"  set-inform: {out2.read().decode().strip()}")
        usg.close()
    except Exception as e:
        print(f"  SSH: {e}")
s.close()

# Wait and check again
print("\nWaiting 30s for adoption...")
time.sleep(30)

_, out, _ = nas.exec_command(
    "docker exec unifi curl -sk -b /tmp/uc "
    "'https://localhost:8443/api/s/default/stat/device' 2>&1",
    timeout=15,
)
devices2 = json.loads(out.read().decode().strip()).get("data", [])
print(f"\nDevices after wait: {len(devices2)}")
for d in devices2:
    name = d.get("name", "?")
    dtype = d.get("type", "?")
    state = d.get("state", "?")
    state_map = {0: "DISCONNECTED", 1: "CONNECTED", 2: "PENDING", 4: "UPGRADING", 5: "PROVISIONING"}
    print(f"  {name}: type={dtype} state={state_map.get(state, state)} adopted={d.get('adopted')}")

nas.close()
print("\n=== DONE ===")
