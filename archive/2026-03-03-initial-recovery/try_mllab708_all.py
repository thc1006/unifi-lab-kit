#!/usr/bin/env python3
"""Try mllab/examplepass on ALL IPs from NAS."""
import paramiko
import time

nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.29", username="admin", password="examplenaspass", timeout=10)
print("NAS connected. Trying mllab/examplepass on ALL IPs...\n")

# Every IP from Controller
ALL_IPS = [
    "192.168.1.6", "192.168.1.8", "192.168.1.9",
    "192.168.1.14", "192.168.1.21",
    "192.168.1.43", "192.168.1.45", "192.168.1.46",
    "192.168.1.49", "192.168.1.50", "192.168.1.53",
    "192.168.1.54", "192.168.1.55", "192.168.1.56",
    "192.168.1.57", "192.168.1.58", "192.168.1.59",
    "192.168.1.61", "192.168.1.62", "192.168.1.75",
    "192.168.1.76", "192.168.1.78", "192.168.1.100",
    "192.168.1.102",
]

PASSWORDS = ["examplepass", "Mllab708", "examplepass!"]
USERS = ["ops", "admin", "root"]

results = []

for ip in ALL_IPS:
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

                print(f".{octet:>3} MATCH! {user}/{pw} -> {hostname}")
                print(f"     GPU={gpu}  CPU={cpu}")
                print(f"     MAC={mac}  MEM={mem}")
                results.append({
                    "ip": ip, "octet": octet, "user": user, "pw": pw,
                    "hostname": hostname, "gpu": gpu, "cpu": cpu, "mac": mac, "mem": mem,
                })
                found = True
                break
            time.sleep(0.05)

    if not found:
        if "refused" in (r or "").lower():
            print(f".{octet:>3} SSH closed")
        elif "denied" in (r or "").lower():
            print(f".{octet:>3} examplepass failed")
        elif not r:
            print(f".{octet:>3} no response")
        else:
            print(f".{octet:>3} skip ({r[:30]})")

nas.close()

print(f"\n{'='*70}")
print(f"TOTAL IDENTIFIED: {len(results)}")
print(f"{'='*70}")
for r in results:
    print(f"  .{r['octet']:>3} = {r['hostname']:<20} ({r['user']}/{r['pw']})")
    print(f"       GPU={r['gpu']}")
    print(f"       CPU={r['cpu']}  MEM={r['mem']}  MAC={r['mac']}")

print("\n=== DONE ===")
