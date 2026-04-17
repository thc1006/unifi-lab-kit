#!/usr/bin/env python3
"""
1. Fix DHCP for server11 + server13 directly on USG
2. Full status report of all devices
"""
import paramiko
import socket
import subprocess
import time

# ============================================================
# Part 1: Set DHCP static mappings directly on USG
# ============================================================
print("=" * 60)
print("PART 1: Set DHCP static mappings on USG")
print("=" * 60)

usg = paramiko.SSHClient()
usg.set_missing_host_key_policy(paramiko.AutoAddPolicy())
usg.connect("192.168.1.1", username="ops", password="exampleswitchpass", timeout=5)
print("Connected to USG")

# Check current DHCP static mappings
_, out, _ = usg.exec_command("show service dhcp-server shared-network-name LAN_192.168.1.0-24 subnet 192.168.1.0/24 static-mapping", timeout=10)
current = out.read().decode().strip()
print(f"\nCurrent static mappings:\n{current[:500]}")

# Set static mappings for server11 and server13
# USG uses EdgeOS (Vyatta) CLI
mappings = [
    ("server11", "00:00:5e:00:53:11", "192.168.1.111"),
    ("server13", "00:00:5e:00:53:13", "192.168.1.113"),
]

for name, mac, ip in mappings:
    print(f"\nSetting {name}: {mac} -> {ip}")
    commands = f"""configure
set service dhcp-server shared-network-name LAN_192.168.1.0-24 subnet 192.168.1.0/24 static-mapping {name} ip-address {ip}
set service dhcp-server shared-network-name LAN_192.168.1.0-24 subnet 192.168.1.0/24 static-mapping {name} mac-address {mac}
commit
save
exit"""

    _, out, err = usg.exec_command(commands, timeout=15)
    result = out.read().decode().strip()
    error = err.read().decode().strip()
    if result:
        print(f"  Output: {result[:200]}")
    if error:
        print(f"  Error: {error[:200]}")

# Verify
print("\nVerifying...")
_, out, _ = usg.exec_command("show service dhcp-server shared-network-name LAN_192.168.1.0-24 subnet 192.168.1.0/24 static-mapping", timeout=10)
print(out.read().decode().strip()[:500])

# Also show current leases
print("\nCurrent DHCP leases:")
_, out, _ = usg.exec_command("show dhcp leases", timeout=10)
leases = out.read().decode().strip()
for line in leases.split("\n"):
    if "192.168.1." in line:
        print(f"  {line.strip()}")

usg.close()

# ============================================================
# Part 2: Reboot both servers
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

print("\nWaiting 45s for servers to come back...")
time.sleep(45)

# Check new IPs
print("\nChecking new IPs...")
checks = [
    ("server11", "192.168.1.111", "192.168.1.220"),
    ("server13", "192.168.1.113", "192.168.1.202"),
]

for name, new_ip, old_ip in checks:
    for ip, label in [(new_ip, "NEW"), (old_ip, "OLD")]:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        r = s.connect_ex((ip, 22))
        if r == 0:
            print(f"  {name}: {ip} ({label}) SSH OPEN")
            break
        s.close()
    else:
        print(f"  {name}: neither {new_ip} nor {old_ip} responding yet")

# ============================================================
# Part 3: Full device status
# ============================================================
print("\n" + "=" * 60)
print("PART 3: Full device inventory")
print("=" * 60)

known = {
    1: ("USG", "infra"),
    106: ("server6", "ok"), 108: ("server8", "ok"), 109: ("server9", "ok"),
    111: ("server11", "new"), 113: ("server13", "new"),
    115: ("server15", "ok"),
    120: ("server20", "ok"), 121: ("server21", "ok"),
    122: ("server22", "ok"), 123: ("Pro6000", "ok"),
    129: ("NAS", "ok"),
    219: ("laptop", "self"),
    220: ("server11-old", "moving"), 202: ("server13-old", "moving"),
}

print(f"\n{'IP':<18} {'Ping':<6} {'SSH':<8} {'Identity':<20} {'Status'}")
print("-" * 75)

# Scan everything
alive_list = []
for i in range(1, 255):
    ip = f"192.168.1.{i}"
    r = subprocess.run(["ping", "-n", "1", "-w", "400", ip], capture_output=True)
    alive = "TTL=" in r.stdout.decode(errors="replace")
    if alive:
        ssh = False
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.5)
        if s.connect_ex((ip, 22)) == 0:
            ssh = True
        s.close()

        name, status = known.get(i, ("???", "UNKNOWN"))
        if status == "UNKNOWN" and ssh:
            status = "UNKNOWN+SSH"
        elif status == "UNKNOWN":
            status = "UNKNOWN-noSSH"

        alive_list.append((i, ip, alive, ssh, name, status))
        print(f"  .{i:<3} {ip:<15} {'UP':<6} {'SSH' if ssh else '-':<8} {name:<20} {status}")

print(f"\nTotal alive: {len(alive_list)}")
unknown = [(i, ip, ssh, name) for i, ip, _, ssh, name, status in alive_list if "UNKNOWN" in status]
if unknown:
    print(f"\nUNKNOWN devices ({len(unknown)}):")
    for i, ip, ssh, name in unknown:
        print(f"  .{i} {ip}  SSH:{'YES' if ssh else 'NO'}")

print("\n=== DONE ===")
