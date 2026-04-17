#!/usr/bin/env python3
"""Reboot server22, Pro6000, server20 to get new DHCP IPs. Also reboot NAS last."""
import paramiko
import time

SERVERS = [
    ("192.168.1.14",  "ops", "examplepass", "server22"),
    ("192.168.1.102", "ops", "examplepass", "server20"),
    # Pro6000 last (it's our jump host)
    ("192.168.1.100", "ops", "examplepass", "Pro6000"),
]

# Don't reboot NAS yet - it runs UniFi Controller

for ip, user, pw, name in SERVERS:
    print(f"--- Rebooting {name} ({ip}) ---")
    try:
        j = paramiko.SSHClient()
        j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        j.connect(ip, username=user, password=pw, timeout=5)
        # Reboot
        channel = j.get_transport().open_session()
        channel.exec_command(f"echo '{pw}' | sudo -S reboot")
        print(f"  Reboot command sent")
        time.sleep(1)
        j.close()
    except Exception as e:
        print(f"  Error: {e}")

print("\nWaiting 60s for servers to come back...")
time.sleep(60)

# Check new IPs
print("\n" + "=" * 60)
print("Checking new IPs...")
print("=" * 60)

CHECK = [
    ("server22", "192.168.1.122", "192.168.1.14",  "ops", "examplepass"),
    ("server20", "192.168.1.120", "192.168.1.102", "ops", "examplepass"),
    ("Pro6000",  "192.168.1.123", "192.168.1.100", "ops", "examplepass"),
]

for name, new_ip, old_ip, user, pw in CHECK:
    for test_ip, label in [(new_ip, "NEW"), (old_ip, "OLD")]:
        try:
            j = paramiko.SSHClient()
            j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            j.connect(test_ip, username=user, password=pw, timeout=10)
            _, out, _ = j.exec_command("hostname -I | awk '{print $1}'", timeout=5)
            actual = out.read().decode().strip()
            j.close()
            print(f"  {name:12s}  {test_ip:>15} ({label})  actual={actual}")
            break
        except:
            continue
    else:
        print(f"  {name:12s}  UNREACHABLE (still booting?)")

print("\n=== DONE ===")
