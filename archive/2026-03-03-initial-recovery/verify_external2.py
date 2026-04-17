#!/usr/bin/env python3
"""Force DHCP renewal (netplan/nmcli) + test external SSH from NAS public IP."""
import paramiko
import time

# ============================================================
# Part 1: Force DHCP renewal on accessible servers
# ============================================================
print("=" * 60)
print("PART 1: Force DHCP renewal")
print("=" * 60)

ACCESSIBLE = [
    ("192.168.1.6",   "admin",   "legacypass06", "server6"),
    ("192.168.1.14",  "ops", "examplepass",       "server22"),
    ("192.168.1.100", "ops", "examplepass",       "Pro6000"),
    ("192.168.1.102", "ops", "examplepass",       "server20"),
]

for ip, user, pw, name in ACCESSIBLE:
    print(f"\n--- {name} ({ip}) ---")
    try:
        j = paramiko.SSHClient()
        j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        j.connect(ip, username=user, password=pw, timeout=5)

        # Detect network manager
        _, out, _ = j.exec_command("which nmcli networkctl dhclient 2>/dev/null", timeout=5)
        tools = out.read().decode().strip()
        print(f"  Tools: {tools}")

        # Find main interface
        _, out, _ = j.exec_command("ip route | grep default | head -1 | awk '{print $5}'", timeout=5)
        iface = out.read().decode().strip()
        print(f"  Interface: {iface}")

        # Try multiple renewal methods
        sudo_prefix = f"echo '{pw}' | sudo -S" if user != "root" else "sudo"
        cmds = [
            f"{sudo_prefix} nmcli device reapply {iface} 2>&1",
            f"{sudo_prefix} nmcli con down {iface} 2>&1 && sleep 1 && {sudo_prefix} nmcli con up {iface} 2>&1",
            f"{sudo_prefix} networkctl reconfigure {iface} 2>&1",
            f"{sudo_prefix} dhclient -r {iface} 2>&1 && sleep 1 && {sudo_prefix} dhclient {iface} 2>&1",
            f"{sudo_prefix} netplan apply 2>&1",
        ]

        renewed = False
        for cmd in cmds:
            _, out, err = j.exec_command(cmd, timeout=15)
            result = out.read().decode().strip()
            error = err.read().decode().strip()
            # Check if it worked (no "not found", no "error")
            combined = result + error
            if "not found" not in combined.lower() and "unrecognized" not in combined.lower() and "no suitable" not in combined.lower():
                print(f"  Renewal: {result[:80] if result else 'OK'}")
                if error and "password" not in error.lower():
                    print(f"  stderr: {error[:80]}")
                renewed = True
                break

        if not renewed:
            print(f"  All renewal methods failed")

        time.sleep(2)
        _, out, _ = j.exec_command("hostname -I", timeout=5)
        new_ip = out.read().decode().strip()
        print(f"  Current IP: {new_ip}")
        j.close()
    except Exception as e:
        print(f"  Error: {e}")

print("\nWaiting 5s...")
time.sleep(5)

# ============================================================
# Part 2: Re-check IPs after renewal
# ============================================================
print("\n" + "=" * 60)
print("PART 2: Check new IPs")
print("=" * 60)

# Try connecting to both old and new IPs
ALL_IPS = [
    # (old_ip, new_ip, user, pw, name)
    ("192.168.1.6",   "192.168.1.106", "admin",   "legacypass06", "server6"),
    ("192.168.1.14",  "192.168.1.122", "ops", "examplepass",       "server22"),
    ("192.168.1.100", "192.168.1.123", "ops", "examplepass",       "Pro6000"),
    ("192.168.1.102", "192.168.1.120", "ops", "examplepass",       "server20"),
]

for old_ip, new_ip, user, pw, name in ALL_IPS:
    for test_ip in [new_ip, old_ip]:
        try:
            j = paramiko.SSHClient()
            j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            j.connect(test_ip, username=user, password=pw, timeout=3)
            _, out, _ = j.exec_command("hostname -I | awk '{print $1}'", timeout=5)
            actual = out.read().decode().strip()
            j.close()
            tag = "NEW IP!" if test_ip == new_ip else "still old"
            print(f"  {name:12s}  {test_ip:>15}  reachable  actual={actual}  ({tag})")
            break
        except:
            continue
    else:
        print(f"  {name:12s}  UNREACHABLE on both {old_ip} and {new_ip}")

# ============================================================
# Part 3: Test external SSH from NAS (has public IP via Docker)
# ============================================================
print("\n" + "=" * 60)
print("PART 3: Test external SSH from NAS (via wan32nginx public net)")
print("=" * 60)

try:
    nas = paramiko.SSHClient()
    nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    nas.connect("192.168.1.29", username="admin", password="examplenaspass", timeout=5)
    print("Connected to NAS")

    # Check if NAS can reach WAN IP (it might route internally)
    _, out, _ = nas.exec_command("ip route get 203.0.113.10 2>&1 | head -3", timeout=5)
    route = out.read().decode().strip()
    print(f"  Route to WAN: {route}")

    # Test from a Docker container that has public IP
    # First check docker networks
    _, out, _ = nas.exec_command("docker ps --format '{{.Names}}' 2>&1", timeout=5)
    containers = out.read().decode().strip()
    print(f"  Containers: {containers[:100]}")

    # Test port connectivity to WAN IP from NAS itself
    WAN = "203.0.113.10"
    test_ports = [12060, 12200, 12210, 12220, 12230]
    for port in test_ports:
        _, out, _ = nas.exec_command(
            f"bash -c '(echo >/dev/tcp/{WAN}/{port}) 2>/dev/null && echo OPEN || echo CLOSED'",
            timeout=5
        )
        status = out.read().decode().strip()
        # Also try nc with timeout
        if status != "OPEN":
            _, out, _ = nas.exec_command(
                f"echo | nc -w2 {WAN} {port} 2>/dev/null | head -1 || echo TIMEOUT",
                timeout=5
            )
            banner = out.read().decode().strip()
            status = f"nc: {banner}" if banner else "CLOSED"
        print(f"  :{port}  {status}")

    # Also test: can we SSH through the port forward from NAS?
    # NAS is inside the network, so hairpin NAT might also fail from NAS
    # Let's try from the wan32nginx container which has a real public IP
    print("\n  Testing from wan32nginx container (public IP 203.0.113.12)...")
    _, out, _ = nas.exec_command(
        "docker exec wan32nginx sh -c 'echo | nc -w3 203.0.113.10 12200 2>&1 || echo TIMEOUT' 2>&1",
        timeout=10
    )
    result = out.read().decode().strip()
    print(f"  wan32nginx -> :12200: {result[:80]}")

    _, out, _ = nas.exec_command(
        "docker exec wan32nginx sh -c 'echo | nc -w3 203.0.113.10 12060 2>&1 || echo TIMEOUT' 2>&1",
        timeout=10
    )
    result = out.read().decode().strip()
    print(f"  wan32nginx -> :12060: {result[:80]}")

    _, out, _ = nas.exec_command(
        "docker exec wan32nginx sh -c 'echo | nc -w3 203.0.113.10 12230 2>&1 || echo TIMEOUT' 2>&1",
        timeout=10
    )
    result = out.read().decode().strip()
    print(f"  wan32nginx -> :12230: {result[:80]}")

    nas.close()
except Exception as e:
    print(f"  NAS Error: {e}")

print("\n=== DONE ===")
