#!/usr/bin/env python3
"""Try to login to newly found devices on legacy ports."""
import paramiko
import time

nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.129", username="admin", password="examplepass", timeout=5)
print("Connected to NAS\n")

devices = [
    ("192.168.1.202", 12050, "server5?"),
    ("192.168.1.220", 12110, "server11?"),
]

users = ["admin", "ops"]
passwords = [
    "examplepass",
    "legacypass05",
    "legacypass10",
    "legacypass06",
    "legacypass07",
    "legacypass08",
    "legacypass16",
    "legacypass09",
    "legacypass11",
    "legacypass12",
    "legacypass13",
    "legacypass04",
    "legacypass02",
    "legacypass03",
    "legacypass01",
    "legacypass14",
    "legacypass15",
    "examplenaspass",
    "exampleswitchpass",
    "ops",
]

for ip, port, guess in devices:
    print(f"=== {ip}:{port} (maybe {guess}) ===")
    found = False
    for user in users:
        if found:
            break
        for pw in passwords:
            cmd = (
                f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no "
                f"-o ConnectTimeout=5 -o NumberOfPasswordPrompts=1 "
                f"-p {port} {user}@{ip} "
                f"'echo SUCCESS; hostname; hostname -I; "
                f"nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo NO-GPU; "
                f"cat /proc/cpuinfo | grep \"model name\" | head -1; "
                f"free -h | grep Mem | awk \"{{print \\$2}}\"; "
                f"ip link show | grep \"link/ether\" | head -1 | awk \"{{print \\$2}}\"' 2>&1"
            )
            _, out, _ = nas.exec_command(cmd, timeout=15)
            result = out.read().decode().strip()
            if "SUCCESS" in result:
                print(f"  FOUND! user={user} pw={pw}")
                for line in result.split("\n"):
                    print(f"  {line}")
                found = True
                break
            elif "timed out" in result.lower() or "refused" in result.lower():
                print(f"  Connection error: {result[:60]}")
                break
            time.sleep(0.3)
    if not found:
        print("  All passwords failed")
    print()

nas.close()
print("=== DONE ===")
