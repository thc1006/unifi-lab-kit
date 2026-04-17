#!/usr/bin/env python3
"""Force DHCP full release/renew + test external SSH from wan32nginx container."""
import paramiko
import time

# ============================================================
# Part 1: Force DHCP full release/renew (nmcli con down/up)
# ============================================================
print("=" * 60)
print("PART 1: Force DHCP release/renew (nmcli con down + up)")
print("=" * 60)

ACCESSIBLE = [
    ("192.168.1.14",  "ops", "examplepass", "server22",  "eno1"),
    ("192.168.1.100", "ops", "examplepass", "Pro6000",   "enp131s0"),
    ("192.168.1.102", "ops", "examplepass", "server20",  "enp132s0"),
]

# server6 separately (god user, has dhclient)
print("\n--- server6 (192.168.1.6) ---")
try:
    j = paramiko.SSHClient()
    j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    j.connect("192.168.1.6", username="admin", password="legacypass06", timeout=5)
    _, out, _ = j.exec_command("ip route | grep default | head -1 | awk '{print $5}'", timeout=5)
    iface = out.read().decode().strip()
    print(f"  Interface: {iface}")
    # Use dhclient with release then renew
    _, out, _ = j.exec_command(f"sudo dhclient -r {iface} 2>&1 && sleep 2 && sudo dhclient {iface} 2>&1", timeout=20)
    result = out.read().decode().strip()
    print(f"  dhclient: {result[:100] if result else 'OK'}")
    j.close()
    time.sleep(3)
    # Try new IP
    for test_ip in ["192.168.1.106", "192.168.1.6"]:
        try:
            j2 = paramiko.SSHClient()
            j2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            j2.connect(test_ip, username="admin", password="legacypass06", timeout=3)
            _, out, _ = j2.exec_command("hostname -I | awk '{print $1}'", timeout=5)
            actual = out.read().decode().strip()
            j2.close()
            print(f"  Reachable at {test_ip}, actual IP: {actual}")
            break
        except:
            continue
    else:
        print(f"  UNREACHABLE")
except Exception as e:
    print(f"  Error: {e}")

# Other servers: nmcli con down/up
for ip, user, pw, name, iface in ACCESSIBLE:
    print(f"\n--- {name} ({ip}) ---")
    try:
        j = paramiko.SSHClient()
        j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        j.connect(ip, username=user, password=pw, timeout=5)

        # Get connection name
        _, out, _ = j.exec_command(f"nmcli -t -f NAME,DEVICE con show --active | grep {iface} | cut -d: -f1", timeout=5)
        con_name = out.read().decode().strip()
        if not con_name:
            con_name = iface
        print(f"  Connection: {con_name}")

        # Down then up (this will drop our SSH!)
        cmd = f"echo '{pw}' | sudo -S bash -c 'nmcli con down \"{con_name}\" && sleep 2 && nmcli con up \"{con_name}\"' 2>&1"
        channel = j.get_transport().open_session()
        channel.exec_command(cmd)
        # Don't wait for result - connection will drop
        print(f"  Sent down/up command (connection will drop)...")
        j.close()
    except Exception as e:
        print(f"  Error: {e}")

# Wait for all to come back
print("\nWaiting 15s for all servers to reconnect...")
time.sleep(15)

# ============================================================
# Part 2: Check which IPs are reachable now
# ============================================================
print("\n" + "=" * 60)
print("PART 2: Check IPs after renewal")
print("=" * 60)

CHECK = [
    ("server6",  "192.168.1.106", "192.168.1.6",   "admin",   "legacypass06"),
    ("server22", "192.168.1.122", "192.168.1.14",   "ops", "examplepass"),
    ("Pro6000",  "192.168.1.123", "192.168.1.100",  "ops", "examplepass"),
    ("server20", "192.168.1.120", "192.168.1.102",  "ops", "examplepass"),
]

for name, new_ip, old_ip, user, pw in CHECK:
    found = False
    for test_ip, label in [(new_ip, "NEW"), (old_ip, "OLD")]:
        try:
            j = paramiko.SSHClient()
            j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            j.connect(test_ip, username=user, password=pw, timeout=5)
            _, out, _ = j.exec_command("hostname -I | awk '{print $1}'", timeout=5)
            actual = out.read().decode().strip()
            j.close()
            print(f"  {name:12s}  at {test_ip:>15} ({label})  actual={actual}")
            found = True
            break
        except:
            continue
    if not found:
        print(f"  {name:12s}  UNREACHABLE on both {new_ip} and {old_ip}")

# ============================================================
# Part 3: Test external SSH from wan32nginx_nginx_1 container
# ============================================================
print("\n" + "=" * 60)
print("PART 3: External SSH test from wan32nginx (203.0.113.12)")
print("=" * 60)

# Connect to NAS - try both old and new IP
nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas_connected = False
for nas_ip in ["192.168.1.129", "192.168.1.29"]:
    try:
        nas.connect(nas_ip, username="admin", password="examplenaspass", timeout=5)
        print(f"Connected to NAS at {nas_ip}")
        nas_connected = True
        break
    except:
        continue

if nas_connected:
    # Test from wan32nginx_nginx_1 container (has public IP on macvlan)
    WAN = "203.0.113.10"
    test_ports = [
        (12060, "server6",  ".106"),
        (12080, "server8",  ".108"),
        (12090, "server9",  ".109"),
        (12200, "server20", ".120"),
        (12210, "server21", ".121"),
        (12220, "server22", ".122"),
        (12230, "Pro6000",  ".123"),
    ]

    for port, name, target in test_ports:
        _, out, _ = nas.exec_command(
            f"docker exec wan32nginx_nginx_1 sh -c 'echo | nc -w3 {WAN} {port} 2>&1 || echo TIMEOUT' 2>&1",
            timeout=10
        )
        result = out.read().decode().strip()
        if "SSH" in result:
            status = f"OPEN ({result[:50]})"
        elif "TIMEOUT" in result or not result:
            status = "TIMEOUT"
        else:
            status = result[:60]
        print(f"  :{port} -> {target} {name:12s}  {status}")

    # Also try direct sshpass from the container
    print("\n  Trying SSH auth from wan32nginx container...")
    for port, name, target in [(12200, "server20", ".120"), (12220, "server22", ".122"), (12230, "Pro6000", ".123")]:
        _, out, _ = nas.exec_command(
            f"docker exec wan32nginx_nginx_1 sh -c 'echo | nc -w3 {WAN} {port} 2>&1' 2>&1",
            timeout=8
        )
        result = out.read().decode().strip()
        print(f"  :{port} {name:12s}  {result[:70] if result else 'no response'}")

    nas.close()
else:
    print("  Cannot connect to NAS!")

print("\n=== DONE ===")
