#!/usr/bin/env python3
"""Check server6 for IP conflict with 203.0.113.10."""
import paramiko

for ip in ["192.168.1.6", "192.168.1.106"]:
    try:
        j = paramiko.SSHClient()
        j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        j.connect(ip, username="admin", password="legacypass06", timeout=5)
        print(f"Connected to server6 at {ip}\n")

        cmds = [
            ("All IPs", "ip addr show"),
            ("Public IPs (140.113)", "ip addr | grep 140.113"),
            ("Routes to public", "ip route | grep 140.113"),
            ("Docker networks", "docker network ls 2>/dev/null"),
            ("Docker containers", "docker ps 2>/dev/null"),
            ("Docker macvlan", "docker network ls | grep -i wan 2>/dev/null"),
            ("iptables NAT", "sudo iptables -t nat -L -n 2>/dev/null | head -30"),
            ("netplan", "cat /etc/netplan/*.yaml 2>/dev/null"),
            ("interfaces", "cat /etc/network/interfaces 2>/dev/null"),
        ]

        for label, cmd in cmds:
            _, out, err = j.exec_command(cmd, timeout=5)
            result = out.read().decode().strip()
            if result:
                print(f"=== {label} ===")
                print(result)
                print()

        j.close()
        break
    except Exception as e:
        print(f"{ip}: {e}")
