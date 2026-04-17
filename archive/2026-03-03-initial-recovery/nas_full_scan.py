#!/usr/bin/env python3
"""Full scan from NAS: SSH port check + all passwords on ALL unknown IPs."""
import paramiko
import sys
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

# ALL IPs from Controller (excluding known: .6=srv6, .9=srv9, .29=NAS, .60=controller)
# Including student desktops .14/.21 and everything else
ALL_IPS = [
    "192.168.1.8",    # Port 7, ASUSTek, active traffic
    "192.168.1.14",   # server22 (student)
    "192.168.1.21",   # server21 (student)
    "192.168.1.43",   # ASUSTek
    "192.168.1.45",   # ASUSTek
    "192.168.1.46",   # ASUSTek (58:11:22)
    "192.168.1.49",   # unknown vendor, 91MB
    "192.168.1.50",   # MSI
    "192.168.1.53",   # ASUSTek (58:11:22)
    "192.168.1.54",   # ASUSTek
    "192.168.1.55",   # ASUSTek
    "192.168.1.56",   # ASUSTek
    "192.168.1.57",   # Advantech
    "192.168.1.58",   # 60:cf:84, 36MB
    "192.168.1.59",   # ASUSTek (58:11:22)
    "192.168.1.61",   # ASUSTek (58:11:22)
    "192.168.1.62",   # 60:cf:84
    "192.168.1.75",   # 60:cf:84, 10MB
    "192.168.1.76",   # ASUSTek
    "192.168.1.78",   # Compal (laptop?), 164MB
    "192.168.1.100",  # 60:cf:84, 43MB
    "192.168.1.102",  # 60:cf:84, server2
]

print("Connecting to NAS (192.168.1.29)...")
nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.29", username="admin", password="examplenaspass", timeout=10)
print("NAS connected.\n")

# Step 1: Check which IPs have SSH open (from NAS perspective)
print("=== Step 1: SSH port scan from NAS ===")
ssh_open = []
ssh_closed = []

for ip in ALL_IPS:
    octet = ip.split(".")[-1]
    cmd = f"bash -c '(echo >/dev/tcp/{ip}/22) 2>/dev/null && echo OPEN || echo CLOSED'"
    _, o, _ = nas.exec_command(cmd, timeout=5)
    result = o.read().decode().strip()
    if "OPEN" in result:
        ssh_open.append(ip)
        print(f"  .{octet:>3} SSH OPEN")
    else:
        ssh_closed.append(ip)
        print(f"  .{octet:>3} SSH closed")

print(f"\nSSH open: {len(ssh_open)} IPs: {[x.split('.')[-1] for x in ssh_open]}")
print(f"SSH closed: {len(ssh_closed)} IPs: {[x.split('.')[-1] for x in ssh_closed]}")

# Step 2: Try all passwords on all SSH-open IPs
print(f"\n=== Step 2: Password matrix ({len(PASSWORDS)} pw x {len(USERS)} users x {len(ssh_open)} IPs) ===")
print("=" * 70)

results = []

for ip in ssh_open:
    octet = ip.split(".")[-1]
    print(f"\n--- .{octet} ({ip}) ---")
    found = False

    for user in USERS:
        if found:
            break
        for pw, label in PASSWORDS:
            cmd = (
                f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no "
                f"-o ConnectTimeout=3 -o PreferredAuthentications=password "
                f"-o NumberOfPasswordPrompts=1 "
                f"{user}@{ip} hostname 2>&1"
            )
            try:
                _, o, _ = nas.exec_command(cmd, timeout=12)
                r = o.read().decode().strip()
            except Exception as e:
                r = f"EXEC_ERROR: {e}"

            is_error = any(x in r.lower() for x in [
                "denied", "permission", "error", "no route",
                "connection", "timeout", "usage:", "kex_exchange",
                "closed", "refused", "reset", "banner", "exec_error",
            ])

            if r and not is_error and len(r) < 100:
                # Gather detailed info
                info_cmd = (
                    f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no "
                    f"-o ConnectTimeout=5 -o PreferredAuthentications=password "
                    f"{user}@{ip} "
                    "'hostname; "
                    "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo NO_GPU; "
                    "lscpu 2>/dev/null | grep \"Model name\" | sed \"s/.*: *//\"; "
                    "ip link show 2>/dev/null | grep \"link/ether\" | head -1 | awk \"{print \\$2}\"; "
                    "free -h 2>/dev/null | grep Mem | awk \"{print \\$2}\"' 2>&1"
                )
                try:
                    _, o2, _ = nas.exec_command(info_cmd, timeout=15)
                    info = o2.read().decode().strip()
                except Exception:
                    info = "INFO_FETCH_FAILED"

                lines = info.split("\n")
                hostname = lines[0] if len(lines) > 0 else r
                gpu = lines[1] if len(lines) > 1 else "?"
                cpu = lines[2] if len(lines) > 2 else "?"
                mac = lines[3] if len(lines) > 3 else "?"
                mem = lines[4] if len(lines) > 4 else "?"

                print(f"  >>> MATCH! user={user}, pw={label} ({pw})")
                print(f"      hostname={hostname}, GPU={gpu}")
                print(f"      CPU={cpu}, MAC={mac}, MEM={mem}")
                results.append({
                    "ip": ip, "octet": octet, "user": user,
                    "pw_label": label, "pw": pw,
                    "hostname": hostname, "gpu": gpu, "cpu": cpu,
                    "mac": mac, "mem": mem,
                })
                found = True
                break

            time.sleep(0.1)

    if not found:
        print(f"  NO MATCH (all passwords failed)")

nas.close()

print("\n" + "=" * 70)
print(f"SUMMARY: {len(results)} servers identified out of {len(ssh_open)} SSH-open")
print("=" * 70)
for r in results:
    print(f"  .{r['octet']:>3} ({r['ip']}) = {r['hostname']}")
    print(f"       user={r['user']}  pw={r['pw_label']}")
    print(f"       GPU={r['gpu']}  CPU={r['cpu']}  MEM={r['mem']}")
    print(f"       MAC={r['mac']}")

print(f"\nSSH closed ({len(ssh_closed)}): {[x.split('.')[-1] for x in ssh_closed]}")
print("\n=== DONE ===")
