#!/usr/bin/env python3
"""
Fix Controller <-> USG connection by making Controller reachable at 192.168.1.60.

Plan:
1. Create Docker macvlan network on 192.168.1.x
2. Connect UniFi container to it with IP 192.168.1.60
3. Verify USG can reach Controller
4. Use Controller API to push port forward rules
"""
import paramiko
import json
import time
import socket

nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.129", username="admin", password="examplepass", timeout=5)
print("Connected to NAS")

# ============================================================
# Step 1: Check if there's already a macvlan for 192.168.1.x
# ============================================================
print("\n" + "=" * 60)
print("Step 1: Check existing Docker networks")
print("=" * 60)

_, out, _ = nas.exec_command("docker network ls", timeout=5)
print(out.read().decode().strip())

# Check if unifi container already has a 192.168.1.x connection
_, out, _ = nas.exec_command(
    'docker inspect unifi -f "{{range $k,$v := .NetworkSettings.Networks}}{{$k}}: {{$v.IPAddress}}\n{{end}}"',
    timeout=5,
)
print(f"\nUnifi current networks:\n{out.read().decode().strip()}")

# ============================================================
# Step 2: Create macvlan on 192.168.1.x and connect UniFi
# ============================================================
print("\n" + "=" * 60)
print("Step 2: Create LAN macvlan for UniFi container")
print("=" * 60)

# Find the physical interface
_, out, _ = nas.exec_command("ip route | grep default | awk '{print $5}'", timeout=5)
phy_iface = out.read().decode().strip()
print(f"Physical interface: {phy_iface}")

# Create macvlan network (if not exists)
_, out, _ = nas.exec_command(
    f'docker network create -d macvlan '
    f'--subnet=192.168.1.0/24 '
    f'--gateway=192.168.1.1 '
    f'-o parent={phy_iface} '
    f'lan_macvlan 2>&1',
    timeout=10,
)
result = out.read().decode().strip()
print(f"Create lan_macvlan: {result}")

# Connect UniFi container to it with IP 192.168.1.60
_, out, _ = nas.exec_command(
    'docker network connect --ip 192.168.1.60 lan_macvlan unifi 2>&1',
    timeout=10,
)
result = out.read().decode().strip()
print(f"Connect unifi to lan_macvlan: {result or 'OK'}")

# Verify
_, out, _ = nas.exec_command(
    'docker inspect unifi -f "{{range $k,$v := .NetworkSettings.Networks}}{{$k}}: {{$v.IPAddress}}\n{{end}}"',
    timeout=5,
)
print(f"\nUnifi networks now:\n{out.read().decode().strip()}")

# ============================================================
# Step 3: Test Controller reachable at 192.168.1.60
# ============================================================
print("\n" + "=" * 60)
print("Step 3: Verify Controller at 192.168.1.60")
print("=" * 60)

# Test from a server (not NAS - macvlan host can't reach its own container)
srv = paramiko.SSHClient()
srv.set_missing_host_key_policy(paramiko.AutoAddPolicy())
srv.connect("192.168.1.123", username="ops", password="examplepass", timeout=5)

_, out, _ = srv.exec_command(
    "curl -sk https://192.168.1.60:8443/status 2>&1 | head -3",
    timeout=10,
)
status = out.read().decode().strip()
print(f"From Pro6000: {status}")

_, out, _ = srv.exec_command(
    "curl -sk http://192.168.1.60:8080/inform 2>&1 | head -1",
    timeout=10,
)
inform = out.read().decode().strip()
print(f"Inform port (8080): {inform[:100]}")

srv.close()

# ============================================================
# Step 4: Set USG inform URL via Controller API
# ============================================================
print("\n" + "=" * 60)
print("Step 4: Update USG inform URL via Controller")
print("=" * 60)

# Login to Controller
_, out, _ = nas.exec_command(
    'docker exec unifi curl -sk -X POST https://localhost:8443/api/login '
    '-H "Content-Type: application/json" '
    "-d '{\"username\":\"mllab\",\"password\":\"examplepass\"}' "
    "-c /tmp/uc 2>&1",
    timeout=15,
)
print(f"Login: {out.read().decode().strip()[:80]}")

# Get USG device info
_, out, _ = nas.exec_command(
    "docker exec unifi curl -sk -b /tmp/uc 'https://localhost:8443/api/s/default/stat/device' 2>&1",
    timeout=15,
)
devices = json.loads(out.read().decode().strip()).get("data", [])
usg_mac = None
for d in devices:
    if d.get("type") == "ugw":
        usg_mac = d.get("mac")
        print(f"USG: {d.get('name')} mac={usg_mac} state={d.get('state')} adopted={d.get('adopted')}")
        print(f"  inform_url: {d.get('inform_url', '?')}")
        print(f"  last_seen: {d.get('last_seen', '?')}")

# Update the Controller's own inform URL setting
_, out, _ = nas.exec_command(
    'docker exec unifi curl -sk -b /tmp/uc -X PUT '
    "'https://localhost:8443/api/s/default/set/setting/super_identity' "
    '-H "Content-Type: application/json" '
    "-d '{\"hostname\":\"192.168.1.60\",\"name\":\"unifi\"}' 2>&1",
    timeout=15,
)
print(f"\nUpdate controller hostname: {out.read().decode().strip()[:200]}")

# Also update the override inform host
_, out, _ = nas.exec_command(
    'docker exec unifi curl -sk -b /tmp/uc -X PUT '
    "'https://localhost:8443/api/s/default/set/setting/super_mgmt' "
    '-H "Content-Type: application/json" '
    "-d '{\"override_inform_host\":true,\"inform_host\":\"192.168.1.60\"}' 2>&1",
    timeout=15,
)
print(f"Set inform host override: {out.read().decode().strip()[:200]}")

# Force provision USG (now that controller is on .60)
if usg_mac:
    print(f"\nForce provisioning USG ({usg_mac})...")
    _, out, _ = nas.exec_command(
        f"docker exec unifi curl -sk -b /tmp/uc -X POST "
        f"'https://localhost:8443/api/s/default/cmd/devmgr' "
        f'-H "Content-Type: application/json" '
        f"-d '{{\"cmd\":\"force-provision\",\"mac\":\"{usg_mac}\"}}' 2>&1",
        timeout=15,
    )
    print(f"  {out.read().decode().strip()[:200]}")

print("\nWaiting 30s for USG to reconnect...")
time.sleep(30)

# Check USG state again
_, out, _ = nas.exec_command(
    "docker exec unifi curl -sk -b /tmp/uc 'https://localhost:8443/api/s/default/stat/device' 2>&1",
    timeout=15,
)
devices2 = json.loads(out.read().decode().strip()).get("data", [])
for d in devices2:
    if d.get("type") == "ugw":
        state = d.get("state")
        print(f"USG state now: {state} ({'CONNECTED' if state == 1 else 'DISCONNECTED'})")
        print(f"  inform_url: {d.get('inform_url', '?')}")

# ============================================================
# Step 5: Set port forwarding via Controller API
# ============================================================
print("\n" + "=" * 60)
print("Step 5: Port forwarding")
print("=" * 60)

# Get current port forward rules
_, out, _ = nas.exec_command(
    "docker exec unifi curl -sk -b /tmp/uc 'https://localhost:8443/api/s/default/rest/portforward' 2>&1",
    timeout=15,
)
pf_raw = out.read().decode().strip()
try:
    pf_rules = json.loads(pf_raw).get("data", [])
    print(f"Existing port forward rules: {len(pf_rules)}")
    existing_ports = set()
    for r in pf_rules:
        src = r.get("src", r.get("dst_port", "?"))
        fwd = r.get("fwd", "?")
        fwd_port = r.get("fwd_port", "?")
        name = r.get("name", "?")
        print(f"  {name}: :{src} -> {fwd}:{fwd_port}")
        existing_ports.add(str(src))
except:
    print(f"Error parsing: {pf_raw[:200]}")
    existing_ports = set()

# Add new rules
new_rules = [
    ("server11-ssh", "12110", "192.168.1.111", "22"),
    ("server13-ssh", "12130", "192.168.1.113", "22"),
]

for name, dst_port, fwd_ip, fwd_port in new_rules:
    if dst_port in existing_ports:
        print(f"\n  {name} (:{dst_port}): already exists")
        continue

    print(f"\n  Adding {name}: :{dst_port} -> {fwd_ip}:{fwd_port}")
    payload = json.dumps({
        "name": name,
        "enabled": True,
        "dst_port": dst_port,
        "fwd": fwd_ip,
        "fwd_port": fwd_port,
        "proto": "tcp",
        "src": "any",
        "log": False,
    })

    # Write payload to file to avoid escaping
    sftp = nas.open_sftp()
    with sftp.open("/tmp/pf_rule.json", "w") as f:
        f.write(payload)
    sftp.close()

    _, out, _ = nas.exec_command(
        "docker exec unifi curl -sk -b /tmp/uc -X POST "
        "'https://localhost:8443/api/s/default/rest/portforward' "
        '-H "Content-Type: application/json" '
        "-d \"$(cat /tmp/pf_rule.json)\" 2>&1",
        timeout=15,
    )
    result = out.read().decode().strip()
    if '"ok"' in result:
        print(f"    OK")
    else:
        print(f"    {result[:200]}")

# Re-provision USG to apply port forward rules
if usg_mac:
    print("\nForce provisioning USG to apply port forward rules...")
    _, out, _ = nas.exec_command(
        f"docker exec unifi curl -sk -b /tmp/uc -X POST "
        f"'https://localhost:8443/api/s/default/cmd/devmgr' "
        f'-H "Content-Type: application/json" '
        f"-d '{{\"cmd\":\"force-provision\",\"mac\":\"{usg_mac}\"}}' 2>&1",
        timeout=15,
    )
    print(f"  {out.read().decode().strip()[:200]}")

nas.close()

# Wait and test
print("\nWaiting 30s for rules to take effect...")
time.sleep(30)

print("\nTesting external port forwards...")
WAN = "203.0.113.10"
test_ports = [
    (12060, "server6"), (12080, "server8"), (12090, "server9"),
    (12110, "server11"), (12130, "server13"), (12150, "server15"),
    (12200, "server20"), (12210, "server21"), (12220, "server22"),
    (12230, "Pro6000"),
]
for port, name in test_ports:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(4)
    r = s.connect_ex((WAN, port))
    if r == 0:
        try:
            banner = s.recv(256).decode().strip()[:40]
        except:
            banner = "?"
        print(f"  :{port} {name:12s}  OK  {banner}")
    else:
        print(f"  :{port} {name:12s}  CLOSED")
    s.close()

print("\n=== DONE ===")
