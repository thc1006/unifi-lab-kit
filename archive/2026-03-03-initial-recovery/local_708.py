#!/usr/bin/env python3
"""Fast: try mllab/examplepass from laptop on all IPs."""
import paramiko
import socket

ALL_IPS = [
    "192.168.1.6", "192.168.1.8", "192.168.1.9",
    "192.168.1.14", "192.168.1.21",
    "192.168.1.43", "192.168.1.45", "192.168.1.46",
    "192.168.1.49", "192.168.1.50", "192.168.1.53",
    "192.168.1.54", "192.168.1.55", "192.168.1.56",
    "192.168.1.57", "192.168.1.58", "192.168.1.59",
    "192.168.1.61", "192.168.1.62", "192.168.1.75",
    "192.168.1.76", "192.168.1.78", "192.168.1.100",
    "192.168.1.102",
]

for ip in ALL_IPS:
    o = ip.split(".")[-1]
    try:
        s = socket.create_connection((ip, 22), timeout=1)
        s.close()
    except:
        print(f".{o:>3} no SSH")
        continue

    # SSH open - try mllab/examplepass
    try:
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(ip, username="ops", password="examplepass", timeout=3, banner_timeout=5)
        _, out, _ = c.exec_command("hostname; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo NO_GPU; lscpu | grep 'Model name' | sed 's/.*: *//'; free -h | grep Mem | awk '{print $2}'", timeout=8)
        info = out.read().decode().strip()
        c.close()
        print(f".{o:>3} MATCH! {info}")
    except paramiko.AuthenticationException:
        print(f".{o:>3} examplepass denied")
    except Exception as e:
        err = str(e)[:40]
        print(f".{o:>3} err: {err}")
