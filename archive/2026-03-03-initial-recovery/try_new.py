#!/usr/bin/env python3
"""Try all passwords on new server8(.30) and server15(.31) from Pro6000."""
import paramiko
import time

j = paramiko.SSHClient()
j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
j.connect("192.168.1.100", username="ops", password="examplepass", timeout=5)
print("Pro6000 connected.\n")

TARGETS = ["192.168.1.30", "192.168.1.31"]
COMBOS = [
    ("ops", "examplepass"),
    ("admin", "examplepass"),
    ("admin", "legacypass07"),      # server8 old pw
    ("admin", "legacypass13"),     # server15 old pw
    ("admin", "legacypass06"),
    ("admin", "legacypass02"),
    ("admin", "legacypass03"),
    ("admin", "legacypass04"),
    ("admin", "legacypass05"),
    ("admin", "legacypass16"),
    ("admin", "legacypass08"),
    ("admin", "legacypass09"),
    ("admin", "legacypass10"),
    ("admin", "legacypass11"),
    ("admin", "legacypass12"),
    ("admin", "legacypass14"),
    ("admin", "legacypass15"),
    ("admin", "exampleswitchpass"),
    ("admin", "legacypass01"),
    ("admin", "examplenaspass"),
]

for tip in TARGETS:
    o = tip.split(".")[-1]
    print(f"--- .{o} ---")
    found = False
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
        try:
            _, out, _ = j.exec_command(cmd, timeout=12)
            r = out.read().decode().strip()
        except:
            r = ""
        is_err = any(x in r.lower() for x in ["denied","permission","error","connection","timeout","closed","refused","reset","kex"])
        if r and not is_err and len(r) < 300:
            print(f"  MATCH! {user}/{pw}")
            for line in r.split("\n"):
                print(f"    {line}")
            found = True
            break
        time.sleep(0.05)
    if not found:
        print(f"  all passwords failed")

j.close()
print("\n=== DONE ===")
