#!/usr/bin/env python3
"""Try mllab user with all passwords on unknown devices."""
import paramiko
import time

nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.129", username="admin", password="examplepass", timeout=5)
print("Connected to NAS\n")

devices = [
    "192.168.1.121",
    "192.168.1.200",
    "192.168.1.205",
    "192.168.1.206",
    "192.168.1.215",
]

passwords = [
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
    "examplenaspass",
    "exampleswitchpass",
    "exampleunifipass",
    "mllab912_router",
    "mllabasus",
    "ops",
    "mllab912",
    "mllabjtc",
    "Mllabjtc912",
    "examplepassmllab",
    "examplepass!",
    "MLLAB708",
]

for ip in devices:
    print(f"=== {ip} (user=mllab) ===")
    found = False
    for pw in passwords:
        cmd = (
            f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no "
            f"-o ConnectTimeout=5 -o NumberOfPasswordPrompts=1 "
            f"mllab@{ip} "
            f"'echo SUCCESS; hostname; hostname -I; "
            f"nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo NO-GPU; "
            f"ip link show | grep \"link/ether\" | head -1 | awk \"{{print \\$2}}\"' 2>&1"
        )
        _, out, _ = nas.exec_command(cmd, timeout=15)
        result = out.read().decode().strip()
        if "SUCCESS" in result:
            print(f"  PASSWORD FOUND: {pw}")
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
