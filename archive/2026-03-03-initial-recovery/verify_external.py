#!/usr/bin/env python3
"""Verify external SSH + force DHCP renewal on accessible servers."""
import paramiko
import socket
import time

WAN_IP = "203.0.113.10"

# ============================================================
# Part 1: Force DHCP renewal on servers we can SSH into (internal)
# ============================================================
print("=" * 60)
print("PART 1: Force DHCP renewal via internal SSH")
print("=" * 60)

ACCESSIBLE = [
    ("192.168.1.6",   "admin",   "legacypass06", "server6"),
    ("192.168.1.14",  "ops", "examplepass",       "server22"),
    ("192.168.1.100", "ops", "examplepass",       "Pro6000"),
    ("192.168.1.102", "ops", "examplepass",       "server20"),
]

for ip, user, pw, name in ACCESSIBLE:
    print(f"\n--- {name} ({ip}) ---")
    try:
        j = paramiko.SSHClient()
        j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        j.connect(ip, username=user, password=pw, timeout=5)

        # Show current IP
        _, out, _ = j.exec_command("hostname -I", timeout=5)
        current = out.read().decode().strip()
        print(f"  Current IPs: {current}")

        # Force DHCP renewal
        if user == "ops":
            # Try with sudo
            _, out, err = j.exec_command(
                f"echo '{pw}' | sudo -S dhclient -r 2>&1 && echo '{pw}' | sudo -S dhclient 2>&1",
                timeout=15
            )
        else:
            _, out, err = j.exec_command("sudo dhclient -r 2>&1 && sudo dhclient 2>&1", timeout=15)
        result = out.read().decode().strip()
        print(f"  DHCP renew: {result[:100] if result else 'OK (silent)'}")

        # Check new IP
        time.sleep(2)
        _, out, _ = j.exec_command("hostname -I", timeout=5)
        new_ip = out.read().decode().strip()
        print(f"  New IPs: {new_ip}")

        j.close()
    except Exception as e:
        print(f"  Error: {e}")

# Wait a moment for network to settle
print("\nWaiting 5s for network to settle...")
time.sleep(5)

# ============================================================
# Part 2: Test external SSH connectivity (hairpin NAT from inside)
# ============================================================
print("\n" + "=" * 60)
print("PART 2: Test external SSH via WAN IP (hairpin NAT)")
print("=" * 60)

PORT_MAP = {
    12060: ("server6",  ".106"),
    12080: ("server8",  ".108"),
    12090: ("server9",  ".109"),
    12150: ("server15", ".115"),
    12200: ("server20", ".120"),
    12210: ("server21", ".121"),
    12220: ("server22", ".122"),
    12230: ("Pro6000",  ".123"),
}

for port, (name, target) in sorted(PORT_MAP.items()):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((WAN_IP, port))
        if result == 0:
            # Try to read SSH banner
            try:
                banner = sock.recv(256).decode().strip()
            except:
                banner = "(connected, no banner)"
            print(f"  :{port} -> {target} {name:12s}  OPEN  {banner[:60]}")
        else:
            print(f"  :{port} -> {target} {name:12s}  CLOSED/TIMEOUT")
        sock.close()
    except Exception as e:
        print(f"  :{port} -> {target} {name:12s}  ERROR: {e}")

# ============================================================
# Part 3: Try actual SSH auth on reachable external ports
# ============================================================
print("\n" + "=" * 60)
print("PART 3: Test SSH auth via WAN IP")
print("=" * 60)

CREDS = {
    "server6":  ("admin",   "legacypass06"),
    "server20": ("ops", "examplepass"),
    "server22": ("ops", "examplepass"),
    "Pro6000":  ("ops", "examplepass"),
}

for port, (name, target) in sorted(PORT_MAP.items()):
    if name not in CREDS:
        continue
    user, pw = CREDS[name]
    try:
        j = paramiko.SSHClient()
        j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        j.connect(WAN_IP, port=port, username=user, password=pw, timeout=5)
        _, out, _ = j.exec_command("hostname", timeout=5)
        hostname = out.read().decode().strip()
        j.close()
        print(f"  :{port} {name:12s}  SSH OK -> hostname={hostname}")
    except paramiko.AuthenticationException:
        print(f"  :{port} {name:12s}  CONNECTED but auth failed")
    except Exception as e:
        err = str(e)[:60]
        print(f"  :{port} {name:12s}  {err}")

print("\n=== DONE ===")
