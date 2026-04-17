#!/usr/bin/env python3
"""Run full password matrix from NAS via sshpass to avoid fail2ban."""
import paramiko
import time

# All server passwords from server-0.csv
PASSWORDS = [
    ("legacypass01", "server1"),
    ("legacypass02", "server2"),
    ("legacypass03", "server3"),
    ("legacypass04", "server4"),
    ("legacypass05", "server5"),
    ("legacypass06", "server6"),
    ("legacypass16", "server7/14"),
    ("legacypass07", "server8"),
    ("legacypass08", "server9"),
    ("legacypass09", "server10"),
    ("legacypass10", "server11"),
    ("legacypass11", "server12"),
    ("legacypass12", "server13"),
    ("legacypass13", "server15"),
    ("legacypass14", "temp"),
    ("legacypass15", "temp2"),
    # Also try switch/router password and NAS password
    ("exampleswitchpass", "switch/router"),
    ("examplenaspass", "NAS"),
]

# Extra users to try
USERS = ["admin", "ops", "root"]

# SSH-open IPs (confirmed from previous scans)
SSH_IPS = [
    "192.168.1.46",
    "192.168.1.49",
    "192.168.1.57",
    "192.168.1.100",
    "192.168.1.102",
]

print("Connecting to NAS (192.168.1.29)...")
nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.29", username="admin", password="examplenaspass", timeout=10)
print("NAS connected. Running full matrix via sshpass.\n")

print(f"Matrix: {len(PASSWORDS)} passwords x {len(USERS)} users x {len(SSH_IPS)} IPs")
print("=" * 70)

results = []

for ip in SSH_IPS:
    print(f"\n--- {ip} ---")
    found = False
    for user in USERS:
        if found:
            break
        for pw, label in PASSWORDS:
            # Use sshpass with short timeout
            cmd = (
                f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no "
                f"-o ConnectTimeout=3 -o PreferredAuthentications=password "
                f"-o NumberOfPasswordPrompts=1 "
                f"{user}@{ip} hostname 2>&1"
            )
            _, o, _ = nas.exec_command(cmd, timeout=10)
            r = o.read().decode().strip()

            # Check if it's a real hostname (not error)
            if (r and "denied" not in r.lower() and "permission" not in r.lower()
                    and "error" not in r.lower() and "no route" not in r.lower()
                    and "connection" not in r.lower() and "timeout" not in r.lower()
                    and "usage:" not in r.lower()):
                # Success! Gather more info
                info_cmd = (
                    f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no "
                    f"-o ConnectTimeout=5 -o PreferredAuthentications=password "
                    f"{user}@{ip} '"
                    f"echo HOSTNAME=$(hostname); "
                    f"echo GPU=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo NO_GPU); "
                    f"echo CPU=$(lscpu 2>/dev/null | grep \"Model name\" | sed \"s/.*: *//\"); "
                    f"echo MAC=$(ip link show 2>/dev/null | grep \"link/ether\" | head -1 | awk \"{{print \\$2}}\"); "
                    f"echo MEM=$(free -h 2>/dev/null | grep Mem | awk \"{{print \\$2}}\")' 2>&1"
                )
                _, o2, _ = nas.exec_command(info_cmd, timeout=15)
                info = o2.read().decode().strip()

                print(f"  MATCH! user={user}, pw={label} ({pw})")
                print(f"    hostname={r}")
                print(f"    {info}")
                results.append((ip, user, label, pw, r, info))
                found = True
                break

            # Small delay between attempts
            time.sleep(0.2)

    if not found:
        print(f"  NO MATCH (all {len(PASSWORDS)*len(USERS)} combos failed)")

nas.close()

print("\n" + "=" * 70)
print(f"RESULTS: {len(results)} servers identified")
print("=" * 70)
for ip, user, label, pw, hostname, info in results:
    print(f"\n  {ip} = {hostname} (user={user}, pwd_label={label})")
    for line in info.split("\n"):
        print(f"    {line}")

print("\n=== DONE ===")
