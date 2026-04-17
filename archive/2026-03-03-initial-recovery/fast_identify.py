#!/usr/bin/env python3
"""Fast identify: sshpass on NAS + nmap, run with proper timeout."""
import paramiko

NAS_IP = "192.168.1.29"
NAS_USER = "admin"
NAS_PASS = "examplenaspass"

def run(c, cmd, timeout=30):
    try:
        _, o, e = c.exec_command(cmd, timeout=timeout)
        return o.read().decode("utf-8", errors="replace").strip()
    except Exception as ex:
        return f"[ERR:{ex}]"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(NAS_IP, username=NAS_USER, password=NAS_PASS, timeout=15)
print("NAS connected. sshpass ready.\n")

# Write comprehensive script on NAS
script = r"""#!/bin/bash
SSH_IPS="192.168.1.14 192.168.1.21 192.168.1.46 192.168.1.49 192.168.1.57 192.168.1.100 192.168.1.102"
PASSWORDS="legacypass01 legacypass02 legacypass03 legacypass04 legacypass05 legacypass06 legacypass16 legacypass07 legacypass08 legacypass09 legacypass10 legacypass11 legacypass12 legacypass13 legacypass14 legacypass15 examplenaspass exampleswitchpass examplewifipass"
USERS="god mllab root"

for ip in $SSH_IPS; do
    found=0
    for user in $USERS; do
        [ $found -eq 1 ] && break
        for pass in $PASSWORDS; do
            result=$(sshpass -p "$pass" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=2 -o PreferredAuthentications=password -o NumberOfPasswordPrompts=1 "$user@$ip" 'hostname' 2>/dev/null)
            if [ $? -eq 0 ] && [ -n "$result" ]; then
                # Get more info
                info=$(sshpass -p "$pass" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 "$user@$ip" 'echo "HOST=$(hostname)|GPU=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo NONE)|CPU=$(lscpu 2>/dev/null | grep "Model name" | sed "s/.*: *//" | head -1)|MEM=$(free -h 2>/dev/null | grep Mem | awk "{print \$2}")|MAC=$(ip link show 2>/dev/null | grep "link/ether" | head -1 | awk "{print \$2}")"' 2>/dev/null)
                echo "MATCH|$ip|$user|$pass|$info"
                found=1
                break
            fi
        done
    done
    [ $found -eq 0 ] && echo "FAIL|$ip"
done
echo "===ALLDONE==="
"""

run(c, f"cat > /tmp/fast_id.sh << 'ENDOFSCRIPT'\n{script}\nENDOFSCRIPT\nchmod +x /tmp/fast_id.sh")

print("=" * 60)
print("Running sshpass identification from NAS (sequential, reliable)...")
print("=" * 60)
# Run with long timeout - sequential so it won't timeout
r = run(c, "bash /tmp/fast_id.sh 2>/dev/null", timeout=300)
print(r)
print()

# Also install and run nmap while we're here
print("=" * 60)
print("Installing nmap...")
print("=" * 60)
r = run(c, "echo 'examplenaspass' | sudo -S apt-get install -y -qq nmap 2>&1 | tail -3", timeout=120)
print(r)

nmap = run(c, "which nmap 2>/dev/null")
if nmap and "nmap" in nmap:
    print("\nRunning nmap OS detection on all IPs...")
    all_ips = "192.168.1.8 192.168.1.9 192.168.1.14 192.168.1.21 192.168.1.43 192.168.1.45 192.168.1.46 192.168.1.49 192.168.1.50 192.168.1.53 192.168.1.54 192.168.1.55 192.168.1.56 192.168.1.57 192.168.1.58 192.168.1.59 192.168.1.61 192.168.1.62 192.168.1.75 192.168.1.76 192.168.1.78 192.168.1.100 192.168.1.102"
    r = run(c, f"echo 'examplenaspass' | sudo -S nmap -sV -O --osscan-guess -T5 --max-retries 1 --host-timeout 10s {all_ips} 2>&1", timeout=180)
    print(r[:5000])

c.close()
print("\n=== DONE ===")
