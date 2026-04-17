#!/usr/bin/env python3
"""Try user-suggested USG passwords."""
import paramiko
import socket
import time

HOST = "192.168.1.1"
PORT = 22

# User suggested + controller-related passwords
CREDS = [
    ("ops", "examplepass"),
    ("ops", "ops"),
    ("ops", "exampleunifipass"),
    ("ops", "exampleunifipass"),
    ("ops", "examplepassunifi"),
    ("admin", "examplepass"),
    ("admin", "ops"),
    ("ubnt", "examplepass"),
    ("ubnt", "ops"),
    ("ops", "mllab912"),
    ("ops", "exampleswitchpass"),
    ("root", "examplepass"),
]


def run_cmd(client, cmd, timeout=10):
    try:
        _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        return out.strip()
    except Exception as e:
        return f"[ERROR]: {e}"


def try_login(user, pwd):
    try:
        sock = socket.create_connection((HOST, PORT), timeout=10)
        t = paramiko.Transport(sock)
        t.banner_timeout = 30
        t.start_client()
        t.auth_password(user, pwd)
        if t.is_authenticated():
            c = paramiko.SSHClient()
            c._transport = t
            return c
        t.close()
    except paramiko.AuthenticationException:
        pass
    except Exception as e:
        print(f"    connection error: {e}")
        time.sleep(2)
    return None


for user, pwd in CREDS:
    label = f"{user}/{pwd}"
    print(f"Trying {label}...", end=" ", flush=True)
    client = try_login(user, pwd)
    if client:
        print("SUCCESS!")
        print(f"\n{'='*60}")
        print(f"  USG-3P CONNECTED: {user}/{pwd}")
        print(f"{'='*60}")

        cmds = [
            "show version",
            "show interfaces",
            "show configuration commands",
            "show nat rules",
            "show dhcp leases",
            "show ip route",
            "show arp",
        ]
        for cmd in cmds:
            print(f"\n>>> {cmd}")
            print(run_cmd(client, cmd))

        client.close()
        print("\n=== DONE ===")
        exit(0)
    else:
        print("failed")
    time.sleep(1)

print("\nAll passwords failed. Need to check UniFi Controller for Device Authentication settings.")
