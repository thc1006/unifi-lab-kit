#!/usr/bin/env python3
"""Add DHCP reservation for server11 via docker exec into UniFi container."""
import paramiko
import json
import time

nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.129", username="admin", password="examplepass", timeout=5)
print("Connected to NAS")

# Login from inside the container (no 2FA needed from localhost)
login_cmd = (
    "docker exec unifi curl -sk -X POST https://localhost:8443/api/login "
    "-H 'Content-Type: application/json' "
    "-d '{\"username\":\"admin@example.com\",\"password\":\"exampleunifipass\"}' "
    "-c /tmp/uc 2>&1"
)
_, out, _ = nas.exec_command(login_cmd, timeout=15)
login_result = out.read().decode().strip()
print(f"Login: {login_result[:100]}")

if '"ok"' not in login_result:
    print("Login failed!")
    nas.close()
    exit(1)

# Check existing DHCP reservations
check_cmd = (
    "docker exec unifi curl -sk -b /tmp/uc "
    "'https://localhost:8443/api/s/default/rest/user' 2>&1"
)
_, out, _ = nas.exec_command(check_cmd, timeout=15)
users_raw = out.read().decode().strip()
try:
    users = json.loads(users_raw).get("data", [])
    print(f"\nExisting reservations:")
    for u in users:
        if u.get("use_fixedip"):
            print(f"  {u.get('mac'):>20} -> {u.get('fixed_ip',''):>15}  {u.get('name','?')}")
except:
    print(f"Parse error: {users_raw[:200]}")
    users = []

# Check if server11 MAC already exists
MAC = "00:00:5e:00:53:11"
TARGET_IP = "192.168.1.111"
NAME = "server11"

existing = None
for u in users:
    if u.get("mac") == MAC:
        existing = u
        break

if existing:
    uid = existing["_id"]
    print(f"\nserver11 MAC already in DB (id={uid}), updating...")
    update_cmd = (
        f"docker exec unifi curl -sk -b /tmp/uc -X PUT "
        f"'https://localhost:8443/api/s/default/rest/user/{uid}' "
        f"-H 'Content-Type: application/json' "
        f"-d '{{\"name\":\"{NAME}\",\"use_fixedip\":true,\"fixed_ip\":\"{TARGET_IP}\"}}' 2>&1"
    )
    _, out, _ = nas.exec_command(update_cmd, timeout=15)
    print(f"  Result: {out.read().decode().strip()[:200]}")
else:
    print(f"\nCreating new DHCP reservation: {MAC} -> {TARGET_IP} ({NAME})")
    create_cmd = (
        f"docker exec unifi curl -sk -b /tmp/uc -X POST "
        f"'https://localhost:8443/api/s/default/rest/user' "
        f"-H 'Content-Type: application/json' "
        f"-d '{{\"mac\":\"{MAC}\",\"name\":\"{NAME}\",\"use_fixedip\":true,\"fixed_ip\":\"{TARGET_IP}\"}}' 2>&1"
    )
    _, out, _ = nas.exec_command(create_cmd, timeout=15)
    print(f"  Result: {out.read().decode().strip()[:200]}")

# Verify
print("\nVerifying...")
_, out, _ = nas.exec_command(check_cmd, timeout=15)
try:
    users2 = json.loads(out.read().decode().strip()).get("data", [])
    for u in users2:
        if u.get("mac") == MAC:
            print(f"  {u.get('mac')} -> {u.get('fixed_ip')} ({u.get('name')}) use_fixedip={u.get('use_fixedip')}")
            break
    else:
        print("  NOT FOUND!")
except:
    print("  Parse error")

nas.close()
print("\n=== DONE ===")
