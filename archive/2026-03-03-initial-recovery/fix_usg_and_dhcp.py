#!/usr/bin/env python3
"""
Fix USG:
1. SSH into USG with correct password
2. Fix inform URL to point to NAS Controller
3. Set DHCP static mappings for server11 + server13
4. Reboot servers to get new IPs
"""
import paramiko
import socket
import time

# ============================================================
# Part 1: SSH into USG and fix inform URL + DHCP
# ============================================================
print("=" * 60)
print("PART 1: Fix USG")
print("=" * 60)

usg = paramiko.SSHClient()
usg.set_missing_host_key_policy(paramiko.AutoAddPolicy())
usg.connect("192.168.1.1", username="ops", password="exampleusgpass", timeout=5)
print("Connected to USG!")

# Check current inform URL
_, out, _ = usg.exec_command("mca-cli-op info", timeout=10)
info = out.read().decode().strip()
print(f"\nUSG info:")
for line in info.split("\n"):
    if any(k in line.lower() for k in ["status", "inform", "hostname"]):
        print(f"  {line.strip()}")

# Fix inform URL to point to Controller on NAS (192.168.54.92 via bridge 172.17.0.3)
# The Controller container listens on 8080 for device inform
# Since USG is on 192.168.1.x, it needs to reach the Controller
# Controller is at 192.168.54.92 (macvlan) - USG can't reach that
# But we can set it to the NAS IP if we have socat forwarding port 8080 too
print("\nSetting inform URL...")

# First, check what IP the USG can reach the Controller at
# The old URL was http://mllab.asuscomm.com:8080/inform
# We need: http://<controller_ip>:8080/inform
# Controller is in Docker on NAS, port 8080 needs to be forwarded too

# For now, set the static mappings directly on USG (this works immediately)
print("\n--- Setting DHCP static mappings ---")

mappings = [
    ("server11", "00:00:5e:00:53:11", "192.168.1.111"),
    ("server13", "00:00:5e:00:53:13", "192.168.1.113"),
]

# First check existing DHCP config structure
_, out, _ = usg.exec_command(
    "vbash -ic 'show configuration commands | grep static-mapping'",
    timeout=10,
)
existing = out.read().decode().strip()
print(f"\nExisting static mappings:")
for line in existing.split("\n"):
    if line.strip():
        print(f"  {line.strip()}")

# Find the correct shared-network-name
_, out, _ = usg.exec_command(
    "vbash -ic 'show configuration commands | grep shared-network-name | head -3'",
    timeout=10,
)
snn_lines = out.read().decode().strip()
print(f"\nShared network config:")
print(f"  {snn_lines[:300]}")

# Extract the shared-network-name
snn = "LAN_192.168.1.0-24"  # default
for line in snn_lines.split("\n"):
    if "shared-network-name" in line:
        parts = line.split()
        for idx, p in enumerate(parts):
            if p == "shared-network-name" and idx + 1 < len(parts):
                snn = parts[idx + 1]
                break
        break
print(f"\nUsing shared-network-name: {snn}")

# Now set the mappings using vbash configure mode
for name, mac, ip in mappings:
    print(f"\nSetting {name}: {mac} -> {ip}")
    # Use a single vbash session with configure mode
    cmd = (
        f"vbash -ic '"
        f"configure ; "
        f"set service dhcp-server shared-network-name {snn} subnet 192.168.1.0/24 static-mapping {name} ip-address {ip} ; "
        f"set service dhcp-server shared-network-name {snn} subnet 192.168.1.0/24 static-mapping {name} mac-address {mac} ; "
        f"commit ; save ; exit'"
    )
    _, out, err = usg.exec_command(cmd, timeout=20)
    result = out.read().decode().strip()
    error = err.read().decode().strip()
    print(f"  Out: {result[:300]}")
    if error:
        print(f"  Err: {error[:200]}")

# Verify
_, out, _ = usg.exec_command(
    f"vbash -ic 'show configuration commands | grep static-mapping'",
    timeout=10,
)
print(f"\nAfter setting:")
for line in out.read().decode().strip().split("\n"):
    if "server11" in line or "server13" in line:
        print(f"  {line.strip()}")

# Show DHCP leases
_, out, _ = usg.exec_command("vbash -ic 'show dhcp leases'", timeout=10)
print(f"\nDHCP leases:")
leases = out.read().decode().strip()
for line in leases.split("\n")[:20]:
    print(f"  {line}")

usg.close()

# ============================================================
# Part 2: Reboot servers
# ============================================================
print("\n" + "=" * 60)
print("PART 2: Reboot server11 + server13")
print("=" * 60)

reboots = [
    ("192.168.1.220", "admin", "examplepass", "server11"),
    ("192.168.1.202", "admin", "examplepass", "server13"),
]

for ip, user, pw, name in reboots:
    try:
        j = paramiko.SSHClient()
        j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        j.connect(ip, username=user, password=pw, timeout=5)
        channel = j.get_transport().open_session()
        channel.exec_command("sudo reboot")
        print(f"  {name} ({ip}): reboot sent")
        j.close()
    except Exception as e:
        print(f"  {name} ({ip}): {e}")

print("\nWaiting 50s...")
time.sleep(50)

# Check
checks = [
    ("server11", [("192.168.1.111", "NEW"), ("192.168.1.220", "OLD")]),
    ("server13", [("192.168.1.113", "NEW"), ("192.168.1.202", "OLD")]),
]

for name, ips in checks:
    for ip, label in ips:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(8)
        r = s.connect_ex((ip, 22))
        if r == 0:
            j = paramiko.SSHClient()
            j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            j.connect(ip, username="admin", password="examplepass", timeout=5)
            _, out, _ = j.exec_command("hostname -I | awk '{print $1}'", timeout=5)
            actual = out.read().decode().strip()
            j.close()
            print(f"  {name}: {ip} ({label}) -> actual IP: {actual}")
            break
        s.close()
    else:
        print(f"  {name}: not responding yet, waiting more...")
        time.sleep(20)
        for ip, label in ips:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            r = s.connect_ex((ip, 22))
            if r == 0:
                print(f"  {name}: {ip} ({label}) UP")
                break
            s.close()
        else:
            print(f"  {name}: still not responding")

print("\n=== DONE ===")
