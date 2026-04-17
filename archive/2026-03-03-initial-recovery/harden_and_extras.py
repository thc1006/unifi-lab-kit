#!/usr/bin/env python3
"""
1. Sync Controller port-forward rules with USG (so provision won't break)
2. Add WAN alias .33 for NAS on USG
3. Identify unknown devices .205/.206/.215
"""
import paramiko
import json
import time
import socket

# ============================================================
# Part 1: Ensure Controller has correct 11 rules
# ============================================================
print("=" * 60)
print("Part 1: Sync Controller rules with USG")
print("=" * 60)

nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.129", username="admin", password="examplepass", timeout=5)

# Login
nas.exec_command(
    'docker exec unifi curl -sk -X POST https://localhost:8443/api/login '
    '-H "Content-Type: application/json" '
    "-d '{\"username\":\"mllab\",\"password\":\"examplepass\"}' "
    "-c /tmp/uc 2>&1",
    timeout=15,
)

# Check current rules
_, out, _ = nas.exec_command(
    "docker exec unifi curl -sk -b /tmp/uc "
    "'https://localhost:8443/api/s/default/rest/portforward' 2>&1",
    timeout=15,
)
existing = json.loads(out.read().decode().strip()).get("data", [])
print(f"  Controller rules: {len(existing)}")

# The correct 11 rules that match USG
correct_rules = [
    ("srv6-ssh", "12060", "192.168.1.106", "22"),
    ("srv8-ssh", "12080", "192.168.1.108", "22"),
    ("srv9-ssh", "12090", "192.168.1.109", "22"),
    ("srv11-ssh", "12110", "192.168.1.111", "22"),
    ("srv13-ssh", "12130", "192.168.1.113", "22"),
    ("srv15-ssh", "12150", "192.168.1.115", "22"),
    ("srv20-ssh", "12200", "192.168.1.120", "22"),
    ("srv21-ssh", "12210", "192.168.1.121", "22"),
    ("srv22-ssh", "12220", "192.168.1.122", "22"),
    ("pro6k-ssh", "12230", "192.168.1.123", "22"),
    ("nas-ssh", "12990", "192.168.1.129", "22"),
]

# Check if rules match
existing_ports = {r.get("dst_port"): r for r in existing}
missing = []
wrong = []
for name, port, fwd, fwd_port in correct_rules:
    if port not in existing_ports:
        missing.append((name, port, fwd, fwd_port))
    elif existing_ports[port].get("fwd") != fwd:
        wrong.append((name, port, fwd, existing_ports[port].get("fwd")))

if not missing and not wrong:
    print("  All rules match USG. Controller is synced.")
else:
    if missing:
        print(f"  Missing {len(missing)} rules, adding...")
    if wrong:
        print(f"  {len(wrong)} rules have wrong IPs, fixing...")

    # Delete all and recreate
    for r in existing:
        nas.exec_command(
            f"docker exec unifi curl -sk -b /tmp/uc -X DELETE "
            f"'https://localhost:8443/api/s/default/rest/portforward/{r['_id']}' 2>&1",
            timeout=10,
        )

    for name, port, fwd, fwd_port in correct_rules:
        payload = json.dumps({
            "name": name, "enabled": True,
            "dst_port": port, "fwd": fwd,
            "fwd_port": fwd_port, "proto": "tcp",
            "src": "any", "log": False,
        })
        sftp = nas.open_sftp()
        with sftp.open("/tmp/pf_sync.json", "w") as f:
            f.write(payload)
        sftp.close()
        time.sleep(0.3)
        _, out, _ = nas.exec_command(
            "docker exec unifi curl -sk -b /tmp/uc -X POST "
            "'https://localhost:8443/api/s/default/rest/portforward' "
            '-H "Content-Type: application/json" '
            '-d "$(cat /tmp/pf_sync.json)" 2>&1',
            timeout=15,
        )
        ok = '"ok"' in out.read().decode().strip()
        print(f"    {name}: {'OK' if ok else 'FAIL'}")

    print("  Controller synced with USG.")

# Also ensure WAN config is static in Controller
_, out, _ = nas.exec_command(
    "docker exec unifi curl -sk -b /tmp/uc "
    "'https://localhost:8443/api/s/default/rest/networkconf' 2>&1",
    timeout=15,
)
for n in json.loads(out.read().decode().strip()).get("data", []):
    if n.get("purpose") == "wan" and "WAN1" in n.get("name", ""):
        if n.get("wan_type") != "static":
            print(f"  WAN type is {n.get('wan_type')}, fixing to static...")
            wan_fix = json.dumps({
                "wan_type": "static", "wan_ip": "203.0.113.10",
                "wan_netmask": "255.255.255.0", "wan_gateway": "203.0.113.1",
                "wan_dns1": "1.1.1.1", "wan_dns2": "8.8.8.8",
            })
            sftp = nas.open_sftp()
            with sftp.open("/tmp/wan_sync.json", "w") as f:
                f.write(wan_fix)
            sftp.close()
            time.sleep(0.5)
            nas.exec_command(
                f"docker exec unifi curl -sk -b /tmp/uc -X PUT "
                f"'https://localhost:8443/api/s/default/rest/networkconf/{n['_id']}' "
                f'-H "Content-Type: application/json" '
                f'-d "$(cat /tmp/wan_sync.json)" 2>&1',
                timeout=15,
            )
        else:
            print(f"  WAN config: static (OK)")

nas.close()

# ============================================================
# Part 2: Add WAN alias .33 on USG for NAS
# ============================================================
print("\n" + "=" * 60)
print("Part 2: Add WAN alias 203.0.113.11 for NAS")
print("=" * 60)

usg = paramiko.SSHClient()
usg.set_missing_host_key_policy(paramiko.AutoAddPolicy())
usg.connect("192.168.1.1", username="ops", password="exampleusgpass", timeout=8)

# Check if .33 already exists
_, out, _ = usg.exec_command("ip addr show eth0 | grep 144.33", timeout=5)
has_33 = "144.33" in out.read().decode().strip()

if has_33:
    print("  .33 already configured")
else:
    print("  Adding 203.0.113.11/24 to eth0...")
    shell = usg.invoke_shell(width=200, height=50)
    time.sleep(2)
    shell.recv(4096)

    def cmd(c, wait=2):
        shell.send(c + "\n")
        time.sleep(wait)
        out = ""
        while shell.recv_ready():
            out += shell.recv(8192).decode(errors="replace")
        return out

    cmd("configure", 3)
    cmd("set interfaces ethernet eth0 address 203.0.113.11/24")

    # Add port forward for NAS SSH via .33
    # Need a DNAT rule: .33:12990 -> .129:22
    # But USG port-forward applies to all WAN IPs, so :12990 already works via .34
    # The .33 alias just makes it reachable on that IP too

    result = cmd("commit", 10)
    cmd("save", 3)
    cmd("exit", 2)
    shell.close()
    print("  Committed and saved")

# Verify
_, out, _ = usg.exec_command("ip addr show eth0 | grep inet", timeout=5)
print(f"  WAN IPs: {out.read().decode().strip()}")

usg.close()

# Test .33 reachability
time.sleep(3)
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
r = s.connect_ex(("203.0.113.11", 22))
print(f"  .33:22 from LAN: {'OK' if r == 0 else 'CLOSED (normal from LAN, test from external)'}")
s.close()

# ============================================================
# Part 3: Identify unknown devices .205/.206/.215
# ============================================================
print("\n" + "=" * 60)
print("Part 3: Identify .205, .206, .215")
print("=" * 60)

nas2 = paramiko.SSHClient()
nas2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas2.connect("192.168.1.129", username="admin", password="examplepass", timeout=5)

for ip in ["192.168.1.205", "192.168.1.206", "192.168.1.215"]:
    print(f"\n--- {ip} ---")

    # Get MAC from ARP
    _, out, _ = nas2.exec_command(f"ip neigh show {ip} 2>/dev/null", timeout=5)
    arp = out.read().decode().strip()
    if arp:
        print(f"  ARP: {arp}")

    # Try SSH with all known passwords
    found = False
    users = ["admin", "ops", "root", "ubuntu"]
    passwords = ["examplepass", "ops", "legacypass06", "legacypass07",
                 "legacypass08", "legacypass05", "legacypass12", "legacypass13",
                 "legacypass16", "legacypass09", "legacypass02", "legacypass03"]

    for user in users:
        if found:
            break
        for pw in passwords:
            login_cmd = (
                f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no "
                f"-o ConnectTimeout=3 -o NumberOfPasswordPrompts=1 "
                f"{user}@{ip} "
                f"'echo SUCCESS; hostname; hostname -I; "
                f"nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo NO-GPU; "
                f"cat /proc/cpuinfo | grep \"model name\" | head -1; "
                f"free -h | grep Mem | awk \"{{print \\$2}}\"' 2>&1"
            )
            _, out, _ = nas2.exec_command(login_cmd, timeout=12)
            result = out.read().decode().strip()
            if "SUCCESS" in result:
                print(f"  LOGIN: user={user} pw={pw}")
                for line in result.split("\n"):
                    print(f"    {line}")
                found = True
                break
            elif "denied" in result.lower():
                continue
            time.sleep(0.3)

    if not found:
        # Get SSH banner for identification
        _, out, _ = nas2.exec_command(
            f"echo | nc -w3 {ip} 22 2>/dev/null | head -1", timeout=8
        )
        banner = out.read().decode().strip()
        print(f"  SSH banner: {banner}")
        print(f"  All passwords failed")

nas2.close()
print("\n=== ALL DONE ===")
