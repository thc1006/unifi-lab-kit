#!/usr/bin/env python3
"""Set new port forwards + shrink DHCP range via UniFi Controller API."""
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
    "ubic_2fa_token": "418966"
})
print(f"Login: {r.status_code} {r.text[:80]}")
if r.status_code != 200:
    # Try without 2FA field name variants
    for token_field in ["token", "2fa_token"]:
        r = s.post(f"{BASE}/api/login", json={
            "username": "admin@example.com",
            "password": "exampleunifipass",
            token_field: "418966"
        })
        if r.status_code == 200:
            print(f"Login OK with field '{token_field}'")
            break
    if r.status_code != 200:
        print(f"Login failed: {r.text[:150]}")
        exit(1)

csrf = s.cookies.get("csrf_token")
if csrf:
    s.headers["X-Csrf-Token"] = csrf

# ============================================================
# Part 1: List existing port forwards
# ============================================================
print("\n" + "=" * 60)
print("EXISTING PORT FORWARDS")
print("=" * 60)

r = s.get(f"{BASE}/api/s/default/rest/portforward")
existing_pf = r.json().get("data", [])
existing_ports = set()
for pf in existing_pf:
    dst_port = pf.get("dst_port", "")
    fwd = pf.get("fwd", "")
    fwd_port = pf.get("fwd_port", "")
    name = pf.get("name", "")
    enabled = pf.get("enabled", True)
    print(f"  {name:25s}  :{dst_port:>5} -> {fwd}:{fwd_port}  {'ON' if enabled else 'OFF'}")
    existing_ports.add(str(dst_port))

# ============================================================
# Part 2: Create new port forwards
# ============================================================
print("\n" + "=" * 60)
print("CREATING NEW PORT FORWARDS")
print("=" * 60)

NEW_RULES = [
    ("server20-ssh", "12200", "192.168.1.120", "22"),
    ("server21-ssh", "12210", "192.168.1.121", "22"),
    ("server22-ssh", "12220", "192.168.1.122", "22"),
    ("Pro6000-ssh",  "12230", "192.168.1.123", "22"),
]

for name, dst_port, fwd_ip, fwd_port in NEW_RULES:
    if dst_port in existing_ports:
        print(f"  SKIP {name}: port {dst_port} already exists")
        continue

    payload = {
        "name": name,
        "enabled": True,
        "proto": "tcp",
        "dst_port": dst_port,
        "fwd": fwd_ip,
        "fwd_port": fwd_port,
        "src": "any",
        "log": False,
    }
    r = s.post(f"{BASE}/api/s/default/rest/portforward", json=payload)
    print(f"  {name}: :{dst_port} -> {fwd_ip}:{fwd_port}  => {r.status_code} {r.text[:100]}")

# Verify port forwards
print("\nVerifying all port forwards...")
r = s.get(f"{BASE}/api/s/default/rest/portforward")
all_pf = r.json().get("data", [])
print(f"Total port forward rules: {len(all_pf)}")
for pf in sorted(all_pf, key=lambda x: x.get("dst_port", "")):
    dst_port = pf.get("dst_port", "")
    fwd = pf.get("fwd", "")
    fwd_port = pf.get("fwd_port", "")
    name = pf.get("name", "")
    print(f"  {name:25s}  :{dst_port:>5} -> {fwd}:{fwd_port}")

# ============================================================
# Part 3: Shrink DHCP range to .200-.254
# ============================================================
print("\n" + "=" * 60)
print("SHRINKING DHCP RANGE")
print("=" * 60)

r = s.get(f"{BASE}/api/s/default/rest/networkconf")
nets = r.json().get("data", [])
for n in nets:
    if n.get("purpose") == "corporate" or n.get("name") == "Default" or "LAN" in n.get("name", ""):
        net_id = n["_id"]
        old_start = n.get("dhcpd_start", "?")
        old_stop = n.get("dhcpd_stop", "?")
        print(f"  Network: {n.get('name')} ({net_id})")
        print(f"  Current DHCP range: {old_start} - {old_stop}")

        payload = {
            "dhcpd_start": "192.168.1.200",
            "dhcpd_stop": "192.168.1.254",
        }
        r = s.put(f"{BASE}/api/s/default/rest/networkconf/{net_id}", json=payload)
        print(f"  Update: {r.status_code}")
        if r.status_code == 200:
            data = r.json().get("data", [{}])
            if data:
                d = data[0] if isinstance(data, list) else data
                print(f"  New DHCP range: {d.get('dhcpd_start', '?')} - {d.get('dhcpd_stop', '?')}")
        else:
            print(f"  Error: {r.text[:200]}")
        break

print("\n=== ALL DONE ===")
