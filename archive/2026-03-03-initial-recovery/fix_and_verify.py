#!/usr/bin/env python3
"""Check netplan config, force proper DHCP renewal, verify external SSH."""
import paramiko
import time

# ============================================================
# Part 1: Check netplan config + force proper DHCP renewal
# ============================================================
print("=" * 60)
print("PART 1: Check network config + force renewal")
print("=" * 60)

SERVERS = [
    ("192.168.1.14",  "ops", "examplepass", "server22"),
    ("192.168.1.100", "ops", "examplepass", "Pro6000"),
    ("192.168.1.102", "ops", "examplepass", "server20"),
]

for ip, user, pw, name in SERVERS:
    print(f"\n--- {name} ({ip}) ---")
    try:
        j = paramiko.SSHClient()
        j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        j.connect(ip, username=user, password=pw, timeout=5)

        # Check netplan config
        _, out, _ = j.exec_command("cat /etc/netplan/*.yaml 2>/dev/null || echo 'NO NETPLAN'", timeout=5)
        netplan = out.read().decode().strip()
        print(f"  Netplan config:")
        for line in netplan.split('\n')[:15]:
            print(f"    {line}")

        # Check current DHCP lease
        _, out, _ = j.exec_command("cat /var/lib/NetworkManager/*.lease 2>/dev/null | head -20 || echo 'no lease file'", timeout=5)
        lease = out.read().decode().strip()
        print(f"  Lease: {lease[:150]}")

        # Get interface
        _, out, _ = j.exec_command("ip route | grep default | head -1 | awk '{print $5}'", timeout=5)
        iface = out.read().decode().strip()

        # Force: flush IP + request new DHCP lease
        print(f"  Flushing {iface} and requesting new lease...")
        cmd = (
            f"echo '{pw}' | sudo -S bash -c '"
            f"ip addr flush dev {iface} && "
            f"sleep 1 && "
            f"nmcli device disconnect {iface} && "
            f"sleep 2 && "
            f"nmcli device connect {iface}"
            f"' 2>&1"
        )
        channel = j.get_transport().open_session()
        channel.exec_command(cmd)
        print(f"  Sent flush+reconnect (connection will drop)")
        j.close()
    except Exception as e:
        print(f"  Error: {e}")

# server6 (god user, has dhclient)
print(f"\n--- server6 (192.168.1.6) ---")
try:
    j = paramiko.SSHClient()
    j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    j.connect("192.168.1.6", username="admin", password="legacypass06", timeout=5)

    _, out, _ = j.exec_command("cat /etc/netplan/*.yaml 2>/dev/null; cat /etc/network/interfaces 2>/dev/null | head -20", timeout=5)
    netcfg = out.read().decode().strip()
    print(f"  Network config:")
    for line in netcfg.split('\n')[:10]:
        print(f"    {line}")

    _, out, _ = j.exec_command("ip route | grep default | head -1 | awk '{print $5}'", timeout=5)
    iface = out.read().decode().strip()
    print(f"  Interface: {iface}")

    # Check if god has sudo
    _, out, _ = j.exec_command("sudo -n whoami 2>&1", timeout=5)
    sudo_check = out.read().decode().strip()
    print(f"  Sudo check: {sudo_check}")

    if sudo_check == "root":
        cmd = f"sudo ip addr flush dev {iface} && sleep 1 && sudo dhclient {iface} 2>&1"
    else:
        cmd = f"sudo dhclient -r {iface} 2>&1; sleep 2; sudo dhclient {iface} 2>&1"

    channel = j.get_transport().open_session()
    channel.exec_command(cmd)
    print(f"  Sent DHCP renewal command")
    j.close()
except Exception as e:
    print(f"  Error: {e}")

# Wait
print("\nWaiting 20s for all servers to get new IPs...")
time.sleep(20)

# ============================================================
# Part 2: Check all new IPs
# ============================================================
print("\n" + "=" * 60)
print("PART 2: Check IPs")
print("=" * 60)

CHECK = [
    ("server6",  [("192.168.1.106", "NEW"), ("192.168.1.6", "OLD")],   "admin",   "legacypass06"),
    ("server22", [("192.168.1.122", "NEW"), ("192.168.1.14", "OLD")],   "ops", "examplepass"),
    ("Pro6000",  [("192.168.1.123", "NEW"), ("192.168.1.100", "OLD")],  "ops", "examplepass"),
    ("server20", [("192.168.1.120", "NEW"), ("192.168.1.102", "OLD")],  "ops", "examplepass"),
]

ip_results = {}
for name, ips, user, pw in CHECK:
    for test_ip, label in ips:
        try:
            j = paramiko.SSHClient()
            j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            j.connect(test_ip, username=user, password=pw, timeout=5)
            _, out, _ = j.exec_command("hostname -I | awk '{print $1}'", timeout=5)
            actual = out.read().decode().strip()
            j.close()
            ip_results[name] = (test_ip, label, actual)
            print(f"  {name:12s}  at {test_ip:>15} ({label})  actual={actual}")
            break
        except:
            continue
    else:
        ip_results[name] = None
        print(f"  {name:12s}  UNREACHABLE")

# ============================================================
# Part 3: Test external SSH from NAS using curl/wget
# ============================================================
print("\n" + "=" * 60)
print("PART 3: External SSH test")
print("=" * 60)

nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    nas.connect("192.168.1.29", username="admin", password="examplenaspass", timeout=5)
except:
    nas.connect("192.168.1.129", username="admin", password="examplenaspass", timeout=5)
print("Connected to NAS")

WAN = "203.0.113.10"
ports = [
    (12060, "server6",  ".106"),
    (12200, "server20", ".120"),
    (12210, "server21", ".121"),
    (12220, "server22", ".122"),
    (12230, "Pro6000",  ".123"),
]

# First, check if USG actually has port forward rules active
# by checking from wan32nginx_nginx_1 (public IP)
print("\n  From wan32nginx_nginx_1 container (public 203.0.113.12):")
for port, name, target in ports:
    _, out, _ = nas.exec_command(
        f"docker exec wan32nginx_nginx_1 bash -c '(echo >/dev/tcp/{WAN}/{port}) 2>/dev/null && echo OPEN || echo CLOSED' 2>&1",
        timeout=8
    )
    result = out.read().decode().strip()
    if "exec format" in result or "OCI" in result:
        # Container might use a different shell, try with sh
        _, out, _ = nas.exec_command(
            f"docker exec wan32nginx_nginx_1 timeout 3 sh -c 'cat < /dev/null > /dev/tcp/{WAN}/{port}' 2>&1 && echo OPEN || echo CLOSED",
            timeout=8
        )
        result = out.read().decode().strip()
    print(f"  :{port} -> {target} {name:12s}  {result}")

# Try with sshpass from wan32nginx_nginx_1 or install nc
print("\n  Installing nc in container and retesting...")
_, out, _ = nas.exec_command(
    "docker exec wan32nginx_nginx_1 sh -c 'apt-get update -qq && apt-get install -y -qq netcat-openbsd 2>&1 | tail -1' 2>&1",
    timeout=30
)
install = out.read().decode().strip()
print(f"  nc install: {install[:80]}")

for port, name, target in ports:
    _, out, _ = nas.exec_command(
        f"docker exec wan32nginx_nginx_1 sh -c 'echo | nc -w3 {WAN} {port} 2>&1' 2>&1",
        timeout=8
    )
    result = out.read().decode().strip()
    if "SSH" in result:
        print(f"  :{port} -> {target} {name:12s}  OPEN: {result[:50]}")
    elif result:
        print(f"  :{port} -> {target} {name:12s}  {result[:60]}")
    else:
        print(f"  :{port} -> {target} {name:12s}  TIMEOUT/CLOSED")

nas.close()
print("\n=== DONE ===")
