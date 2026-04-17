#!/usr/bin/env python3
"""Final check all servers + port forwards."""
import paramiko
import time

print("Waiting 30s for servers to finish booting...")
time.sleep(30)

j = paramiko.SSHClient()
j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
j.connect("192.168.1.29", username="admin", password="examplenaspass", timeout=5)

WAN = "203.0.113.10"

print("=" * 60)
print("SERVER STATUS")
print("=" * 60)

checks = [
    ("server6",  ["192.168.1.106", "192.168.1.6"]),
    ("server22", ["192.168.1.122", "192.168.1.14"]),
    ("server20", ["192.168.1.120"]),
    ("Pro6000",  ["192.168.1.123"]),
]

for name, ips in checks:
    for ip in ips:
        try:
            _, out, _ = j.exec_command(
                f"bash -c '(echo >/dev/tcp/{ip}/22) 2>/dev/null && echo OPEN || echo CLOSED'",
                timeout=4
            )
            status = out.read().decode().strip()
            label = "NEW" if ip.split(".")[-1] in ["106","120","122","123"] else "OLD"
            print(f"  {name:12s}  {ip:>15} ({label})  SSH: {status}")
            if status == "OPEN":
                break
        except:
            print(f"  {name:12s}  {ip:>15}  timeout")

print("\n" + "=" * 60)
print("PORT FORWARD (from NAS -> WAN)")
print("=" * 60)

pf_tests = [
    (12060, "server6",  ".106"),
    (12200, "server20", ".120"),
    (12220, "server22", ".122"),
    (12230, "Pro6000",  ".123"),
]

for port, name, target in pf_tests:
    try:
        _, out, _ = j.exec_command(
            f"echo | nc -w3 {WAN} {port} 2>/dev/null | head -1",
            timeout=6
        )
        banner = out.read().decode().strip()
        if "SSH" in banner:
            print(f"  :{port} -> {target} {name:12s}  OK ({banner})")
        else:
            print(f"  :{port} -> {target} {name:12s}  NO RESPONSE")
    except:
        print(f"  :{port} -> {target} {name:12s}  TIMEOUT")

print("\n" + "=" * 60)
print("SSH AUTH via port forward")
print("=" * 60)

auth_tests = [
    (12200, "ops", "examplepass",       "server20"),
    (12230, "ops", "examplepass",       "Pro6000"),
    (12220, "ops", "examplepass",       "server22"),
    (12060, "admin",   "legacypass06", "server6"),
]

for port, user, pw, name in auth_tests:
    try:
        _, out, _ = j.exec_command(
            f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 "
            f"-p {port} {user}@{WAN} 'hostname' 2>&1",
            timeout=10
        )
        result = out.read().decode().strip()
        if "denied" in result.lower() or "timeout" in result.lower() or "refused" in result.lower():
            print(f"  :{port} {name:12s}  FAIL: {result[:60]}")
        else:
            print(f"  :{port} {name:12s}  OK -> {result}")
    except:
        print(f"  :{port} {name:12s}  TIMEOUT")

# Internet check
_, out, _ = j.exec_command("ping -c 1 -W 2 8.8.8.8 2>&1 | tail -2", timeout=5)
print(f"\nInternet: {out.read().decode().strip()}")

# IP conflict check
_, out, _ = j.exec_command(
    "sshpass -p 'legacypass06' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 admin@192.168.1.106 "
    "'ip addr | grep 140.113 || echo NO-PUBLIC-IP' 2>&1",
    timeout=10
)
print(f"server6 conflict check: {out.read().decode().strip()}")

j.close()
print("\n=== DONE ===")
