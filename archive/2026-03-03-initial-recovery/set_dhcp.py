#!/usr/bin/env python3
"""Set DHCP reservations via UniFi Controller API."""
import requests
import json
import urllib3
urllib3.disable_warnings()

BASE = "https://192.168.1.60:8443"
s = requests.Session()
s.verify = False

# Login
r = s.post(f"{BASE}/api/login", json={
    "username": "admin@example.com",
    "password": "exampleunifipass"
})
print(f"Login: {r.status_code}")
csrf = s.cookies.get("csrf_token")
if csrf:
    s.headers["X-Csrf-Token"] = csrf

# DHCP reservations: MAC -> target fixed IP
RESERVATIONS = {
    # Known servers (matching port forward scheme)
    "00:00:5e:00:53:06": ("192.168.1.106", "server6"),
    "00:00:5e:00:53:09": ("192.168.1.109", "server9"),
    "00:00:5e:00:53:15": ("192.168.1.115", "server15"),
    # New servers
    "00:00:5e:00:53:20": ("192.168.1.120", "server20"),
    "00:00:5e:00:53:21": ("192.168.1.121", "server21"),
    "00:00:5e:00:53:22": ("192.168.1.122", "server22"),
    "00:00:5e:00:53:23": ("192.168.1.123", "server-Pro6000"),
    # NAS
    "00:00:5e:00:53:29": ("192.168.1.129", "NAS"),
}

# First, get all known clients to find their _id
r = s.get(f"{BASE}/api/s/default/stat/sta")
clients = r.json().get("data", [])
print(f"Got {len(clients)} clients\n")

# Build MAC -> client ID map
mac_to_client = {}
for c in clients:
    mac = c.get("mac", "")
    mac_to_client[mac] = c

# Also get user records (includes offline devices)
r = s.get(f"{BASE}/api/s/default/rest/user")
users = r.json().get("data", [])
print(f"Got {len(users)} user records\n")

mac_to_user = {}
for u in users:
    mac = u.get("mac", "")
    mac_to_user[mac] = u

# Set DHCP reservations
for mac, (fixed_ip, name) in RESERVATIONS.items():
    print(f"--- {name}: {mac} -> {fixed_ip} ---")

    # Check if user record exists
    user = mac_to_user.get(mac)
    if user:
        uid = user["_id"]
        print(f"  Found user record: {uid}")
        # Update existing user
        payload = {
            "name": name,
            "use_fixedip": True,
            "fixed_ip": fixed_ip,
            "network_id": user.get("network_id", ""),
        }
        r = s.put(f"{BASE}/api/s/default/rest/user/{uid}", json=payload)
        print(f"  Update: {r.status_code} {r.text[:100]}")
    else:
        # Create new user record
        print(f"  No user record, creating...")
        payload = {
            "mac": mac,
            "name": name,
            "use_fixedip": True,
            "fixed_ip": fixed_ip,
        }
        r = s.post(f"{BASE}/api/s/default/rest/user", json=payload)
        print(f"  Create: {r.status_code} {r.text[:100]}")

# Also handle server8 - we need the full MAC
# From controller: "server8 91:ce" - need full MAC
# Let's search for it
print("\n--- Looking for server8 MAC ---")
for u in users:
    if "server8" in u.get("name", "").lower() or "91:ce" in u.get("mac", ""):
        print(f"  Found: {u.get('mac')} = {u.get('name')}")
        mac8 = u.get("mac")
        uid8 = u["_id"]
        payload = {
            "name": "server8",
            "use_fixedip": True,
            "fixed_ip": "192.168.1.108",
            "network_id": u.get("network_id", ""),
        }
        r = s.put(f"{BASE}/api/s/default/rest/user/{uid8}", json=payload)
        print(f"  Update: {r.status_code} {r.text[:100]}")
        break
else:
    # Search in clients
    for c in clients:
        if "91:ce" in c.get("mac", ""):
            print(f"  Found in clients: {c.get('mac')}")
            mac8 = c.get("mac")
            payload = {
                "mac": mac8,
                "name": "server8",
                "use_fixedip": True,
                "fixed_ip": "192.168.1.108",
            }
            r = s.post(f"{BASE}/api/s/default/rest/user", json=payload)
            print(f"  Create: {r.status_code} {r.text[:100]}")
            break
    else:
        print("  server8 MAC not found!")

# Verify
print("\n=== Verifying DHCP reservations ===")
r = s.get(f"{BASE}/api/s/default/rest/user")
users2 = r.json().get("data", [])
for u in users2:
    if u.get("use_fixedip"):
        print(f"  {u.get('mac'):>20} -> {u.get('fixed_ip', 'N/A'):>15}  ({u.get('name', '?')})")

print("\n=== DONE ===")
