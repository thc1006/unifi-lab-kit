#!/usr/bin/env python3
"""
1. Try USG SSH with multiple passwords
2. If that fails, use config.gateway.json via Controller
3. Reboot server11 + server13
4. Full device status
"""
import paramiko
import socket
import subprocess
import time
import json

# ============================================================
# Part 1: Try USG SSH
# ============================================================
print("=" * 60)
print("PART 1: USG SSH - try passwords")
print("=" * 60)

usg_passwords = [
    ("ops", "exampleswitchpass"),
    ("ops", "examplepass"),
    ("admin", "exampleswitchpass"),
    ("admin", "examplepass"),
    ("root", "exampleswitchpass"),
    ("ubnt", "ubnt"),
]

usg = paramiko.SSHClient()
usg.set_missing_host_key_policy(paramiko.AutoAddPolicy())
usg_connected = False

for user, pw in usg_passwords:
    try:
        usg.connect("192.168.1.1", username=user, password=pw, timeout=5)
        print(f"  Connected! user={user} pw={pw}")
        usg_connected = True

        # Set DHCP static mappings
        mappings = [
            ("server11", "00:00:5e:00:53:11", "192.168.1.111"),
            ("server13", "00:00:5e:00:53:13", "192.168.1.113"),
        ]

        # First check the DHCP config structure
        _, out, _ = usg.exec_command(
            "vbash -ic 'show configuration commands | grep static-mapping | head -20'",
            timeout=10,
        )
        print(f"\nExisting mappings:\n{out.read().decode().strip()[:500]}")

        # Find the correct shared-network-name
        _, out, _ = usg.exec_command(
            "vbash -ic 'show configuration commands | grep shared-network-name | head -5'",
            timeout=10,
        )
        snn = out.read().decode().strip()
        print(f"\nShared network: {snn[:200]}")

        # Try setting mappings
        for name, mac, ip in mappings:
            print(f"\nSetting {name}: {mac} -> {ip}")
            cfg_cmds = (
                f"vbash -ic '"
                f"configure ; "
                f"set service dhcp-server shared-network-name LAN_192.168.1.0-24 subnet 192.168.1.0/24 static-mapping {name} ip-address {ip} ; "
                f"set service dhcp-server shared-network-name LAN_192.168.1.0-24 subnet 192.168.1.0/24 static-mapping {name} mac-address {mac} ; "
                f"commit ; save ; exit'"
            )
            _, out, err = usg.exec_command(cfg_cmds, timeout=15)
            result = out.read().decode().strip()
            error = err.read().decode().strip()
            print(f"  Out: {result[:200]}")
            if error:
                print(f"  Err: {error[:200]}")

        # Show DHCP leases
        _, out, _ = usg.exec_command("vbash -ic 'show dhcp leases'", timeout=10)
        print(f"\nDHCP leases:\n{out.read().decode().strip()[:500]}")

        usg.close()
        break
    except paramiko.AuthenticationException:
        continue
    except Exception as e:
        print(f"  {user}/{pw}: {e}")
        break

if not usg_connected:
    print("  All USG passwords failed!")
    print("  Will need to set DHCP via config.gateway.json or directly on servers")

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

print("\nWaiting 50s...")
time.sleep(50)

# Check new IPs
checks = [
    ("server11", [("192.168.1.111", "NEW"), ("192.168.1.220", "OLD")]),
    ("server13", [("192.168.1.113", "NEW"), ("192.168.1.202", "OLD")]),
]

for name, ips in checks:
    for ip, label in ips:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        r = s.connect_ex((ip, 22))
        if r == 0:
            print(f"  {name}: {ip} ({label}) SSH OPEN")
            break
        s.close()
    else:
        print(f"  {name}: not responding yet")

# ============================================================
# Part 3: Full scan + unknown devices
# ============================================================
print("\n" + "=" * 60)
print("PART 3: Full device inventory")
print("=" * 60)

known = {
    1: "USG", 106: "server6", 108: "server8", 109: "server9",
    111: "server11(new)", 113: "server13(new)",
    115: "server15", 120: "server20", 121: "server21",
    122: "server22", 123: "Pro6000", 129: "NAS",
    219: "laptop", 220: "server11(old)", 202: "server13(old)",
}

unknown_ssh = []
unknown_nossh = []
all_alive = []

for i in range(1, 255):
    ip = f"192.168.1.{i}"
    r = subprocess.run(["ping", "-n", "1", "-w", "400", ip], capture_output=True)
    if "TTL=" not in r.stdout.decode(errors="replace"):
        continue

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.5)
    ssh = s.connect_ex((ip, 22)) == 0
    s.close()

    name = known.get(i, "")
    all_alive.append((i, ssh, name))
    if not name:
        if ssh:
            unknown_ssh.append(i)
        else:
            unknown_nossh.append(i)

print(f"\nTotal alive: {len(all_alive)}")
print(f"\n--- Known devices ({len(all_alive) - len(unknown_ssh) - len(unknown_nossh)}) ---")
for i, ssh, name in all_alive:
    if name:
        print(f"  .{i:<3}  {'SSH' if ssh else '---'}  {name}")

print(f"\n--- UNKNOWN with SSH ({len(unknown_ssh)}) ---")
for i in unknown_ssh:
    print(f"  .{i:<3}  SSH OPEN  <- need to identify")

print(f"\n--- UNKNOWN no SSH ({len(unknown_nossh)}) ---")
for i in unknown_nossh:
    print(f"  .{i:<3}  no SSH   <- student PC / other")

print("\n=== DONE ===")
