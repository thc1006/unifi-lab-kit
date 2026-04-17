#!/usr/bin/env python3
"""Full Controller fix via API - same as doing it in the web UI."""
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
login = out.read().decode().strip()
print(f"Login: {login[:80]}")

# ============================================================
# Step 1: Set Controller hostname/IP to 192.168.1.129
# ============================================================
print("\n=== Step 1: Set inform host ===")

# Get current settings
_, out, _ = nas.exec_command(
    "docker exec unifi curl -sk -b /tmp/uc "
    "'https://localhost:8443/api/s/default/get/setting/super_identity' 2>&1",
    timeout=15,
)
identity = json.loads(out.read().decode().strip())
print(f"Current identity: {json.dumps([{k:v for k,v in s.items() if k in ['hostname','name']} for s in identity.get('data',[])])}")

_, out, _ = nas.exec_command(
    "docker exec unifi curl -sk -b /tmp/uc "
    "'https://localhost:8443/api/s/default/get/setting/super_mgmt' 2>&1",
    timeout=15,
)
mgmt = json.loads(out.read().decode().strip())
for s in mgmt.get("data", []):
    print(f"Current mgmt: override_inform={s.get('override_inform_host')}, inform_host={s.get('inform_host')}")

# Set hostname to 192.168.1.129
sftp = nas.open_sftp()

payload1 = json.dumps({"hostname": "192.168.1.129", "name": "unifi"})
with sftp.open("/tmp/p1.json", "w") as f:
    f.write(payload1)

_, out, _ = nas.exec_command(
    "docker exec unifi curl -sk -b /tmp/uc -X PUT "
    "'https://localhost:8443/api/s/default/set/setting/super_identity' "
    '-H "Content-Type: application/json" '
    '-d "$(cat /tmp/p1.json)" 2>&1',
    timeout=15,
)
print(f"Set hostname: {out.read().decode().strip()[:100]}")

# Set override inform host
payload2 = json.dumps({"override_inform_host": True, "inform_host": "192.168.1.129"})
with sftp.open("/tmp/p2.json", "w") as f:
    f.write(payload2)

_, out, _ = nas.exec_command(
    "docker exec unifi curl -sk -b /tmp/uc -X PUT "
    "'https://localhost:8443/api/s/default/set/setting/super_mgmt' "
    '-H "Content-Type: application/json" '
    '-d "$(cat /tmp/p2.json)" 2>&1',
    timeout=15,
)
print(f"Set inform override: {out.read().decode().strip()[:100]}")

sftp.close()

# ============================================================
# Step 2: Check all devices
# ============================================================
print("\n=== Step 2: Device status ===")

_, out, _ = nas.exec_command(
    "docker exec unifi curl -sk -b /tmp/uc "
    "'https://localhost:8443/api/s/default/stat/device' 2>&1",
    timeout=15,
)
devices = json.loads(out.read().decode().strip()).get("data", [])
for d in devices:
    name = d.get("name", "?")
    dtype = d.get("type", "?")
    state = d.get("state", "?")
    ip = d.get("ip", "?")
    adopted = d.get("adopted", False)
    inform = d.get("inform_url", "?")
    state_text = {0: "DISCONNECTED", 1: "CONNECTED", 2: "PENDING", 4: "UPGRADING", 5: "PROVISIONING"}.get(state, f"UNKNOWN({state})")
    print(f"  {name}: type={dtype} ip={ip} state={state_text} adopted={adopted}")
    print(f"    inform_url={inform}")

# ============================================================
# Step 3: Try to force adopt/provision USG
# ============================================================
print("\n=== Step 3: Force adopt/provision ===")

for d in devices:
    if d.get("type") == "ugw":
        mac = d.get("mac")
        state = d.get("state")

        if state == 0:
            # Disconnected - try force adopt
            print(f"USG is disconnected. Trying set-inform via SSH from NAS...")

            # Since we can't SSH to USG, try to send set-inform packet
            # The USG needs to know the new Controller IP
            # Method: use the Controller's built-in device discovery

            # Try L3 adoption (send inform URL to USG)
            payload = json.dumps({
                "cmd": "set-inform",
                "inform_url": "http://192.168.1.129:8080/inform",
                "mac": mac,
            })
            sftp = nas.open_sftp()
            with sftp.open("/tmp/p3.json", "w") as f:
                f.write(payload)
            sftp.close()

            _, out, _ = nas.exec_command(
                "docker exec unifi curl -sk -b /tmp/uc -X POST "
                "'https://localhost:8443/api/s/default/cmd/devmgr' "
                '-H "Content-Type: application/json" '
                '-d "$(cat /tmp/p3.json)" 2>&1',
                timeout=15,
            )
            print(f"  set-inform: {out.read().decode().strip()[:200]}")

            # Also try force-provision
            payload4 = json.dumps({"cmd": "force-provision", "mac": mac})
            sftp = nas.open_sftp()
            with sftp.open("/tmp/p4.json", "w") as f:
                f.write(payload4)
            sftp.close()

            _, out, _ = nas.exec_command(
                "docker exec unifi curl -sk -b /tmp/uc -X POST "
                "'https://localhost:8443/api/s/default/cmd/devmgr' "
                '-H "Content-Type: application/json" '
                '-d "$(cat /tmp/p4.json)" 2>&1',
                timeout=15,
            )
            print(f"  force-provision: {out.read().decode().strip()[:200]}")

        elif state == 1:
            print("USG is CONNECTED! Pushing config...")
            # Force provision to push all settings
            payload = json.dumps({"cmd": "force-provision", "mac": mac})
            sftp = nas.open_sftp()
            with sftp.open("/tmp/p5.json", "w") as f:
                f.write(payload)
            sftp.close()

            _, out, _ = nas.exec_command(
                "docker exec unifi curl -sk -b /tmp/uc -X POST "
                "'https://localhost:8443/api/s/default/cmd/devmgr' "
                '-H "Content-Type: application/json" '
                '-d "$(cat /tmp/p5.json)" 2>&1',
                timeout=15,
            )
            print(f"  provision: {out.read().decode().strip()[:200]}")

# ============================================================
# Step 4: Check USG SSH with controller password
# ============================================================
print("\n=== Step 4: Check device SSH settings ===")

_, out, _ = nas.exec_command(
    "docker exec unifi curl -sk -b /tmp/uc "
    "'https://localhost:8443/api/s/default/get/setting/mgmt' 2>&1",
    timeout=15,
)
mgmt_data = json.loads(out.read().decode().strip())
for s in mgmt_data.get("data", []):
    user = s.get("x_ssh_username", "?")
    pw = s.get("x_ssh_password", "?")
    enabled = s.get("x_ssh_enabled", False)
    print(f"  Device SSH: user={user} pw={pw} enabled={enabled}")

print("\nWaiting 30s for USG to respond...")
time.sleep(30)

# Check state again
_, out, _ = nas.exec_command(
    "docker exec unifi curl -sk -b /tmp/uc "
    "'https://localhost:8443/api/s/default/stat/device' 2>&1",
    timeout=15,
)
devices2 = json.loads(out.read().decode().strip()).get("data", [])
for d in devices2:
    if d.get("type") == "ugw":
        state = d.get("state", "?")
        state_text = {0: "DISCONNECTED", 1: "CONNECTED", 2: "PENDING", 4: "UPGRADING", 5: "PROVISIONING"}.get(state, f"UNKNOWN({state})")
        print(f"\nUSG state after 30s: {state_text}")
        print(f"  inform_url: {d.get('inform_url', '?')}")

# Try SSH again
print("\n=== Step 5: Try USG SSH ===")
try:
    j = paramiko.SSHClient()
    j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    j.connect("192.168.1.1", username="ops", password="exampleusgpass", timeout=5)
    print("SSH SUCCESS with mllab/exampleusgpass!")
    _, out, _ = j.exec_command("mca-cli-op info | head -5", timeout=5)
    print(out.read().decode().strip())
    j.close()
except Exception as e:
    print(f"SSH failed: {e}")

nas.close()
print("\n=== DONE ===")
