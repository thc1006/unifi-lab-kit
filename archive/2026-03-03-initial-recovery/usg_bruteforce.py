#!/usr/bin/env python3
"""Exhaustive password attempt for USG-3P using ALL passwords from CSV."""
import paramiko
import socket
import time

HOST = "192.168.1.1"

# ALL unique passwords found anywhere in server-0.csv
ALL_PASSWORDS = [
    # USG/Switch specific
    "exampleswitchpass",
    # UniFi Controller
    "exampleunifipass",
    "exampleunifipass",
    "examplepassunifi",
    "examplepass",
    # ASUS Router
    "mllabasus",
    "mllab912_router",
    # Server SSH passwords
    "legacypass01",
    "legacypass02",
    "legacypass03",
    "legacypass04",
    "legacypass05",
    "legacypass06",
    "legacypass16",
    "legacypass07",
    "legacypass08",
    "legacypass09",
    "legacypass10",
    "legacypass11",
    "legacypass12",
    "legacypass13",
    "legacypass14",
    "legacypass15",
    # NAS / Nextcloud
    "examplenaspass",
    "mllab912jtc",
    # H264
    "MLLABH264",
    "MLLAB264",
    # GitHub
    "Mllabjtc912",
    # Common patterns
    "ops",
    "examplepass",
    "mllab912",
    "ubnt",
    "admin",
    "",
    "password",
    "unifi",
    # User suggested
    "examplepass",
    # Adoption key from QR code
    "UOeyDr",
]

# ALL unique usernames
ALL_USERS = ["ops", "ubnt", "admin", "root", "admin", "mllab_router", "mllab_ncadmin"]

# Remove duplicates while preserving order
seen_pw = set()
unique_pw = []
for p in ALL_PASSWORDS:
    if p not in seen_pw:
        seen_pw.add(p)
        unique_pw.append(p)


def try_login(user, pwd):
    try:
        sock = socket.create_connection((HOST, 22), timeout=8)
        t = paramiko.Transport(sock)
        t.banner_timeout = 20
        t.start_client()
        t.auth_password(user, pwd)
        if t.is_authenticated():
            c = paramiko.SSHClient()
            c._transport = t
            return c
        t.close()
    except paramiko.AuthenticationException:
        pass
    except Exception as e:
        print(f"    [{e}]")
        time.sleep(3)
    return None


def run_cmd(c, cmd, timeout=10):
    try:
        _, stdout, _ = c.exec_command(cmd, timeout=timeout)
        return stdout.read().decode("utf-8", errors="replace").strip()
    except Exception as e:
        return f"[ERROR]: {e}"


print(f"Trying {len(ALL_USERS)} users x {len(unique_pw)} passwords = {len(ALL_USERS) * len(unique_pw)} combinations\n")

for user in ALL_USERS:
    for pwd in unique_pw:
        label = f"{user}/{pwd or '(empty)'}"
        print(f"  {label}...", end=" ", flush=True)
        c = try_login(user, pwd)
        if c:
            print("SUCCESS!!!")
            print(f"\n{'='*60}")
            print(f"  USG LOGIN: {user} / {pwd}")
            print(f"{'='*60}\n")
            for cmd in ["show version", "show interfaces", "show configuration commands",
                        "show nat rules", "show dhcp leases", "show arp"]:
                print(f">>> {cmd}")
                print(run_cmd(c, cmd))
                print()
            c.close()
            exit(0)
        else:
            print("x")

print("\n" + "=" * 60)
print("ALL COMBINATIONS FAILED")
print("=" * 60)
print("\nNext steps:")
print("1. Find and start the UniFi Controller")
print("   Check Settings > System > Device Authentication")
print("2. Or factory reset the USG again (hold reset 10s)")
print("   Then SSH with ubnt/ubnt BEFORE adopting")
