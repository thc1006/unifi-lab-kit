#!/usr/bin/env python3
"""Gather recon info from NAS: known_hosts, arp table, etc."""
import paramiko

print("Connecting to NAS...")
nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.29", username="admin", password="examplenaspass", timeout=10)
print("NAS connected.\n")

commands = [
    ("=== ARP table ===", "arp -a 2>/dev/null || ip neigh 2>/dev/null"),
    ("=== SSH known_hosts (god) ===", "cat ~/.ssh/known_hosts 2>/dev/null || echo '(empty)'"),
    ("=== SSH known_hosts (root) ===", "sudo cat /root/.ssh/known_hosts 2>/dev/null || echo '(empty)'"),
    ("=== SSH config (god) ===", "cat ~/.ssh/config 2>/dev/null || echo '(empty)'"),
    ("=== SSH authorized_keys (god) ===", "cat ~/.ssh/authorized_keys 2>/dev/null || echo '(empty)'"),
    ("=== /etc/hosts ===", "cat /etc/hosts 2>/dev/null"),
    ("=== bash_history SSH lines ===", "grep -i ssh ~/.bash_history 2>/dev/null | tail -30 || echo '(none)'"),
    ("=== Docker networks ===", "docker network ls 2>/dev/null && echo '---' && docker network inspect bridge 2>/dev/null | grep -A2 'IPv4' || echo '(no docker)'"),
    ("=== Last logins ===", "last -20 2>/dev/null || echo '(unavailable)'"),
    ("=== /etc/ethers or dnsmasq ===", "cat /etc/ethers 2>/dev/null; cat /etc/dnsmasq.conf 2>/dev/null | grep -v '^#' | grep . 2>/dev/null; echo '(done)'"),
    ("=== All users with shell ===", "grep -v nologin /etc/passwd | grep -v /bin/false 2>/dev/null"),
]

for title, cmd in commands:
    print(title)
    try:
        _, o, e = nas.exec_command(cmd, timeout=10)
        out = o.read().decode().strip()
        err = e.read().decode().strip()
        if out:
            print(out)
        if err:
            print(f"  (stderr: {err})")
    except Exception as ex:
        print(f"  ERROR: {ex}")
    print()

nas.close()
print("=== DONE ===")
