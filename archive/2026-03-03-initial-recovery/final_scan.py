#!/usr/bin/env python3
"""All passwords (old + new) on all SSH-open IPs via NAS."""
import paramiko
import time

PASSWORDS = [
    ("ops", "examplepass"),
    ("admin", "examplepass"),
    ("admin", "legacypass01"),
    ("admin", "legacypass02"),
    ("admin", "legacypass03"),
    ("admin", "legacypass04"),
    ("admin", "legacypass05"),
    ("admin", "legacypass06"),
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
    ("admin", "examplenaspass"),
    ("ops", "Mllab708"),
    ("ops", "examplepass!"),
    ("root", "examplepass"),
    ("root", "Mllab708"),
]

SSH_OPEN = [
    "192.168.1.6",
    "192.168.1.14",
    "192.168.1.21",
    "192.168.1.46",
    "192.168.1.49",
    "192.168.1.57",
    "192.168.1.100",
    "192.168.1.102",
]

nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.29", username="admin", password="examplenaspass", timeout=10)
print(f"NAS connected. {len(PASSWORDS)} combos x {len(SSH_OPEN)} IPs\n")

results = []

for ip in SSH_OPEN:
    o = ip.split(".")[-1]
    print(f".{o:>3} ", end="", flush=True)
    found = False
    for user, pw in PASSWORDS:
        cmd = (
            f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no "
            f"-o ConnectTimeout=2 -o PreferredAuthentications=password "
            f"-o NumberOfPasswordPrompts=1 "
            f"{user}@{ip} hostname 2>&1"
        )
        try:
            _, out, _ = nas.exec_command(cmd, timeout=8)
            r = out.read().decode().strip()
        except:
            r = ""
        is_err = any(x in r.lower() for x in [
            "denied", "permission", "error", "connection",
            "timeout", "closed", "refused", "reset", "kex",
        ])
        if r and not is_err and len(r) < 80:
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
            lines = info.split("\n")
            hostname = lines[0] if lines else r
            gpu = lines[1] if len(lines) > 1 else "?"
            cpu = lines[2] if len(lines) > 2 else "?"
            mac = lines[3] if len(lines) > 3 else "?"
            mem = lines[4] if len(lines) > 4 else "?"
            print(f"MATCH {user}/{pw} -> {hostname} | GPU={gpu} | CPU={cpu} | MAC={mac} | MEM={mem}")
            results.append(dict(ip=ip, user=user, pw=pw, hostname=hostname, gpu=gpu, cpu=cpu, mac=mac, mem=mem))
            found = True
            break
        time.sleep(0.05)
    if not found:
        print("NO MATCH")

nas.close()
print(f"\n{'='*70}")
print(f"IDENTIFIED: {len(results)}/{len(SSH_OPEN)}")
print(f"{'='*70}")
for r in results:
    print(f"  {r['ip']:>15} = {r['hostname']:<20} {r['user']}/{r['pw']}")
    print(f"                   GPU={r['gpu']}")
    print(f"                   CPU={r['cpu']}  MEM={r['mem']}  MAC={r['mac']}")
print("\n=== DONE ===")
