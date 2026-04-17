#!/usr/bin/env python3
"""Identify all GPU servers by SSH-ing in and checking hostname + GPU."""
import paramiko
import socket

# Server IPs that could be GPU servers (exclude known: .7=switch, .29=nas, .60=controller)
# From Controller client list, focusing on likely servers
CANDIDATE_IPS = [
    "192.168.1.6",    # confirmed server6
    "192.168.1.8",
    "192.168.1.9",
    "192.168.1.14",
    "192.168.1.21",
    "192.168.1.43",
    "192.168.1.45",
    "192.168.1.46",
    "192.168.1.49",
    "192.168.1.50",
    "192.168.1.53",
    "192.168.1.54",
    "192.168.1.55",
    "192.168.1.56",
    "192.168.1.57",
    "192.168.1.58",
    "192.168.1.59",
    "192.168.1.61",
    "192.168.1.62",
    "192.168.1.75",
    "192.168.1.76",
    "192.168.1.78",
    "192.168.1.100",
    "192.168.1.102",  # confirmed server2
]

# All server passwords from server-0.csv (user: god)
PASSWORDS = [
    "legacypass01",      # server1
    "legacypass02",    # server2
    "legacypass03",    # server3
    "legacypass04",     # server4
    "legacypass05",     # server5
    "legacypass06",   # server6
    "legacypass16",    # server7/14
    "legacypass07",     # server8
    "legacypass08",      # server9
    "legacypass09",    # server10
    "legacypass10",    # server11
    "legacypass11",       # server12
    "legacypass12",    # server13
    "legacypass13",    # server15
    "legacypass14",  # temp
    "legacypass15", # temp2
]


def try_ssh(ip, user, password, cmd, timeout=8):
    try:
        sock = socket.create_connection((ip, 22), timeout=5)
        t = paramiko.Transport(sock)
        t.banner_timeout = 15
        t.start_client()
        t.auth_password(user, password)
        if t.is_authenticated():
            c = paramiko.SSHClient()
            c._transport = t
            _, stdout, _ = c.exec_command(cmd, timeout=timeout)
            out = stdout.read().decode("utf-8", errors="replace").strip()
            c.close()
            return out
        t.close()
    except paramiko.AuthenticationException:
        return None
    except Exception as e:
        return f"[ERR:{type(e).__name__}]"
    return None


print("=" * 70)
print("Server Identification - SSH into each IP and check hostname + GPU")
print("=" * 70)

identified = []

for ip in CANDIDATE_IPS:
    # First check if SSH port is open
    try:
        s = socket.create_connection((ip, 22), timeout=3)
        s.close()
    except:
        continue
    
    print(f"\n--- {ip} ---")
    
    # Try each password with user 'admin'
    for pwd in PASSWORDS:
        result = try_ssh(ip, "admin", pwd, "hostname && nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'no-gpu-cmd'")
        if result and not result.startswith("[ERR"):
            lines = result.split("\n")
            hostname = lines[0] if lines else "?"
            gpu = lines[1] if len(lines) > 1 else "?"
            print(f"  User: god, Pass: {pwd}")
            print(f"  Hostname: {hostname}")
            print(f"  GPU: {gpu}")
            identified.append({
                "ip": ip, "hostname": hostname, "gpu": gpu,
                "password": pwd, "mac": ""
            })
            break
    else:
        # Try with other users too
        for user in ["ops", "ubnt"]:
            for pwd in ["examplenaspass", "exampleswitchpass"]:
                result = try_ssh(ip, user, pwd, "hostname 2>/dev/null || echo unknown")
                if result and not result.startswith("[ERR"):
                    print(f"  User: {user}, Pass: {pwd}")
                    print(f"  Hostname: {result}")
                    identified.append({
                        "ip": ip, "hostname": result, "user": user,
                        "password": pwd
                    })
                    break
            else:
                continue
            break
        else:
            print(f"  No password worked")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
for s in identified:
    print(f"  {s['ip']:>15s} = {s['hostname']:<15s} GPU: {s.get('gpu', '?')}")

print(f"\nIdentified: {len(identified)} / {len(CANDIDATE_IPS)} candidates")
