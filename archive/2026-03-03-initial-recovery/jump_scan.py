#!/usr/bin/env python3
"""Jump from each logged-in machine to scan .21/.46/.49/.57"""
import paramiko
import time

JUMP_HOSTS = [
    ("192.168.1.6", "admin", "legacypass06", "server6"),
    ("192.168.1.14", "ops", "examplepass", "server22"),
    ("192.168.1.100", "ops", "examplepass", "Pro6000"),
    ("192.168.1.102", "ops", "examplepass", "server20"),
    ("192.168.1.29", "admin", "examplenaspass", "NAS"),
]

TARGETS = ["192.168.1.21", "192.168.1.46", "192.168.1.49", "192.168.1.57"]

PASSWORDS = [
    ("ops", "examplepass"),
    ("admin", "examplepass"),
    ("admin", "legacypass06"),
    ("admin", "legacypass02"),
    ("admin", "legacypass03"),
    ("admin", "legacypass04"),
    ("admin", "legacypass05"),
    ("admin", "legacypass16"),
    ("admin", "legacypass07"),
    ("admin", "legacypass08"),
    ("admin", "legacypass09"),
    ("admin", "legacypass10"),
    ("admin", "legacypass11"),
    ("admin", "legacypass12"),
    ("admin", "legacypass13"),
    ("admin", "legacypass14"),
    ("admin", "legacypass15"),
    ("admin", "exampleswitchpass"),
    ("admin", "legacypass01"),
    ("admin", "examplenaspass"),
]

for jip, juser, jpw, jname in JUMP_HOSTS:
    print(f"\n{'='*60}")
    print(f"JUMP HOST: {jname} ({jip})")
    print(f"{'='*60}")
    try:
        j = paramiko.SSHClient()
        j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        j.connect(jip, username=juser, password=jpw, timeout=5)
    except Exception as e:
        print(f"  FAILED to connect: {e}")
        continue

    # Check what SSH keys this host has
    _, o, _ = j.exec_command("ls -la ~/.ssh/id_* 2>/dev/null; cat ~/.ssh/authorized_keys 2>/dev/null | wc -l", timeout=5)
    keys = o.read().decode().strip()
    print(f"  SSH keys: {keys}")

    # Check known_hosts
    for tip in TARGETS:
        to = tip.split(".")[-1]
        _, o, _ = j.exec_command(f"ssh-keygen -H -F {tip} 2>/dev/null | head -1", timeout=3)
        kh = o.read().decode().strip()
        if kh:
            print(f"  known_hosts has .{to}")

    # Check if sshpass exists
    _, o, _ = j.exec_command("which sshpass 2>/dev/null", timeout=3)
    has_sshpass = o.read().decode().strip()

    for tip in TARGETS:
        to = tip.split(".")[-1]
        print(f"\n  --- .{to} from {jname} ---")

        # 1) Try key-based auth first
        for user in ["admin", "ops", "root"]:
            cmd = (
                f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=2 "
                f"-o BatchMode=yes {user}@{tip} hostname 2>&1"
            )
            _, o, _ = j.exec_command(cmd, timeout=8)
            r = o.read().decode().strip()
            is_err = any(x in r.lower() for x in ["denied","permission","error","connection","timeout","closed","refused","reset","kex"])
            if r and not is_err and len(r) < 80:
                print(f"    KEY AUTH {user} -> {r}")
                # Get full info
                _, o2, _ = j.exec_command(
                    f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 -o BatchMode=yes {user}@{tip} "
                    "\"hostname; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo NO_GPU; "
                    "lscpu | grep 'Model name' | sed 's/.*: *//'; "
                    "ip link show | grep 'link/ether' | head -1 | awk '{print \\$2}'; "
                    "free -h | grep Mem | awk '{print \\$2}'\" 2>&1", timeout=10)
                info = o2.read().decode().strip()
                print(f"    INFO: {info}")
                break

        # 2) Try password auth via sshpass if available
        if has_sshpass:
            found = False
            for user, pw in PASSWORDS:
                if found:
                    break
                cmd = (
                    f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no "
                    f"-o ConnectTimeout=2 -o PreferredAuthentications=password "
                    f"-o NumberOfPasswordPrompts=1 {user}@{tip} hostname 2>&1"
                )
                _, o, _ = j.exec_command(cmd, timeout=8)
                r = o.read().decode().strip()
                is_err = any(x in r.lower() for x in ["denied","permission","error","connection","timeout","closed","refused","reset","kex"])
                if r and not is_err and len(r) < 80:
                    print(f"    SSHPASS {user}/{pw} -> {r}")
                    _, o2, _ = j.exec_command(
                        f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no "
                        f"-o ConnectTimeout=3 -o PreferredAuthentications=password "
                        f"{user}@{tip} "
                        "\"hostname; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo NO_GPU; "
                        "lscpu | grep 'Model name' | sed 's/.*: *//'; "
                        "ip link show | grep 'link/ether' | head -1 | awk '{print \\$2}'; "
                        "free -h | grep Mem | awk '{print \\$2}'\" 2>&1", timeout=10)
                    info = o2.read().decode().strip()
                    print(f"    INFO: {info}")
                    found = True
                time.sleep(0.05)
            if not found:
                print(f"    sshpass: all passwords failed")
        else:
            print(f"    (no sshpass on {jname})")

    j.close()

print(f"\n{'='*60}")
print("=== DONE ===")
