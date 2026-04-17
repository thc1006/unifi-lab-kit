#!/usr/bin/env python3
"""
Fix ALL port forward rules in Controller, then provision USG.
Strategy: Delete all old rules, create clean new ones with correct IPs.
"""
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


def api_get(path):
    _, out, _ = nas.exec_command(
        f"docker exec unifi curl -sk -b /tmp/uc "
        f"'https://localhost:8443/api/s/default/{path}' 2>&1",
        timeout=15,
    )
    return json.loads(out.read().decode().strip())


def api_delete(path):
    _, out, _ = nas.exec_command(
        f"docker exec unifi curl -sk -b /tmp/uc -X DELETE "
        f"'https://localhost:8443/api/s/default/{path}' 2>&1",
        timeout=15,
    )
    return out.read().decode().strip()


def api_post(path, data):
    payload = json.dumps(data)
    sftp = nas.open_sftp()
    with sftp.open("/tmp/pf_payload.json", "w") as f:
        f.write(payload)
    sftp.close()
    time.sleep(0.5)
    _, out, _ = nas.exec_command(
        f"docker exec unifi curl -sk -b /tmp/uc -X POST "
        f"'https://localhost:8443/api/s/default/{path}' "
        f'-H "Content-Type: application/json" '
        f'-d "$(cat /tmp/pf_payload.json)" 2>&1',
        timeout=15,
    )
    return out.read().decode().strip()


# ============================================================
# Step 1: Delete ALL old port forward rules
# ============================================================
print("\n=== Step 1: Delete old port forward rules ===")
result = api_get("rest/portforward")
old_rules = result.get("data", [])
print(f"Found {len(old_rules)} old rules. Deleting...")

for r in old_rules:
    rid = r["_id"]
    name = r.get("name", "?")
    api_delete(f"rest/portforward/{rid}")
    # print(f"  Deleted: {name}")

print(f"  Deleted {len(old_rules)} rules")

# Verify
result = api_get("rest/portforward")
remaining = len(result.get("data", []))
print(f"  Remaining: {remaining}")

# ============================================================
# Step 2: Create new clean port forward rules
# ============================================================
print("\n=== Step 2: Create new port forward rules ===")

# Server SSH rules (correct IPs)
new_rules = [
    # Server SSH (port 120X0 → .10X:22)
    ("srv6-ssh", "12060", "192.168.1.106", "22", "tcp"),
    ("srv8-ssh", "12080", "192.168.1.108", "22", "tcp"),
    ("srv9-ssh", "12090", "192.168.1.109", "22", "tcp"),
    ("srv11-ssh", "12110", "192.168.1.111", "22", "tcp"),
    ("srv13-ssh", "12130", "192.168.1.113", "22", "tcp"),
    ("srv15-ssh", "12150", "192.168.1.115", "22", "tcp"),
    ("srv20-ssh", "12200", "192.168.1.120", "22", "tcp"),
    ("srv21-ssh", "12210", "192.168.1.121", "22", "tcp"),
    ("srv22-ssh", "12220", "192.168.1.122", "22", "tcp"),
    ("pro6k-ssh", "12230", "192.168.1.123", "22", "tcp"),
    ("nas-ssh", "12990", "192.168.1.129", "22", "tcp"),
]

for name, dst_port, fwd_ip, fwd_port, proto in new_rules:
    payload = {
        "name": name,
        "enabled": True,
        "dst_port": dst_port,
        "fwd": fwd_ip,
        "fwd_port": fwd_port,
        "proto": proto,
        "src": "any",
        "log": False,
    }
    result = api_post("rest/portforward", payload)
    ok = '"ok"' in result
    print(f"  {name}: :{dst_port} -> {fwd_ip}:{fwd_port}  {'OK' if ok else 'FAIL'}")

# ============================================================
# Step 3: Also fix WAN config to static
# ============================================================
print("\n=== Step 3: Verify WAN config ===")
nets = api_get("rest/networkconf").get("data", [])
for n in nets:
    if n.get("purpose") == "wan" and "WAN1" in n.get("name", ""):
        wan_type = n.get("wan_type")
        print(f"WAN type: {wan_type}")
        if wan_type != "static":
            print("  Updating to static...")
            wan_update = json.dumps({
                "wan_type": "static",
                "wan_ip": "203.0.113.10",
                "wan_netmask": "255.255.255.0",
                "wan_gateway": "203.0.113.1",
                "wan_dns1": "1.1.1.1",
                "wan_dns2": "8.8.8.8",
            })
            sftp = nas.open_sftp()
            with sftp.open("/tmp/wan_fix.json", "w") as f:
                f.write(wan_update)
            sftp.close()
            time.sleep(0.5)
            _, out, _ = nas.exec_command(
                f"docker exec unifi curl -sk -b /tmp/uc -X PUT "
                f"'https://localhost:8443/api/s/default/rest/networkconf/{n['_id']}' "
                f'-H "Content-Type: application/json" '
                f'-d "$(cat /tmp/wan_fix.json)" 2>&1',
                timeout=15,
            )
            print(f"  {out.read().decode().strip()[:80]}")
        else:
            print("  Already static, OK")
        break

# ============================================================
# Step 4: Verify all rules
# ============================================================
print("\n=== Step 4: Verify rules ===")
result = api_get("rest/portforward")
rules = result.get("data", [])
print(f"Total rules: {len(rules)}")
for r in rules:
    print(f"  {r.get('name','?')}: :{r.get('dst_port','?')} -> {r.get('fwd','?')}:{r.get('fwd_port','?')}")

# ============================================================
# Step 5: Force provision USG
# ============================================================
print("\n=== Step 5: Force provision USG ===")

# First, make sure USG WAN is up (set it manually if needed)
usg = paramiko.SSHClient()
usg.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    usg.connect("192.168.1.1", username="ops", password="exampleusgpass", timeout=5)
    _, out, _ = usg.exec_command("ip addr show eth0 | grep 'inet '", timeout=5)
    wan_ip = out.read().decode().strip()
    print(f"USG WAN: {wan_ip}")

    if "203.0.113.10" not in wan_ip:
        print("  WAN IP missing, setting manually...")
        shell = usg.invoke_shell()
        time.sleep(1)
        shell.recv(4096)
        for c in [
            "configure",
            "delete interfaces ethernet eth0 address dhcp",
            "delete interfaces ethernet eth0 dhcp-options",
            "set interfaces ethernet eth0 address 203.0.113.10/24",
            "set protocols static route 0.0.0.0/0 next-hop 203.0.113.1",
            "commit",
            "save",
            "exit",
        ]:
            shell.send(c + "\n")
            time.sleep(2)
            if shell.recv_ready():
                shell.recv(4096)
        shell.close()
        print("  WAN IP set manually")

    # Send set-inform to reconnect to controller
    _, out, _ = usg.exec_command(
        "mca-cli-op set-inform http://192.168.1.129:8080/inform", timeout=10
    )
    usg.close()
except Exception as e:
    print(f"  USG SSH: {e}")

# Wait for controller connection
print("\nWaiting 30s for Controller to connect and provision...")
time.sleep(30)

# Check USG state
devices = api_get("stat/device").get("data", [])
for d in devices:
    if d.get("type") == "ugw":
        state = d.get("state")
        state_map = {0: "DISCONNECTED", 1: "CONNECTED", 2: "PENDING", 5: "PROVISIONING"}
        print(f"USG state: {state_map.get(state, state)}")

        if state == 1:
            print("USG CONNECTED! Provisioning now...")
            prov = json.dumps({"cmd": "force-provision", "mac": "00:00:5e:00:53:01"})
            sftp = nas.open_sftp()
            with sftp.open("/tmp/prov_final.json", "w") as f:
                f.write(prov)
            sftp.close()
            time.sleep(0.5)
            _, out, _ = nas.exec_command(
                "docker exec unifi curl -sk -b /tmp/uc -X POST "
                "'https://localhost:8443/api/s/default/cmd/devmgr' "
                '-H "Content-Type: application/json" '
                '-d "$(cat /tmp/prov_final.json)" 2>&1',
                timeout=15,
            )
            print(f"  Provision: {out.read().decode().strip()[:100]}")

            print("  Waiting 60s for provision to complete...")
            time.sleep(60)

nas.close()

# ============================================================
# Step 6: Test all port forwards
# ============================================================
print("\n=== Step 6: Test port forwards ===")
WAN = "203.0.113.10"
tests = [
    (22, "USG-SSH"),
    (12060, "server6"), (12080, "server8"), (12090, "server9"),
    (12110, "server11"), (12130, "server13"), (12150, "server15"),
    (12200, "server20"), (12210, "server21"), (12220, "server22"),
    (12230, "Pro6000"), (12990, "NAS"),
]

all_ok = True
for port, name in tests:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(4)
    r = s.connect_ex((WAN, port))
    if r == 0:
        try:
            banner = s.recv(256).decode().strip()[:40]
        except:
            banner = "?"
        print(f"  :{port:<5} {name:12s} OK  {banner}")
    else:
        print(f"  :{port:<5} {name:12s} CLOSED")
        if name != "USG-SSH":
            all_ok = False
    s.close()

if all_ok:
    print("\n*** ALL PORT FORWARDS WORKING! ***")
else:
    print("\n*** Some ports still closed ***")

print("\n=== DONE ===")
