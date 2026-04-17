#!/usr/bin/env python3
"""Try examplepass password on all SSH-open IPs from NAS."""
import paramiko
import time

nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.29", username="admin", password="examplenaspass", timeout=10)
print("NAS connected. Trying examplepass...\n")

SSH_IPS = [
    "192.168.1.14", "192.168.1.21",
    "192.168.1.46", "192.168.1.49", "192.168.1.57",
    "192.168.1.100", "192.168.1.102",
]

PASSWORDS = ["examplepass", "Mllab708", "examplepass!", "Mllab708!", "examplepassexamplepass", "mllab912708"]
USERS = ["admin", "ops", "root"]

for ip in SSH_IPS:
    octet = ip.split(".")[-1]
    found = False
    for user in USERS:
        if found:
            break
        for pw in PASSWORDS:
            cmd = (
                f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no "
                f"-o ConnectTimeout=3 -o PreferredAuthentications=password "
                f"-o NumberOfPasswordPrompts=1 "
                f"{user}@{ip} hostname 2>&1"
            )
            try:
                _, o, _ = nas.exec_command(cmd, timeout=10)
                r = o.read().decode().strip()
            except:
                r = ""

            is_err = any(x in r.lower() for x in [
                "denied", "permission", "error", "connection",
                "timeout", "closed", "refused", "reset", "kex",
            ])

            if r and not is_err and len(r) < 80:
                # Get full info
                info_cmd = (
                    f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no "
                    f"-o ConnectTimeout=5 -o PreferredAuthentications=password "
                    f"{user}@{ip} "
                    "\"hostname; "
                    "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo NO_GPU; "
                    "lscpu 2>/dev/null | grep 'Model name' | sed 's/.*: *//'; "
                    "ip link show 2>/dev/null | grep 'link/ether' | head -1 | awk '{print \\$2}'; "
                    "free -h 2>/dev/null | grep Mem | awk '{print \\$2}'\" 2>&1"
                )
                _, o2, _ = nas.exec_command(info_cmd, timeout=15)
                info = o2.read().decode().strip()
                print(f".{octet} MATCH! user={user} pw={pw}")
                print(f"  {info}")
                found = True
                break
            time.sleep(0.1)

    if not found:
        print(f".{octet} no match")

nas.close()
print("\n=== DONE ===")
