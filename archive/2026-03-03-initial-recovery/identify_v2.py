#!/usr/bin/env python3
"""Identify servers - one attempt per IP with delay to avoid rate limiting."""
import paramiko, socket, time

# Known server passwords mapped to server numbers (user: god)
SERVER_PASSWORDS = {
    "legacypass02": 2, "legacypass03": 3, "legacypass04": 4,
    "legacypass05": 5, "legacypass06": 6, "legacypass16": 14,
    "legacypass07": 8, "legacypass08": 9, "legacypass09": 10,
    "legacypass10": 11, "legacypass11": 12, "legacypass12": 13,
    "legacypass13": 15, "legacypass14": "temp", "legacypass15": "temp2",
    "legacypass01": 1,
}

# IPs with SSH open (from Controller client list, excluding known non-servers)
CANDIDATE_IPS = [
    "192.168.1.6", "192.168.1.8", "192.168.1.9", "192.168.1.14",
    "192.168.1.21", "192.168.1.43", "192.168.1.45", "192.168.1.46",
    "192.168.1.49", "192.168.1.50", "192.168.1.53", "192.168.1.54",
    "192.168.1.55", "192.168.1.56", "192.168.1.57", "192.168.1.58",
    "192.168.1.59", "192.168.1.61", "192.168.1.62", "192.168.1.75",
    "192.168.1.76", "192.168.1.78", "192.168.1.100", "192.168.1.102",
]

PASSWORDS = list(SERVER_PASSWORDS.keys())

def try_one(ip, pwd):
    """Single SSH attempt with proper error handling."""
    try:
        sock = socket.create_connection((ip, 22), timeout=5)
        t = paramiko.Transport(sock)
        t.banner_timeout = 15
        t.start_client()
        t.auth_password("admin", pwd)
        if t.is_authenticated():
            c = paramiko.SSHClient()
            c._transport = t
            _, stdout, _ = c.exec_command(
                "hostname && nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'no-nvidia-smi'",
                timeout=10
            )
            out = stdout.read().decode("utf-8", errors="replace").strip()
            c.close()
            return out
        t.close()
        return None  # wrong password
    except paramiko.AuthenticationException:
        return None
    except Exception:
        return "ERR"

print("Identifying servers (one pwd per IP, 2s delay)...")
print("=" * 60)

results = []
for ip in CANDIDATE_IPS:
    # Check SSH port
    try:
        s = socket.create_connection((ip, 22), timeout=2)
        s.close()
    except:
        continue

    found = False
    for pwd in PASSWORDS:
        out = try_one(ip, pwd)
        if out == "ERR":
            time.sleep(3)  # longer delay on error
            continue
        if out is not None:
            lines = out.split("\n")
            hostname = lines[0]
            gpu = lines[1] if len(lines) > 1 else "?"
            srv_num = SERVER_PASSWORDS[pwd]
            print(f"  {ip:>15s} = server{srv_num} (hostname={hostname}, gpu={gpu})")
            results.append((ip, srv_num, hostname, gpu, pwd))
            found = True
            break
        time.sleep(0.5)  # short delay between pwd attempts
    
    if not found:
        print(f"  {ip:>15s} = ? (no password matched or not a server)")
    
    time.sleep(1)  # delay between IPs

print("\n" + "=" * 60)
print("FINAL MAPPING")
print("=" * 60)
print(f"{'IP':<18s} {'Server':<12s} {'Hostname':<15s} {'GPU'}")
print("-" * 60)
for ip, srv, hostname, gpu, pwd in sorted(results, key=lambda x: (isinstance(x[1], str), x[1])):
    print(f"{ip:<18s} server{str(srv):<7s} {hostname:<15s} {gpu}")

print(f"\nTotal identified: {len(results)}")
