#!/usr/bin/env python3
"""Quick sshpass test from NAS."""
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.1.29", username="admin", password="examplenaspass", timeout=10)
print("NAS connected")

# Test sshpass on SSH-open IPs with targeted passwords
tests = [
    ("192.168.1.102", "admin", "legacypass02", "srv2?"),
    ("192.168.1.14", "admin", "legacypass03", "srv3?"),
    ("192.168.1.21", "admin", "legacypass08", "srv9?"),
    ("192.168.1.46", "admin", "legacypass07", "srv8?"),
    ("192.168.1.49", "admin", "legacypass09", "srv10?"),
    ("192.168.1.57", "admin", "legacypass10", "srv11?"),
    ("192.168.1.100", "admin", "legacypass11", "srv12?"),
]

for ip, user, pw, label in tests:
    _, o, _ = c.exec_command(
        f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=2 "
        f"-o PreferredAuthentications=password {user}@{ip} hostname 2>&1",
        timeout=10
    )
    r = o.read().decode().strip()
    status = "OK" if r and "denied" not in r.lower() and "error" not in r.lower() else "FAIL"
    print(f"  {ip} ({label}): {user}/{pw} -> {status}: {r[:60]}")

# Now try ALL passwords on each IP systematically
PASSWORDS = [
    "legacypass01", "legacypass02", "legacypass03", "legacypass04",
    "legacypass05", "legacypass06", "legacypass16", "legacypass07",
    "legacypass08", "legacypass09", "legacypass10", "legacypass11",
    "legacypass12", "legacypass13", "legacypass14", "legacypass15",
    "examplenaspass", "exampleswitchpass", "examplewifipass",
]

SSH_IPS = ["192.168.1.14", "192.168.1.21", "192.168.1.46", "192.168.1.49",
           "192.168.1.57", "192.168.1.100", "192.168.1.102"]

print("\n=== Full scan: all passwords on all SSH IPs ===")
for ip in SSH_IPS:
    found = False
    for user in ["admin", "ops", "root"]:
        if found:
            break
        for pw in PASSWORDS:
            _, o, _ = c.exec_command(
                f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=2 "
                f"-o PreferredAuthentications=password -o NumberOfPasswordPrompts=1 "
                f"{user}@{ip} hostname 2>&1",
                timeout=8
            )
            r = o.read().decode().strip()
            if r and "denied" not in r.lower() and "error" not in r.lower() and "Permission" not in r:
                # Get GPU info too
                _, o2, _ = c.exec_command(
                    f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 "
                    f"{user}@{ip} 'nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo NO_GPU' 2>&1",
                    timeout=10
                )
                gpu = o2.read().decode().strip()
                print(f"  MATCH {ip}: user={user} pw={pw} hostname={r} gpu={gpu}")
                found = True
                break
    if not found:
        print(f"  FAIL {ip}: no password matched")

c.close()
print("\n=== DONE ===")
