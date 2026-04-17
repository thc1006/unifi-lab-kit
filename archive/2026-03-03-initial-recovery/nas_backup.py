#!/usr/bin/env python3
"""Check NAS backup dir and scan non-SSH ports for web interfaces."""
import paramiko

print("Connecting to NAS...")
nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.29", username="admin", password="examplenaspass", timeout=10)
print("NAS connected.\n")

commands = [
    ("=== /mllab_nas/server/backup/ contents ===",
     "ls -la /mllab_nas/server/backup/ 2>/dev/null"),

    ("=== Backup subdirectories ===",
     "find /mllab_nas/server/backup/ -maxdepth 2 -type d 2>/dev/null | head -30"),

    ("=== Any SSH config in backups ===",
     "find /mllab_nas/server/backup/ -name 'sshd_config' -o -name 'authorized_keys' -o -name '*.conf' 2>/dev/null | head -20"),

    ("=== NAS docker wan/nat54 network details ===",
     "docker network inspect wan 2>/dev/null | head -40; echo '---'; docker network inspect nat54 2>/dev/null | head -40"),

    ("=== Check wan32nginx config (might have server IPs) ===",
     "cat /mllab_nas/server/docker/wan32nginx/nginx.conf 2>/dev/null || find /mllab_nas/server/docker/wan32nginx/ -name '*.conf' -exec cat {} \\; 2>/dev/null | head -50"),

    ("=== god known_hosts decoded (try unhash) ===",
     "ssh-keygen -l -f /home/god/.ssh/known_hosts 2>/dev/null"),
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

# Scan common non-SSH ports on timeout IPs (these have SSH blocked but might have web)
print("=== Port scan: HTTP/HTTPS/RDP on SSH-timeout IPs ===")
timeout_ips = ["192.168.1.8", "192.168.1.50", "192.168.1.53", "192.168.1.54",
               "192.168.1.58", "192.168.1.59", "192.168.1.61", "192.168.1.62",
               "192.168.1.75", "192.168.1.78"]
ports = [80, 443, 3389, 8080, 8443, 9090]

for ip in timeout_ips:
    octet = ip.split(".")[-1]
    open_ports = []
    for port in ports:
        cmd = f"bash -c '(echo >/dev/tcp/{ip}/{port}) 2>/dev/null && echo OPEN || echo CLOSED'"
        try:
            _, o, _ = nas.exec_command(cmd, timeout=4)
            r = o.read().decode().strip()
            if "OPEN" in r:
                open_ports.append(port)
        except:
            pass
    if open_ports:
        print(f"  .{octet}: ports {open_ports}")
    else:
        print(f"  .{octet}: all checked ports closed")

# Also check SSH-open IPs for extra ports
print("\n=== Extra ports on SSH-open IPs ===")
ssh_ips = ["192.168.1.46", "192.168.1.49", "192.168.1.57",
           "192.168.1.100", "192.168.1.102"]
for ip in ssh_ips:
    octet = ip.split(".")[-1]
    open_ports = [22]  # already known
    for port in ports:
        cmd = f"bash -c '(echo >/dev/tcp/{ip}/{port}) 2>/dev/null && echo OPEN || echo CLOSED'"
        try:
            _, o, _ = nas.exec_command(cmd, timeout=4)
            r = o.read().decode().strip()
            if "OPEN" in r:
                open_ports.append(port)
        except:
            pass
    print(f"  .{octet}: ports {open_ports}")

nas.close()
print("\n=== DONE ===")
