#!/usr/bin/env python3
"""Check IP conflict - who has 203.0.113.10?"""
import paramiko
import socket

# Quick port scan to find reachable servers
print("=== Quick connectivity check ===")
for ip in ["192.168.1.6", "192.168.1.106", "192.168.1.29", "192.168.1.129",
           "192.168.1.14", "192.168.1.100", "192.168.1.102",
           "192.168.1.122", "192.168.1.123", "192.168.1.120"]:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((ip, 22))
        sock.close()
        if result == 0:
            print(f"  {ip:>15}  SSH OPEN")
        else:
            print(f"  {ip:>15}  closed")
    except:
        print(f"  {ip:>15}  timeout")

# Connect to first reachable server
print("\n=== Checking from reachable server ===")
targets = [
    ("192.168.1.29",  "admin",   "examplenaspass"),
    ("192.168.1.129", "admin",   "examplenaspass"),
    ("192.168.1.14",  "ops", "examplepass"),
    ("192.168.1.122", "ops", "examplepass"),
    ("192.168.1.100", "ops", "examplepass"),
    ("192.168.1.123", "ops", "examplepass"),
    ("192.168.1.102", "ops", "examplepass"),
    ("192.168.1.120", "ops", "examplepass"),
]

j = paramiko.SSHClient()
j.set_missing_host_key_policy(paramiko.AutoAddPolicy())

connected_ip = None
for ip, user, pw in targets:
    try:
        j.connect(ip, username=user, password=pw, timeout=5)
        print(f"Connected to {ip}")
        connected_ip = ip
        break
    except Exception as e:
        print(f"  {ip}: {str(e)[:40]}")

if not connected_ip:
    print("Cannot connect to any server!")
    exit(1)

# Check who has .34 via arping (if available)
cmds = [
    ("Check .34 via arping", "arping -c 2 -w 3 203.0.113.10 2>&1 || echo done"),
    ("ARP table for .34", "arp -n 2>/dev/null | grep 144.34 || ip neigh | grep 144.34"),
    ("My IPs", "hostname -I"),
    ("Check server6 SSH .6", "bash -c '(echo >/dev/tcp/192.168.1.6/22) 2>/dev/null && echo OPEN || echo CLOSED'"),
    ("Check server6 SSH .106", "bash -c '(echo >/dev/tcp/192.168.1.106/22) 2>/dev/null && echo OPEN || echo CLOSED'"),
]

for label, cmd in cmds:
    try:
        _, out, _ = j.exec_command(cmd, timeout=8)
        result = out.read().decode().strip()
        print(f"\n  {label}: {result}")
    except Exception as e:
        print(f"\n  {label}: timeout/error: {e}")

# Try to reach server6 via sshpass
print("\n=== Try SSH to server6 ===")
for ip in ["192.168.1.6", "192.168.1.106"]:
    try:
        _, out, _ = j.exec_command(
            f"sshpass -p 'legacypass06' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 admin@{ip} "
            f"'echo CONNECTED; ip addr | grep \"inet \" | grep -v 127.0; docker network ls 2>/dev/null; ip route | grep 140.113 2>/dev/null' 2>&1",
            timeout=12
        )
        result = out.read().decode().strip()
        print(f"  {ip}: {result}")
        if "CONNECTED" in result:
            break
    except Exception as e:
        print(f"  {ip}: {e}")

j.close()
