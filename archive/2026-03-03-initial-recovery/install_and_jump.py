#!/usr/bin/env python3
"""Install sshpass on accessible machines, then jump to targets."""
import paramiko
import time

HOSTS = [
    ("192.168.1.100", "ops", "examplepass", "Pro6000"),
    ("192.168.1.102", "ops", "examplepass", "server20"),
    ("192.168.1.14", "ops", "examplepass", "server22"),
    ("192.168.1.6", "admin", "legacypass06", "server6"),
]

TARGETS = ["192.168.1.21", "192.168.1.46", "192.168.1.49", "192.168.1.57"]

PASSWORDS = [
    ("ops", "examplepass"), ("admin", "examplepass"),
    ("admin", "legacypass06"), ("admin", "legacypass02"),
    ("admin", "legacypass03"), ("admin", "legacypass04"),
    ("admin", "legacypass05"), ("admin", "legacypass16"),
    ("admin", "legacypass07"), ("admin", "legacypass08"),
    ("admin", "legacypass09"), ("admin", "legacypass10"),
    ("admin", "legacypass11"), ("admin", "legacypass12"),
    ("admin", "legacypass13"), ("admin", "legacypass14"),
    ("admin", "legacypass15"), ("admin", "exampleswitchpass"),
    ("admin", "legacypass01"), ("admin", "examplenaspass"),
]

for jip, juser, jpw, jname in HOSTS:
    print(f"\n{'='*60}")
    print(f"{jname} ({jip}) - checking sudo + sshpass")
    print(f"{'='*60}")

    j = paramiko.SSHClient()
    j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        j.connect(jip, username=juser, password=jpw, timeout=5)
    except Exception as e:
        print(f"  Connect failed: {e}")
        continue

    # Check sudo
    _, o, e = j.exec_command(f"echo '{jpw}' | sudo -S whoami 2>&1", timeout=5)
    sudo_out = o.read().decode().strip()
    print(f"  sudo: {sudo_out}")

    if "root" in sudo_out:
        # Install sshpass
        _, o, _ = j.exec_command(f"echo '{jpw}' | sudo -S apt-get install -y sshpass 2>&1 | tail -3", timeout=30)
        install = o.read().decode().strip()
        print(f"  sshpass install: {install}")

        # Verify
        _, o, _ = j.exec_command("which sshpass 2>/dev/null", timeout=3)
        sp = o.read().decode().strip()
        if sp:
            print(f"  sshpass at: {sp}")
            # Now try all targets
            for tip in TARGETS:
                to = tip.split(".")[-1]
                found = False
                for user, pw in PASSWORDS:
                    cmd = (
                        f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no "
                        f"-o ConnectTimeout=2 -o PreferredAuthentications=password "
                        f"-o NumberOfPasswordPrompts=1 {user}@{tip} hostname 2>&1"
                    )
                    _, o, _ = j.exec_command(cmd, timeout=8)
                    r = o.read().decode().strip()
                    is_err = any(x in r.lower() for x in ["denied","permission","error","connection","timeout","closed","refused","reset","kex"])
                    if r and not is_err and len(r) < 80:
                        # Get info
                        _, o2, _ = j.exec_command(
                            f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no "
                            f"-o ConnectTimeout=5 -o PreferredAuthentications=password "
                            f"{user}@{tip} "
                            "\"hostname; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo NO_GPU; "
                            "lscpu | grep 'Model name' | sed 's/.*: *//'; "
                            "ip link show | grep 'link/ether' | head -1 | awk '{print \\$2}'; "
                            "free -h | grep Mem | awk '{print \\$2}'\" 2>&1", timeout=10)
                        info = o2.read().decode().strip()
                        print(f"  .{to} MATCH! {user}/{pw}")
                        for line in info.split("\n"):
                            print(f"    {line}")
                        found = True
                        break
                    time.sleep(0.05)
                if not found:
                    print(f"  .{to} all passwords failed")

            # Done with this jump host - found sshpass, tried all
            j.close()
            break  # No need to try other jump hosts
        else:
            print(f"  sshpass install failed")
    else:
        # No sudo - try key auth only
        for tip in TARGETS:
            to = tip.split(".")[-1]
            for user in ["admin", "ops", "root"]:
                cmd = f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=2 -o BatchMode=yes {user}@{tip} hostname 2>&1"
                _, o, _ = j.exec_command(cmd, timeout=8)
                r = o.read().decode().strip()
                is_err = any(x in r.lower() for x in ["denied","permission","error","connection","timeout","closed","refused","reset","kex"])
                if r and not is_err and len(r) < 80:
                    print(f"  .{to} KEY {user} -> {r}")
                    break

    j.close()

print(f"\n{'='*60}")
print("=== DONE ===")
