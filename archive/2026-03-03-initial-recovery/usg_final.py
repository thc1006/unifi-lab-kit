#!/usr/bin/env python3
"""Connect to USG-3P with the REAL password from Controller API."""
import paramiko
import socket

HOST = "192.168.1.1"
USER = "ops"
PASS = "examplewifipass"


def run_cmd(client, cmd, timeout=15):
    try:
        _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        return (out + ("\n[ERR]: " + err if err.strip() else "")).strip()
    except Exception as e:
        return f"[ERROR]: {e}"


print(f"Connecting to {USER}@{HOST} with password from Controller API...")
sock = socket.create_connection((HOST, 22), timeout=10)
t = paramiko.Transport(sock)
t.banner_timeout = 30
t.start_client()
t.auth_password(USER, PASS)

if t.is_authenticated():
    print("SUCCESS!\n")
    c = paramiko.SSHClient()
    c._transport = t

    commands = [
        ("show version", "系統版本"),
        ("show interfaces", "介面設定"),
        ("show configuration commands", "完整設定"),
        ("show nat rules", "NAT / Port Forward 規則"),
        ("show nat translations", "NAT 轉換表"),
        ("show dhcp leases", "DHCP 租約表"),
        ("show ip route", "路由表"),
        ("show arp", "ARP 表（MAC 對應）"),
    ]

    for cmd, desc in commands:
        print(f"\n{'='*60}")
        print(f">>> {cmd}  ({desc})")
        print(f"{'='*60}")
        print(run_cmd(c, cmd))

    c.close()
else:
    print("Authentication failed!")
    t.close()
