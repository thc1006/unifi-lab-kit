#!/usr/bin/env python3
"""Try server21 passwords via NAS jump host."""
import paramiko
import time

nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.129", username="admin", password="examplepass", timeout=5)
print("Connected to NAS\n")

IP = "192.168.1.121"
users = ["ops", "admin"]
passwords = [
    "examplepass",
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
]

found = False
for user in users:
    if found:
        break
    print(f"User: {user}")
    for pw in passwords:
        cmd = (
            f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no "
            f"-o ConnectTimeout=5 -o NumberOfPasswordPrompts=1 "
            f"{user}@{IP} 'hostname && hostname -I' 2>&1"
        )
        _, out, _ = nas.exec_command(cmd, timeout=12)
        result = out.read().decode().strip()
        if "denied" in result.lower() or "permission" in result.lower():
            print(f"  {pw:25s}  auth failed")
        elif "timed out" in result.lower() or "refused" in result.lower():
            print(f"  {pw:25s}  {result[:50]}")
            break
        else:
            print(f"  {pw:25s}  SUCCESS -> {result}")
            found = True
            break
        time.sleep(0.5)

if not found:
    print("\nAll combinations failed.")

nas.close()
print("\n=== DONE ===")
