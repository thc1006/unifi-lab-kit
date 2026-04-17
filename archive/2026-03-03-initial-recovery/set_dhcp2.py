#!/usr/bin/env python3
"""Set DHCP reservations via UniFi Controller API - fixed login."""
import requests
import json
import urllib3
urllib3.disable_warnings()

BASE = "https://192.168.1.60:8443"
s = requests.Session()
s.verify = False

# Login with 2FA
r = s.post(f"{BASE}/api/login", json={
    "username": "admin@example.com",
    "password": "exampleunifipass",
    "ubic_2fa_token": "132514"
})
print(f"Login: {r.status_code} {r.text[:80]}")

if r.status_code != 200:
    # Try alternate username with 2FA
    r = s.post(f"{BASE}/api/login", json={
        "username": "mllabjtc",
        "password": "exampleunifipass",
        "ubic_2fa_token": "132514"
    })
    print(f"Login2: {r.status_code} {r.text[:80]}")

csrf = s.cookies.get("csrf_token")
if csrf:
    s.headers["X-Csrf-Token"] = csrf
    print(f"CSRF: {csrf[:20]}...")

# Test
r = s.get(f"{BASE}/api/s/default/stat/sta")
print(f"Test: {r.status_code}, clients: {len(r.json().get('data', []))}")

if r.status_code != 200:
    print("Login failed, cannot proceed")
    exit(1)

clients = r.json().get("data", [])
r2 = s.get(f"{BASE}/api/s/default/rest/user")
users = r2.json().get("data", [])
print(f"Users: {len(users)}")

# Build lookup
mac_to_user = {u.get("mac"): u for u in users}
mac_to_client = {c.get("mac"): c for c in clients}

# Find server8 full MAC
server8_mac = None
for c in clients:
    if c.get("mac", "").endswith("91:ce"):
        server8_mac = c["mac"]
        print(f"\nserver8 full MAC: {server8_mac}")
        break
for u in users:
    if u.get("mac", "").endswith("91:ce") or "server8" in u.get("name", "").lower():
        server8_mac = u["mac"]
        print(f"\nserver8 from users: {server8_mac}")
        break

RESERVATIONS = {
    "00:00:5e:00:53:06": ("192.168.1.106", "server6"),
    "00:00:5e:00:53:09": ("192.168.1.109", "server9"),
    "00:00:5e:00:53:15": ("192.168.1.115", "server15"),
    "00:00:5e:00:53:20": ("192.168.1.120", "server20"),
    "00:00:5e:00:53:21": ("192.168.1.121", "server21"),
    "00:00:5e:00:53:22": ("192.168.1.122", "server22"),
    "00:00:5e:00:53:23": ("192.168.1.123", "server-Pro6000"),
    "00:00:5e:00:53:29": ("192.168.1.129", "NAS"),
}
if server8_mac:
    RESERVATIONS[server8_mac] = ("192.168.1.108", "server8")

print(f"\nSetting {len(RESERVATIONS)} DHCP reservations...")
print("=" * 60)

# Get the default network ID
r = s.get(f"{BASE}/api/s/default/rest/networkconf")
nets = r.json().get("data", [])
net_id = ""
for n in nets:
    if n.get("purpose") == "corporate" or n.get("name") == "Default" or "LAN" in n.get("name", ""):
        net_id = n["_id"]
        print(f"Network: {n.get('name')} ({net_id})")
        break

for mac, (fixed_ip, name) in RESERVATIONS.items():
    print(f"\n{name}: {mac} -> {fixed_ip}")

    user = mac_to_user.get(mac)
    if user:
        uid = user["_id"]
        payload = {
            "name": name,
            "use_fixedip": True,
            "fixed_ip": fixed_ip,
        }
        if net_id:
            payload["network_id"] = net_id
        r = s.put(f"{BASE}/api/s/default/rest/user/{uid}", json=payload)
        print(f"  PUT: {r.status_code} {r.text[:120]}")
    else:
        payload = {
            "mac": mac,
            "name": name,
            "use_fixedip": True,
            "fixed_ip": fixed_ip,
        }
        if net_id:
            payload["network_id"] = net_id
        r = s.post(f"{BASE}/api/s/default/rest/user", json=payload)
        print(f"  POST: {r.status_code} {r.text[:120]}")

# Verify
print("\n" + "=" * 60)
print("Verifying...")
r = s.get(f"{BASE}/api/s/default/rest/user")
for u in r.json().get("data", []):
    if u.get("use_fixedip"):
        print(f"  {u.get('mac'):>20} -> {u.get('fixed_ip',''):>15}  {u.get('name','?')}")

print("\n=== DONE ===")
