#!/usr/bin/env python3
"""Add DHCP reservation for server11 via UniFi API (no 2FA needed now)."""
import paramiko
import json
import time

nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.129", username="admin", password="examplepass", timeout=5)
print("Connected to NAS")

# Login
_, out, _ = nas.exec_command(
    "docker exec unifi curl -sk -X POST https://localhost:8443/api/login "
    '-H "Content-Type: application/json" '
    "-d '{\"username\":\"mllab\",\"password\":\"examplepass\"}' "
    "-c /tmp/uc 2>&1",
    timeout=15,
)
login = out.read().decode().strip()
print(f"Login: {login[:100]}")

if '"ok"' not in login:
    print("Login failed!")
    nas.close()
    exit(1)

# Get existing users/reservations
_, out, _ = nas.exec_command(
    "docker exec unifi curl -sk -b /tmp/uc "
    "'https://localhost:8443/api/s/default/rest/user' 2>&1",
    timeout=15,
)
users_raw = out.read().decode().strip()
users = json.loads(users_raw).get("data", [])

print(f"\nExisting DHCP reservations:")
for u in users:
    if u.get("use_fixedip"):
        print(f"  {u.get('mac'):>20} -> {u.get('fixed_ip',''):>15}  {u.get('name','?')}")

# Check if server11 MAC exists
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
    print(f"\nMAC {MAC} already in DB (id={uid}), updating to {TARGET_IP}...")
    _, out, _ = nas.exec_command(
        f"docker exec unifi curl -sk -b /tmp/uc -X PUT "
        f"'https://localhost:8443/api/s/default/rest/user/{uid}' "
        f'-H "Content-Type: application/json" '
        f"-d '{{\"name\":\"{NAME}\",\"use_fixedip\":true,\"fixed_ip\":\"{TARGET_IP}\"}}' 2>&1",
        timeout=15,
    )
    print(f"  {out.read().decode().strip()[:200]}")
else:
    print(f"\nCreating new: {MAC} -> {TARGET_IP} ({NAME})")
    _, out, _ = nas.exec_command(
        f"docker exec unifi curl -sk -b /tmp/uc -X POST "
        f"'https://localhost:8443/api/s/default/rest/user' "
        f'-H "Content-Type: application/json" '
        f"-d '{{\"mac\":\"{MAC}\",\"name\":\"{NAME}\",\"use_fixedip\":true,\"fixed_ip\":\"{TARGET_IP}\"}}' 2>&1",
        timeout=15,
    )
    print(f"  {out.read().decode().strip()[:200]}")

# Verify
print("\nVerifying...")
_, out, _ = nas.exec_command(
    "docker exec unifi curl -sk -b /tmp/uc "
    "'https://localhost:8443/api/s/default/rest/user' 2>&1",
    timeout=15,
)
users2 = json.loads(out.read().decode().strip()).get("data", [])
for u in users2:
    if u.get("mac") == MAC:
        print(f"  OK: {u.get('mac')} -> {u.get('fixed_ip')} ({u.get('name')})")
        break
else:
    print("  NOT FOUND!")

nas.close()
print("\n=== DONE ===")
print("Server11 needs reboot to get new IP .111")
