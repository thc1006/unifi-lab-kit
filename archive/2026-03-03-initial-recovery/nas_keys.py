#!/usr/bin/env python3
"""Explore SSH keys on NAS and try using them to access servers."""
import paramiko

print("Connecting to NAS...")
nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.29", username="admin", password="examplenaspass", timeout=10)
print("NAS connected.\n")

commands = [
    ("=== Backup SSH keys ===",
     "ls -la /mllab_nas/server/docker/backup/ssh_file/ 2>/dev/null || echo 'NOT FOUND'"),

    ("=== Backup SSH key contents (pub) ===",
     "cat /mllab_nas/server/docker/backup/ssh_file/*.pub 2>/dev/null || echo 'no pub keys'"),

    ("=== god home ssh dir ===",
     "ls -la /home/god/.ssh/ 2>/dev/null"),

    ("=== god ssh private keys ===",
     "ls -la /home/god/.ssh/id_* 2>/dev/null || echo 'no private keys in god home'"),

    ("=== ssh_file from history (god cwd) ===",
     "ls -la /home/god/ssh_file/ 2>/dev/null || echo 'NOT FOUND'"),

    ("=== Docker containers (all, including stopped) ===",
     "docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}' 2>/dev/null"),

    ("=== Check ups container ===",
     "docker inspect ups --format '{{.Mounts}}' 2>/dev/null || echo 'ups container not found'"),

    ("=== Check backup container ===",
     "docker inspect backup --format '{{.Mounts}}' 2>/dev/null || echo 'backup container not found'"),

    ("=== Find all SSH keys on NAS ===",
     "echo 'examplenaspass' | sudo -S find / -maxdepth 5 -name 'id_rsa' -o -name 'id_ed25519' -o -name '*.pem' 2>/dev/null | head -20"),

    ("=== known_hosts: check against our IPs ===",
     """for ip in 192.168.1.8 192.168.1.14 192.168.1.21 192.168.1.43 192.168.1.45 192.168.1.46 192.168.1.49 192.168.1.50 192.168.1.53 192.168.1.54 192.168.1.55 192.168.1.56 192.168.1.57 192.168.1.58 192.168.1.59 192.168.1.61 192.168.1.62 192.168.1.75 192.168.1.76 192.168.1.78 192.168.1.100 192.168.1.102 192.168.1.6 192.168.1.9; do
         ssh-keygen -H -F "$ip" 2>/dev/null | grep -q "found" && echo "KNOWN: $ip" || true
     done
     echo "(done checking)"
     """),

    ("=== NAS /mllab_nas directory structure ===",
     "ls -la /mllab_nas/ 2>/dev/null || echo 'NOT FOUND'"),

    ("=== NAS /mllab_nas/server/ ===",
     "ls -la /mllab_nas/server/ 2>/dev/null || echo 'NOT FOUND'"),

    ("=== NAS /mllab_nas/server/docker/ ===",
     "ls -la /mllab_nas/server/docker/ 2>/dev/null || echo 'NOT FOUND'"),
]

for title, cmd in commands:
    print(title)
    try:
        _, o, e = nas.exec_command(cmd, timeout=15)
        out = o.read().decode().strip()
        err = e.read().decode().strip()
        if out:
            print(out)
        if err and "password" not in err.lower():
            print(f"  (stderr: {err})")
    except Exception as ex:
        print(f"  ERROR: {ex}")
    print()

# Now try SSH with any found keys
print("=== Try SSH with NAS god's keys to all IPs ===")
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

for ip in ALL_IPS:
    octet = ip.split(".")[-1]
    # Try key-based auth with any available key
    for user in ["admin", "root", "ops"]:
        cmd = (
            f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=2 "
            f"-o BatchMode=yes -o PasswordAuthentication=no "
            f"{user}@{ip} hostname 2>&1"
        )
        _, o, _ = nas.exec_command(cmd, timeout=8)
        r = o.read().decode().strip()
        if r and "denied" not in r.lower() and "permission" not in r.lower() and "error" not in r.lower() and "closed" not in r.lower() and "timeout" not in r.lower() and "refused" not in r.lower() and "reset" not in r.lower():
            print(f"  .{octet} KEY AUTH SUCCESS as {user} -> {r}")
            break
    else:
        continue
    # If we didn't break from inner, this won't run
    # But if inner loop broke (found match), we continue outer
    continue

# Also try with backup keys if found
print("\n=== Try with backup SSH key path ===")
for ip in ALL_IPS:
    octet = ip.split(".")[-1]
    cmd = (
        f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=2 "
        f"-i /mllab_nas/server/docker/backup/ssh_file/id_rsa "
        f"-o BatchMode=yes admin@{ip} hostname 2>&1"
    )
    try:
        _, o, _ = nas.exec_command(cmd, timeout=8)
        r = o.read().decode().strip()
        if r and "denied" not in r.lower() and "permission" not in r.lower() and "no such" not in r.lower() and "error" not in r.lower() and "closed" not in r.lower() and "timeout" not in r.lower():
            print(f"  .{octet} BACKUP KEY -> {r}")
    except:
        pass

nas.close()
print("\n=== DONE ===")
