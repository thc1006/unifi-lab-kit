#!/usr/bin/env python3
"""Try legacypass07 on .21/.46/.49/.57 from Pro6000 (has sshpass+sudo)."""
import paramiko

j = paramiko.SSHClient()
j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
j.connect("192.168.1.100", username="ops", password="examplepass", timeout=5)
print("Pro6000 connected.\n")

TARGETS = ["192.168.1.21", "192.168.1.46", "192.168.1.49", "192.168.1.57"]
# Try both old and new user with this password
COMBOS = [
    ("admin", "legacypass07"),
    ("ops", "legacypass07"),
]

for tip in TARGETS:
    o = tip.split(".")[-1]
    for user, pw in COMBOS:
        cmd = (
            f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no "
            f"-o ConnectTimeout=3 -o PreferredAuthentications=password "
            f"-o NumberOfPasswordPrompts=1 {user}@{tip} "
            "\"hostname; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo NO_GPU; "
            "lscpu | grep 'Model name' | sed 's/.*: *//'; "
            "ip link show | grep 'link/ether' | head -1 | awk '{print \\$2}'; "
            "free -h | grep Mem | awk '{print \\$2}'\" 2>&1"
        )
        _, out, _ = j.exec_command(cmd, timeout=12)
        r = out.read().decode().strip()
        is_err = any(x in r.lower() for x in ["denied","permission","error","connection","timeout","closed","refused","reset","kex"])
        if r and not is_err:
            print(f".{o} MATCH! {user}/{pw}")
            for line in r.split("\n"):
                print(f"  {line}")
            break
        else:
            print(f".{o} {user}/{pw} -> failed")

j.close()
print("\n=== DONE ===")
