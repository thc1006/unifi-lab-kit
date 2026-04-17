#!/usr/bin/env python3
"""Verify external SSH after server6 physical disconnect."""
import paramiko
import socket
import time

print("Waiting 5s for ARP cache to clear...")
time.sleep(5)

# ============================================================
# Part 1: Check WAN IP port forwards from laptop (hairpin NAT)
# ============================================================
print("=" * 60)
print("PART 1: Port scan WAN IP 203.0.113.10")
print("=" * 60)

WAN = "203.0.113.10"
ALL_PORTS = [
    (12020, "server2(old)",  ".102"),
    (12060, "server6",       ".106"),
    (12080, "server8",       ".108"),
    (12090, "server9",       ".109"),
    (12150, "server15",      ".115"),
    (12200, "server20",      ".120"),
    (12210, "server21",      ".121"),
    (12220, "server22",      ".122"),
    (12230, "Pro6000",       ".123"),
]

for port, name, target in ALL_PORTS:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((WAN, port))
        if result == 0:
            try:
                banner = sock.recv(256).decode().strip()
            except:
                banner = "connected"
            print(f"  :{port} -> {target} {name:15s}  OPEN  {banner[:50]}")
        else:
            print(f"  :{port} -> {target} {name:15s}  CLOSED")
        sock.close()
    except Exception as e:
        print(f"  :{port} -> {target} {name:15s}  {str(e)[:30]}")

# ============================================================
# Part 2: Test from NAS wan32nginx container (true external)
# ============================================================
print("\n" + "=" * 60)
print("PART 2: Test from NAS (external perspective)")
print("=" * 60)

nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.29", username="admin", password="examplenaspass", timeout=5)
print("Connected to NAS")

# Port check from NAS
for port, name, target in ALL_PORTS:
    try:
        _, out, _ = nas.exec_command(
            f"bash -c '(echo >/dev/tcp/{WAN}/{port}) 2>/dev/null && echo OPEN || echo CLOSED'",
            timeout=5
        )
        status = out.read().decode().strip()
        if status == "OPEN":
            _, out2, _ = nas.exec_command(f"echo | nc -w2 {WAN} {port} 2>/dev/null | head -1", timeout=5)
            banner = out2.read().decode().strip()
            print(f"  :{port} -> {target} {name:15s}  OPEN  {banner[:50]}")
        else:
            print(f"  :{port} -> {target} {name:15s}  {status}")
    except Exception as e:
        print(f"  :{port} -> {target} {name:15s}  timeout")

# ============================================================
# Part 3: Test from wan32nginx_nginx_1 (real public IP)
# ============================================================
print("\n" + "=" * 60)
print("PART 3: Test from wan32nginx_nginx_1 (203.0.113.12)")
print("=" * 60)

for port, name, target in [(12200, "server20", ".120"), (12220, "server22", ".122"), (12230, "Pro6000", ".123"), (12060, "server6", ".106")]:
    try:
        _, out, _ = nas.exec_command(
            f"docker exec wan32nginx_nginx_1 bash -c '(echo >/dev/tcp/{WAN}/{port}) 2>/dev/null && echo OPEN || echo CLOSED' 2>&1",
            timeout=8
        )
        result = out.read().decode().strip()
        print(f"  :{port} -> {target} {name:15s}  {result}")
    except:
        print(f"  :{port} -> {target} {name:15s}  timeout")

# ============================================================
# Part 4: Check current server IPs (still old?)
# ============================================================
print("\n" + "=" * 60)
print("PART 4: Current server IPs")
print("=" * 60)

servers = [
    ("192.168.1.14",  "ops", "examplepass", "server22",  "192.168.1.122"),
    ("192.168.1.100", "ops", "examplepass", "Pro6000",   "192.168.1.123"),
    ("192.168.1.102", "ops", "examplepass", "server20",  "192.168.1.120"),
]

for old_ip, user, pw, name, new_ip in servers:
    for ip in [new_ip, old_ip]:
        try:
            _, out, _ = nas.exec_command(
                f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 {user}@{ip} 'hostname -I' 2>&1",
                timeout=10
            )
            result = out.read().decode().strip()
            if "denied" not in result.lower() and "timed out" not in result.lower():
                label = "NEW" if ip == new_ip else "OLD"
                print(f"  {name:12s}  at {ip:>15} ({label})  IPs: {result[:40]}")
                break
        except:
            continue
    else:
        print(f"  {name:12s}  UNREACHABLE")

nas.close()
print("\n=== DONE ===")
