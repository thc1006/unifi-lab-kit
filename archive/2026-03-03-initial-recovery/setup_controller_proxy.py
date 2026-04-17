#!/usr/bin/env python3
"""Setup port forward so laptop can access UniFi Controller."""
import paramiko
import time

nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.129", username="admin", password="examplepass", timeout=5)
print("Connected to NAS")

# Step 1: Find how the container is actually reachable
print("\n1. Checking container connectivity...")
cmds = [
    ("Container IP", 'docker inspect unifi -f "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}"'),
    ("Container gateway", 'docker inspect unifi -f "{{range .NetworkSettings.Networks}}{{.Gateway}}{{end}}"'),
    ("NAS interfaces", "ip addr show | grep 'inet ' | grep -v 127.0.0"),
    ("Route to 192.168.54", "ip route | grep 54"),
    ("Can ping container?", "ping -c 1 -W 2 192.168.54.92 2>&1 | tail -1"),
    ("Port 8443 via docker", 'docker port unifi 2>/dev/null'),
]

for label, cmd in cmds:
    _, out, _ = nas.exec_command(cmd, timeout=8)
    result = out.read().decode().strip()
    print(f"  {label}: {result}")

# Step 2: Try socat using docker network gateway
print("\n2. Setting up socat proxy on NAS port 8443...")

# Kill existing
nas.exec_command("sudo pkill -f 'socat.*8443' 2>/dev/null", timeout=3)
time.sleep(1)

# Start socat - forward NAS:8443 -> container:8443
nas.exec_command(
    "nohup sudo socat TCP-LISTEN:8443,fork,reuseaddr TCP:192.168.54.92:8443 > /tmp/socat.log 2>&1 &",
    timeout=5,
)
time.sleep(2)

_, out, _ = nas.exec_command("ss -tlnp | grep 8443 || echo 'NOT LISTENING'", timeout=5)
listen = out.read().decode().strip()
print(f"  Listening: {listen}")

if "NOT LISTENING" in listen:
    # Alternative: use iptables DNAT
    print("\n  socat failed, trying iptables DNAT...")
    cmds_ipt = [
        "sudo iptables -t nat -A PREROUTING -p tcp -d 192.168.1.129 --dport 8443 -j DNAT --to-destination 192.168.54.92:8443",
        "sudo iptables -t nat -A POSTROUTING -p tcp -d 192.168.54.92 --dport 8443 -j MASQUERADE",
        "sudo sysctl -w net.ipv4.ip_forward=1",
    ]
    for cmd in cmds_ipt:
        _, out, _ = nas.exec_command(cmd + " 2>&1", timeout=5)
        print(f"  {cmd.split()[-1]}: {out.read().decode().strip() or 'OK'}")

nas.close()
print("\nTry opening: https://192.168.1.129:8443")
print("=== DONE ===")
