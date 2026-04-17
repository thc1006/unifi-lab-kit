#!/usr/bin/env python3
"""Identify DHCP-range devices via NAS jump host."""
import paramiko
import time

nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.129", username="admin", password="examplepass", timeout=5)
print("Connected to NAS\n")

devices = ["192.168.1.200", "192.168.1.205", "192.168.1.206", "192.168.1.215"]
users = ["admin", "ops"]
passwords = [
    "examplepass",
    "legacypass06",
    "legacypass07",
    "legacypass08",
    "legacypass16",
    "legacypass09",
    "legacypass10",
    "legacypass11",
    "legacypass12",
    "legacypass13",
    "legacypass04",
    "legacypass05",
    "legacypass02",
    "legacypass03",
    "legacypass01",
    "legacypass14",
    "legacypass15",
    "examplenaspass",
    "exampleswitchpass",
]

for ip in devices:
    print(f"=== {ip} ===")
    found = False
    for user in users:
        if found:
            break
        for pw in passwords:
            cmd = (
                f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no "
                f"-o ConnectTimeout=5 -o NumberOfPasswordPrompts=1 "
                f"{user}@{ip} "
                f"'echo USER={user} PW_OK; hostname; hostname -I; "
                f"nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo NO-GPU; "
                f"cat /proc/cpuinfo | grep \"model name\" | head -1; "
                f"free -h | grep Mem | awk \"{{print \\$2}}\"; "
                f"ip link show | grep \"link/ether\" | head -1 | awk \"{{print \\$2}}\"' 2>&1"
            )
            _, out, _ = nas.exec_command(cmd, timeout=15)
            result = out.read().decode().strip()
            if "denied" in result.lower() or "permission" in result.lower():
                continue
            elif "timed out" in result.lower() or "refused" in result.lower():
                print(f"  Connection error: {result[:60]}")
                break
            elif "PW_OK" in result:
                print(f"  user={user}  pw={pw}")
                for line in result.split("\n"):
                    print(f"  {line}")
                found = True
                break
            time.sleep(0.3)
    if not found:
        print("  All passwords failed")
    print()

nas.close()
print("=== DONE ===")
