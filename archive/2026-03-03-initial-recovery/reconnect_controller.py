#!/usr/bin/env python3
"""
Reconnect USG to Controller properly.
1. Add correct port forward rules to Controller FIRST
2. Ensure WAN config is static
3. Then set-inform on USG to re-adopt
"""
import paramiko
import json
import time

# ============================================================
# Step 1: Prepare Controller with correct rules
# ============================================================
print("=" * 60)
print("Step 1: Add correct rules to Controller")
print("=" * 60)

nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.129", username="admin", password="examplepass", timeout=5)

# Login
_, out, _ = nas.exec_command(
    'docker exec unifi curl -sk -X POST https://localhost:8443/api/login '
    '-H "Content-Type: application/json" '
    "-d '{\"username\":\"mllab\",\"password\":\"examplepass\"}' "
    "-c /tmp/uc 2>&1",
    timeout=15,
)
print(f"Login: {out.read().decode().strip()[:50]}")

# Add port forward rules
rules = [
    ("srv6-ssh", "12060", "192.168.1.106", "22"),
    ("srv8-ssh", "12080", "192.168.1.108", "22"),
    ("srv9-ssh", "12090", "192.168.1.109", "22"),
    ("srv11-ssh", "12110", "192.168.1.111", "22"),
    ("srv13-ssh", "12130", "192.168.1.113", "22"),
    ("srv15-ssh", "12150", "192.168.1.115", "22"),
    ("srv20-ssh", "12200", "192.168.1.120", "22"),
    ("srv21-ssh", "12210", "192.168.1.121", "22"),
    ("srv22-ssh", "12220", "192.168.1.122", "22"),
    ("pro6k-ssh", "12230", "192.168.1.123", "22"),
    ("nas-ssh", "12990", "192.168.1.129", "22"),
]

# Check existing rules first
_, out, _ = nas.exec_command(
    "docker exec unifi curl -sk -b /tmp/uc "
    "'https://localhost:8443/api/s/default/rest/portforward' 2>&1",
    timeout=15,
)
existing = json.loads(out.read().decode().strip()).get("data", [])
print(f"Existing rules: {len(existing)}")

if len(existing) == 0:
    print("Adding 11 rules...")
    for name, dst_port, fwd_ip, fwd_port in rules:
        payload = json.dumps({
            "name": name, "enabled": True,
            "dst_port": dst_port, "fwd": fwd_ip,
            "fwd_port": fwd_port, "proto": "tcp",
            "src": "any", "log": False,
        })
        sftp = nas.open_sftp()
        with sftp.open("/tmp/pf.json", "w") as f:
            f.write(payload)
        sftp.close()
        time.sleep(0.5)
        _, out, _ = nas.exec_command(
            "docker exec unifi curl -sk -b /tmp/uc -X POST "
            "'https://localhost:8443/api/s/default/rest/portforward' "
            '-H "Content-Type: application/json" '
            '-d "$(cat /tmp/pf.json)" 2>&1',
            timeout=15,
        )
        ok = '"ok"' in out.read().decode().strip()
        print(f"  {name}: {'OK' if ok else 'FAIL'}")
else:
    print("Rules already exist, skipping")

# Verify WAN config
_, out, _ = nas.exec_command(
    "docker exec unifi curl -sk -b /tmp/uc "
    "'https://localhost:8443/api/s/default/rest/networkconf' 2>&1",
    timeout=15,
)
for n in json.loads(out.read().decode().strip()).get("data", []):
    if n.get("purpose") == "wan" and "WAN1" in n.get("name", ""):
        print(f"\nWAN: type={n.get('wan_type')} ip={n.get('wan_ip')}")

# ============================================================
# Step 2: Set-inform on USG
# ============================================================
print("\n" + "=" * 60)
print("Step 2: Set-inform on USG")
print("=" * 60)

usg = paramiko.SSHClient()
usg.set_missing_host_key_policy(paramiko.AutoAddPolicy())
usg.connect("192.168.1.1", username="ops", password="exampleusgpass", timeout=8)

shell = usg.invoke_shell(width=200, height=50)
time.sleep(2)
shell.recv(4096)
shell.send("mca-cli-op set-inform http://192.168.1.129:8080/inform\n")
time.sleep(10)
out = ""
while shell.recv_ready():
    out += shell.recv(4096).decode(errors="replace")
print(f"set-inform: {out.strip()[-100:]}")

# Send twice (UniFi sometimes needs 2)
time.sleep(3)
shell.send("mca-cli-op set-inform http://192.168.1.129:8080/inform\n")
time.sleep(10)

shell.close()
usg.close()

# ============================================================
# Step 3: Wait and check
# ============================================================
print("\n" + "=" * 60)
print("Step 3: Wait for adoption")
print("=" * 60)
print("Waiting 30s...")
time.sleep(30)

# Re-login (cookie may have expired)
nas2 = paramiko.SSHClient()
nas2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas2.connect("192.168.1.129", username="admin", password="examplepass", timeout=5)

nas2.exec_command(
    'docker exec unifi curl -sk -X POST https://localhost:8443/api/login '
    '-H "Content-Type: application/json" '
    "-d '{\"username\":\"mllab\",\"password\":\"examplepass\"}' "
    "-c /tmp/uc 2>&1",
    timeout=15,
)

_, out, _ = nas2.exec_command(
    "docker exec unifi curl -sk -b /tmp/uc "
    "'https://localhost:8443/api/s/default/stat/device' 2>&1",
    timeout=15,
)
devices = json.loads(out.read().decode().strip()).get("data", [])
state_map = {0: "DISCONNECTED", 1: "CONNECTED", 2: "PENDING", 5: "PROVISIONING", 10: "ADOPTING"}

if devices:
    for d in devices:
        state = d.get("state")
        print(f"  {d.get('name','?')}: state={state_map.get(state, state)} adopted={d.get('adopted')} ip={d.get('ip')}")
else:
    print("  No devices yet. Check Controller UI for Pending Adoption.")

# Check rules still intact
_, out, _ = nas2.exec_command(
    "docker exec unifi curl -sk -b /tmp/uc "
    "'https://localhost:8443/api/s/default/rest/portforward' 2>&1",
    timeout=15,
)
rule_count = len(json.loads(out.read().decode().strip()).get("data", []))
print(f"\n  Port forward rules in Controller: {rule_count}")

nas2.close()
print("\n=== DONE ===")
print("If USG shows 'Pending Adoption', click Adopt in Controller UI.")
print("https://192.168.1.129:8443/manage/default/devices")
