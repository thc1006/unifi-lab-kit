#!/usr/bin/env python3
"""Check server6 IP conflict via NAS jump."""
import paramiko

nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.29", username="admin", password="examplenaspass", timeout=5)
print("Connected to NAS\n")

# First find server6 - try .6 and .106
for ip in ["192.168.1.6", "192.168.1.106"]:
    _, out, _ = nas.exec_command(
        f"bash -c '(echo >/dev/tcp/{ip}/22) 2>/dev/null && echo OPEN || echo CLOSED'",
        timeout=5
    )
    status = out.read().decode().strip()
    print(f"  server6 at {ip}: SSH {status}")

# Try SSH via sshpass
print("\nTrying SSH to server6...")
for ip in ["192.168.1.6", "192.168.1.106"]:
    _, out, _ = nas.exec_command(
        f"sshpass -p 'legacypass06' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 admin@{ip} 'ip addr show; echo SEPARATOR; docker network ls; echo SEPARATOR; ip route | grep 140' 2>&1",
        timeout=15
    )
    result = out.read().decode().strip()
    if "denied" not in result.lower() and "timed out" not in result.lower() and "No route" not in result:
        print(f"\n=== server6 at {ip} ===")
        print(result)
        break
    else:
        print(f"  {ip}: {result[:80]}")

# Also check ARP for .34
print("\n=== ARP for 203.0.113.10 ===")
_, out, _ = nas.exec_command("arp -n | grep 140.113", timeout=5)
print(out.read().decode().strip())

# Check from NAS: who has .34?
_, out, _ = nas.exec_command("arping -c 2 -I enp8s0 203.0.113.10 2>&1", timeout=10)
print(f"\narping result: {out.read().decode().strip()}")

# Check NAS docker for any container using .34
print("\n=== NAS Docker networks with 140.113 ===")
_, out, _ = nas.exec_command("docker network inspect wan 2>/dev/null | grep -A3 '\"IPv4\\|Gateway\\|Subnet'", timeout=5)
print(out.read().decode().strip())

_, out, _ = nas.exec_command("docker network inspect wan 2>/dev/null | grep -B5 '144.34'", timeout=5)
result = out.read().decode().strip()
if result:
    print(f"\nContainer using .34: {result}")

nas.close()
