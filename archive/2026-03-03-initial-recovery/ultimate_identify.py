#!/usr/bin/env python3
"""Run identification from server6 - install sshpass and nmap, then sweep."""
import paramiko
import time

S6_IP = "192.168.1.6"
S6_USER = "admin"
S6_PASS = "legacypass06"


def run(client, cmd, timeout=60):
    try:
        _, o, e = client.exec_command(cmd, timeout=timeout)
        out = o.read().decode("utf-8", errors="replace").strip()
        err = e.read().decode("utf-8", errors="replace").strip()
        return out + ("\n[ERR]:" + err if err else "")
    except Exception as ex:
        return f"[TIMEOUT/ERROR]: {ex}"


print("Connecting to server6...")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(S6_IP, username=S6_USER, password=S6_PASS, timeout=15)
print("Connected!\n")

# Install sshpass if not available
print("=" * 60)
print("Installing sshpass...")
print("=" * 60)
r = run(c, "which sshpass 2>/dev/null || (sudo apt-get update -qq && sudo apt-get install -y -qq sshpass 2>&1 | tail -3)")
print(r)
print()

# Install nmap for OS detection
print("=" * 60)
print("Checking nmap...")
print("=" * 60)
r = run(c, "which nmap 2>/dev/null || echo 'nmap not installed'")
print(r)
print()

# SSH-open IPs from scan
SSH_OPEN = ["192.168.1.14", "192.168.1.21", "192.168.1.46", "192.168.1.49",
            "192.168.1.57", "192.168.1.100", "192.168.1.102"]

# ALL passwords
PASSWORDS = {
    "legacypass01": "srv1",
    "legacypass02": "srv2",
    "legacypass03": "srv3",
    "legacypass04": "srv4",
    "legacypass05": "srv5",
    "legacypass06": "srv6",
    "legacypass16": "srv7/14",
    "legacypass07": "srv8",
    "legacypass08": "srv9",
    "legacypass09": "srv10",
    "legacypass10": "srv11",
    "legacypass11": "srv12",
    "legacypass12": "srv13",
    "legacypass13": "srv15",
    "legacypass14": "srvtemp",
    "legacypass15": "srvtemp2",
    "examplenaspass": "NAS",
    "exampleswitchpass": "switch",
    "examplewifipass": "unifi",
    "exampleunifipass": "ctrl",
    "mllabasus": "asus",
    "mllab912_router": "asus-admin",
    "legacypass01": "srv1-alt",
    "legacypass02": "srv2-alt",
}

USERS = ["admin", "ops", "root", "admin"]

print("=" * 60)
print(f"Trying all {len(USERS)} users x {len(PASSWORDS)} passwords on {len(SSH_OPEN)} IPs from server6")
print("=" * 60)

# Build a massive parallel sshpass command
# For each IP, try each user/password combo until success
script = """#!/bin/bash
identify_server() {
    local ip=$1
    for user in god mllab root admin; do
        for pass in legacypass01 legacypass02 legacypass03 legacypass04 legacypass05 legacypass06 legacypass16 legacypass07 legacypass08 legacypass09 legacypass10 legacypass11 legacypass12 legacypass13 legacypass14 legacypass15 examplenaspass exampleswitchpass examplewifipass 'exampleunifipass' mllabasus mllab912_router; do
            result=$(sshpass -p "$pass" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 -o PreferredAuthentications=password "$user@$ip" 'hostname 2>/dev/null; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null; lscpu 2>/dev/null | grep "Model name" | sed "s/.*: *//"' 2>/dev/null)
            if [ $? -eq 0 ] && [ -n "$result" ]; then
                echo "MATCH|$ip|$user|$pass|$result"
                return 0
            fi
        done
    done
    echo "FAIL|$ip"
    return 1
}

"""

for ip in SSH_OPEN:
    script += f'identify_server {ip} &\n'

script += "wait\necho ALLDONE"

# Write and run
r = run(c, f"cat > /tmp/identify.sh << 'ENDSCRIPT'\n{script}\nENDSCRIPT\nchmod +x /tmp/identify.sh", timeout=10)

print("Running identification in parallel from server6...")
r = run(c, "bash /tmp/identify.sh 2>/dev/null", timeout=120)
print(r)
print()

# Also try nmap OS detection on all IPs
print("=" * 60)
print("Nmap service scan on all IPs (if available)")
print("=" * 60)
ALL_IPS = [
    "192.168.1.8", "192.168.1.9", "192.168.1.14", "192.168.1.21",
    "192.168.1.43", "192.168.1.45", "192.168.1.46",
    "192.168.1.49", "192.168.1.50", "192.168.1.53",
    "192.168.1.54", "192.168.1.55", "192.168.1.56",
    "192.168.1.57", "192.168.1.58", "192.168.1.59",
    "192.168.1.61", "192.168.1.62", "192.168.1.75",
    "192.168.1.76", "192.168.1.78", "192.168.1.100",
    "192.168.1.102",
]
ip_list = " ".join(ALL_IPS)

# Quick nmap scan for open ports and OS detection
r = run(c, f"nmap -sV -O --osscan-guess -T4 {ip_list} 2>&1 | head -300", timeout=120)
if "nmap" in r.lower() or "Nmap" in r:
    print(r[:3000])
else:
    print("nmap not available, trying alternative approach...")
    # Use /proc/net/arp or other methods
    r = run(c, f"""
for ip in {ip_list}; do
    echo "--- $ip ---"
    # Check what ports are open
    for port in 22 80 443 3389 8080 5900; do
        timeout 1 bash -c "echo '' > /dev/tcp/$ip/$port" 2>/dev/null && echo "  port $port OPEN"
    done
    # Try to get SSH banner
    timeout 2 bash -c "echo '' | nc -w2 $ip 22 2>/dev/null" | head -1 && true
done
""", timeout=120)
    print(r[:3000])

c.close()
print("\n=== DONE ===")
