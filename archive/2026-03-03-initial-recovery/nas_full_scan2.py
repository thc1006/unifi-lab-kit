#!/usr/bin/env python3
"""Full scan from NAS v2: skip port scan, directly try sshpass on all IPs."""
import paramiko
import time

PASSWORDS = [
    ("legacypass01", "server1"),
    ("legacypass02", "server2"),
    ("legacypass03", "server3"),
    ("legacypass04", "server4"),
    ("legacypass05", "server5"),
    ("legacypass06", "server6"),
    ("legacypass16", "server7/14"),
    ("legacypass07", "server8"),
    ("legacypass08", "server9"),
    ("legacypass09", "server10"),
    ("legacypass10", "server11"),
    ("legacypass11", "server12"),
    ("legacypass12", "server13"),
    ("legacypass13", "server15"),
    ("legacypass14", "temp"),
    ("legacypass15", "temp2"),
    ("exampleswitchpass", "switch/router"),
    ("examplenaspass", "NAS"),
]

USERS = ["admin", "ops", "root"]

ALL_IPS = [
    "192.168.1.8", "192.168.1.14", "192.168.1.21",
    "192.168.1.43", "192.168.1.45", "192.168.1.46",
    "192.168.1.49", "192.168.1.50", "192.168.1.53",
    "192.168.1.54", "192.168.1.55", "192.168.1.56",
    "192.168.1.57", "192.168.1.58", "192.168.1.59",
    "192.168.1.61", "192.168.1.62", "192.168.1.75",
    "192.168.1.76", "192.168.1.78", "192.168.1.100",
    "192.168.1.102",
]

print("Connecting to NAS...")
nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.29", username="admin", password="examplenaspass", timeout=10)
print(f"NAS connected. Testing {len(ALL_IPS)} IPs x {len(PASSWORDS)} pw x {len(USERS)} users\n")

results = []

for ip in ALL_IPS:
    octet = ip.split(".")[-1]
    print(f"--- .{octet} ---", end=" ", flush=True)
    found = False

    for user in USERS:
        if found:
            break
        for pw, label in PASSWORDS:
            cmd = (
                f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no "
                f"-o ConnectTimeout=2 -o PreferredAuthentications=password "
                f"-o NumberOfPasswordPrompts=1 "
                f"{user}@{ip} hostname 2>&1"
            )
            try:
                _, o, _ = nas.exec_command(cmd, timeout=8)
                r = o.read().decode().strip()
            except Exception:
                r = ""

            is_error = any(x in r.lower() for x in [
                "denied", "permission", "error", "no route",
                "connection", "timeout", "usage:", "kex_exchange",
                "closed", "refused", "reset", "banner", "port 22",
            ])

            if r and not is_error and len(r) < 80:
                # Get detailed info
                info_cmd = (
                    f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no "
                    f"-o ConnectTimeout=5 -o PreferredAuthentications=password "
                    f"{user}@{ip} "
                    "\"hostname; "
                    "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo NO_GPU; "
                    "lscpu 2>/dev/null | grep 'Model name' | sed 's/.*: *//'; "
                    "free -h 2>/dev/null | grep Mem | awk '{print \\$2}'\" 2>&1"
                )
                try:
                    _, o2, _ = nas.exec_command(info_cmd, timeout=15)
                    info = o2.read().decode().strip()
                except Exception:
                    info = ""

                lines = info.split("\n") if info else []
                hostname = lines[0] if lines else r
                gpu = lines[1] if len(lines) > 1 else "?"
                cpu = lines[2] if len(lines) > 2 else "?"
                mem = lines[3] if len(lines) > 3 else "?"

                print(f"MATCH! {user}/{label} -> {hostname} GPU={gpu}")
                results.append({
                    "ip": ip, "user": user, "pw_label": label,
                    "hostname": hostname, "gpu": gpu, "cpu": cpu, "mem": mem,
                })
                found = True
                break

            time.sleep(0.05)

    if not found:
        # Quick check: is SSH even open? Use first password attempt result
        if "refused" in (r or "").lower() or "port 22" in (r or "").lower():
            print("SSH closed")
        elif "denied" in (r or "").lower():
            print("SSH open, all passwords failed")
        elif not r:
            print("no response / timeout")
        else:
            print(f"failed ({r[:40]})")

nas.close()

print("\n" + "=" * 70)
print(f"IDENTIFIED: {len(results)} servers")
print("=" * 70)
for r in results:
    print(f"  {r['ip']:>15} = {r['hostname']:<15} ({r['user']}/{r['pw_label']})")
    print(f"                   GPU={r['gpu']}  CPU={r['cpu']}  MEM={r['mem']}")

print("\n=== DONE ===")
