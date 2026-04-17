#!/usr/bin/env python3
"""Try ALL passwords from server-0.csv on ALL IPs with multiple users. Maximum parallel."""
import paramiko
import socket
import concurrent.futures
import time

# All passwords from server-0.csv
ALL_PASSWORDS = [
    ("legacypass01", "srv1"),
    ("legacypass02", "srv2"),
    ("legacypass03", "srv3"),
    ("legacypass04", "srv4"),
    ("legacypass05", "srv5"),
    ("legacypass06", "srv6"),
    ("legacypass16", "srv7/14"),
    ("legacypass07", "srv8"),
    ("legacypass08", "srv9"),
    ("legacypass09", "srv10"),
    ("legacypass10", "srv11"),
    ("legacypass11", "srv12"),
    ("legacypass12", "srv13"),
    ("legacypass13", "srv15"),
    ("legacypass14", "srvtemp"),
    ("legacypass15", "srvtemp2"),
    ("examplenaspass", "NAS"),
    ("exampleswitchpass", "switch/router"),
    ("examplewifipass", "unifi-adopt"),
    ("exampleunifipass", "unifi-ctrl"),
    ("mllabasus", "asus-router"),
    ("mllab912_router", "asus-admin"),
]

USERS = ["admin", "ops", "root", "admin"]

# All IPs (exclude known: .6=server6, .29=NAS, .7=switch, .60=controller)
TARGET_IPS = [
    "192.168.1.8", "192.168.1.9", "192.168.1.14", "192.168.1.21",
    "192.168.1.43", "192.168.1.45", "192.168.1.46",
    "192.168.1.49", "192.168.1.50", "192.168.1.53",
    "192.168.1.54", "192.168.1.55", "192.168.1.56",
    "192.168.1.57", "192.168.1.58", "192.168.1.59",
    "192.168.1.61", "192.168.1.62", "192.168.1.75",
    "192.168.1.76", "192.168.1.78", "192.168.1.100",
    "192.168.1.102",
]

# First check which have SSH open
def check_ssh(ip):
    try:
        s = socket.create_connection((ip, 22), timeout=3)
        s.close()
        return ip
    except:
        return None

print("Checking SSH ports...")
with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
    ssh_open = [ip for ip in ex.map(check_ssh, TARGET_IPS) if ip]
print(f"SSH open: {ssh_open}\n")


def try_login(ip, user, passwd, label):
    try:
        sock = socket.create_connection((ip, 22), timeout=5)
        t = paramiko.Transport(sock)
        t.banner_timeout = 10
        t.start_client()
        t.auth_password(user, passwd)
        if t.is_authenticated():
            c = paramiko.SSHClient()
            c._transport = t
            _, o, _ = c.exec_command("hostname", timeout=5)
            hostname = o.read().decode().strip()
            _, o, _ = c.exec_command("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null", timeout=5)
            gpu = o.read().decode().strip() or "NO_GPU"
            _, o, _ = c.exec_command("lscpu | grep 'Model name' | sed 's/.*: *//'", timeout=5)
            cpu = o.read().decode().strip() or "?"
            _, o, _ = c.exec_command("free -h | grep Mem | awk '{print $2}'", timeout=5)
            mem = o.read().decode().strip() or "?"
            _, o, _ = c.exec_command("ip link show | grep 'link/ether' | head -1 | awk '{print $2}'", timeout=5)
            mac = o.read().decode().strip() or "?"
            c.close()
            return (ip, user, passwd, label, hostname, gpu, cpu, mem, mac)
        t.close()
    except:
        pass
    return None


results = []
print("Trying all user/password combinations on SSH-open IPs...")
print(f"  {len(ssh_open)} IPs x {len(USERS)} users x {len(ALL_PASSWORDS)} passwords = {len(ssh_open)*len(USERS)*len(ALL_PASSWORDS)} attempts")
print()

for ip in ssh_open:
    found = False
    for user in USERS:
        if found:
            break
        for passwd, label in ALL_PASSWORDS:
            r = try_login(ip, user, passwd, label)
            if r:
                ip, user, passwd, label, hostname, gpu, cpu, mem, mac = r
                print(f"  MATCH: {ip} -> {user}/{label}")
                print(f"    hostname={hostname}, GPU={gpu}")
                print(f"    CPU={cpu}, MEM={mem}, MAC={mac}")
                results.append(r)
                found = True
                break
            time.sleep(0.1)  # Small delay to avoid rate limiting
    if not found:
        print(f"  {ip}: NO MATCH (all passwords failed)")

print(f"\n{'='*60}")
print(f"FINAL RESULTS: {len(results)} servers identified")
print(f"{'='*60}")
for r in results:
    ip, user, passwd, label, hostname, gpu, cpu, mem, mac = r
    print(f"  {ip:>15} -> {hostname:<12} user={user} pwd_label={label}")
    print(f"                   GPU={gpu}, CPU={cpu}, MEM={mem}, MAC={mac}")

print("\n=== DONE ===")
