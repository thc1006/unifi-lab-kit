#!/usr/bin/env python3
"""Smart identification: try each password on known SSH-capable IPs, one at a time."""
import paramiko, socket, time, sys

# IPs that have SSH open and are likely servers (exclude known)
# Skip: .7=switch, .29=nas, .60=controller, .9=server9, .6=server6, .102=server2
# Skip: .14=server22(desktop), .21=server21(desktop), .78=Compal(laptop)
SSH_IPS = [
    "192.168.1.8", "192.168.1.43", "192.168.1.45", "192.168.1.46",
    "192.168.1.49", "192.168.1.50", "192.168.1.53", "192.168.1.54",
    "192.168.1.55", "192.168.1.56", "192.168.1.57", "192.168.1.58",
    "192.168.1.59", "192.168.1.61", "192.168.1.62", "192.168.1.75",
    "192.168.1.76", "192.168.1.100",
]

# Passwords to try (one at a time across all IPs)
PWDS = [
    ("legacypass03", 3), ("legacypass04", 4), ("legacypass05", 5),
    ("legacypass16", 14), ("legacypass07", 8),
    ("legacypass09", 10), ("legacypass10", 11), ("legacypass11", 12),
    ("legacypass12", 13), ("legacypass13", 15),
    ("legacypass01", 1),
]

def ssh_check(ip, pwd):
    try:
        sock = socket.create_connection((ip, 22), timeout=4)
        t = paramiko.Transport(sock)
        t.banner_timeout = 10
        t.start_client()
        t.auth_password("admin", pwd)
        if t.is_authenticated():
            c = paramiko.SSHClient()
            c._transport = t
            _, stdout, _ = c.exec_command("hostname", timeout=5)
            hostname = stdout.read().decode().strip()
            c.close()
            return hostname
        t.close()
    except paramiko.AuthenticationException:
        pass
    except:
        return "ERR"
    return None

# First check which IPs have SSH open
print("Checking SSH ports...")
ssh_open = []
for ip in SSH_IPS:
    try:
        s = socket.create_connection((ip, 22), timeout=2)
        s.close()
        ssh_open.append(ip)
        sys.stdout.write(f"  {ip} OPEN\n")
    except:
        pass
    sys.stdout.flush()

print(f"\n{len(ssh_open)} IPs with SSH open")
print("=" * 50)

# For each password, try ALL IPs (one attempt each)
found = {}
remaining_ips = set(ssh_open)

for pwd, srv_num in PWDS:
    if not remaining_ips:
        break
    print(f"\nTrying password for server{srv_num}...")
    for ip in list(remaining_ips):
        sys.stdout.write(f"  {ip}... ")
        sys.stdout.flush()
        result = ssh_check(ip, pwd)
        if result == "ERR":
            print("connection error")
            time.sleep(2)
        elif result is not None:
            print(f"MATCH! hostname={result}")
            found[ip] = (srv_num, result, pwd)
            remaining_ips.discard(ip)
            break
        else:
            print("no")
        time.sleep(0.3)

print("\n" + "=" * 50)
print("RESULTS")
print("=" * 50)
# Add previously known
known = {
    "192.168.1.6": (6, "server6", "legacypass06"),
    "192.168.1.9": (9, "server9", "legacypass08"),
    "192.168.1.102": (2, "server2", "legacypass02"),
}
found.update(known)

for ip in sorted(found.keys(), key=lambda x: found[x][0]):
    srv_num, hostname, pwd = found[ip]
    print(f"  {ip:>15s} -> server{srv_num:<5} (hostname: {hostname})")

print(f"\nTotal: {len(found)} servers identified")
