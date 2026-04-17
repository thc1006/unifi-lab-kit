#!/usr/bin/env python3
"""Test NEW IPs (never tested from laptop before, so no fail2ban)."""
import paramiko
import socket
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

# IPs from Controller that we NEVER tried from laptop (no fail2ban risk)
NEW_IPS = [
    "192.168.1.8",
    "192.168.1.43",
    "192.168.1.45",
    "192.168.1.50",
    "192.168.1.53",
    "192.168.1.54",
    "192.168.1.55",
    "192.168.1.56",
    "192.168.1.58",
    "192.168.1.59",
    "192.168.1.61",
    "192.168.1.62",
    "192.168.1.75",
    "192.168.1.76",
]

print(f"Local laptop scan: {len(NEW_IPS)} new IPs (never tested, no ban risk)")
print("=" * 70)

results = []

for ip in NEW_IPS:
    octet = ip.split(".")[-1]
    # First check if SSH is open
    try:
        sock = socket.create_connection((ip, 22), timeout=2)
        banner = sock.recv(256).decode(errors="ignore").strip()
        sock.close()
        print(f"\n--- .{octet} ({ip}) SSH OPEN: {banner} ---")
    except socket.timeout:
        print(f"\n--- .{octet} ({ip}) SSH timeout ---")
        continue
    except ConnectionRefusedError:
        print(f"\n--- .{octet} ({ip}) SSH refused ---")
        continue
    except Exception as e:
        print(f"\n--- .{octet} ({ip}) error: {e} ---")
        continue

    # SSH is open, try passwords
    found = False
    for user in USERS:
        if found:
            break
        for pw, label in PASSWORDS:
            try:
                sock = socket.create_connection((ip, 22), timeout=3)
                t = paramiko.Transport(sock)
                t.banner_timeout = 8
                t.start_client()
                t.auth_password(user, pw)
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
                    _, o, _ = c.exec_command("free -h | grep Mem | awk '{print $2}'", timeout=5)
                    mem = o.read().decode().strip()
                    c.close()
                    print(f"  >>> MATCH! user={user}, pw={label}")
                    print(f"      hostname={hostname}, GPU={gpu}, CPU={cpu}, MAC={mac}, MEM={mem}")
                    results.append((ip, octet, user, label, hostname, gpu, cpu, mac, mem))
                    found = True
                    break
                t.close()
            except paramiko.AuthenticationException:
                pass
            except Exception as e:
                err = str(e)
                if "banner" in err.lower():
                    print(f"  RATE LIMITED at user={user}/pw={label}, skipping IP")
                    found = True  # stop trying this IP
                    break
            time.sleep(0.2)

    if not found:
        print(f"  NO MATCH")

print("\n" + "=" * 70)
print(f"LOCAL RESULTS: {len(results)} identified")
print("=" * 70)
for ip, octet, user, label, hostname, gpu, cpu, mac, mem in results:
    print(f"  .{octet} = {hostname} (user={user}, pw={label}) GPU={gpu} CPU={cpu} MEM={mem}")

print("\n=== DONE ===")
