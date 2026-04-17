#!/usr/bin/env python3
"""Try every server password on every SSH-open IP. Full matrix."""
import paramiko
import socket
import time

# All server passwords from server-0.csv (user confirmed these)
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
]

# SSH-open IPs (excluding .6=server6, .29=NAS, .14/.21=student desktops)
SSH_IPS = [
    "192.168.1.46",
    "192.168.1.49",
    "192.168.1.57",
    "192.168.1.100",
    "192.168.1.102",
]

print(f"Full matrix: {len(PASSWORDS)} passwords x {len(SSH_IPS)} IPs = {len(PASSWORDS)*len(SSH_IPS)} attempts")
print("=" * 60)

results = []

for ip in SSH_IPS:
    print(f"\n--- {ip} ---")
    found = False
    for pw, label in PASSWORDS:
        try:
            sock = socket.create_connection((ip, 22), timeout=3)
            t = paramiko.Transport(sock)
            t.banner_timeout = 8
            t.start_client()
            t.auth_password("admin", pw)
            if t.is_authenticated():
                c = paramiko.SSHClient()
                c._transport = t
                _, o, _ = c.exec_command("hostname", timeout=5)
                hostname = o.read().decode().strip()
                _, o, _ = c.exec_command(
                    "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo NO_GPU",
                    timeout=5,
                )
                gpu = o.read().decode().strip()
                _, o, _ = c.exec_command("lscpu | grep 'Model name' | sed 's/.*: *//'", timeout=5)
                cpu = o.read().decode().strip()
                _, o, _ = c.exec_command("ip link show | grep 'link/ether' | head -1 | awk '{print $2}'", timeout=5)
                mac = o.read().decode().strip()
                c.close()
                print(f"  MATCH! pw={label} ({pw})")
                print(f"    hostname={hostname}, GPU={gpu}, CPU={cpu}, MAC={mac}")
                results.append((ip, label, hostname, gpu, cpu, mac))
                found = True
                break
            t.close()
        except paramiko.AuthenticationException:
            pass  # wrong password, try next
        except Exception as e:
            err = str(e)
            if "banner" in err.lower():
                print(f"  RATE LIMITED at pw={label}, stopping this IP")
                break
            # other error, continue
        time.sleep(0.3)

    if not found:
        print(f"  NO MATCH (all 16 passwords failed)")

print("\n" + "=" * 60)
print(f"RESULTS: {len(results)} identified")
print("=" * 60)
for ip, label, hostname, gpu, cpu, mac in results:
    print(f"  {ip:>15} = {hostname:<12} (pwd={label}) GPU={gpu} CPU={cpu}")

print("\n=== DONE ===")
