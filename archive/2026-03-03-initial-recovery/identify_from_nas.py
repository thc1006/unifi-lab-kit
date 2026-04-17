#!/usr/bin/env python3
"""Use NAS (which has sudo + Docker) to identify servers via sshpass/expect/python."""
import paramiko

NAS_IP = "192.168.1.29"
NAS_USER = "admin"
NAS_PASS = "examplenaspass"


def run(client, cmd, timeout=60):
    try:
        _, o, e = client.exec_command(cmd, timeout=timeout)
        out = o.read().decode("utf-8", errors="replace").strip()
        err = e.read().decode("utf-8", errors="replace").strip()
        return out + ("\n[ERR]:" + err if err else "")
    except Exception as ex:
        return f"[TIMEOUT/ERROR]: {ex}"


print("Connecting to NAS...")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(NAS_IP, username=NAS_USER, password=NAS_PASS, timeout=15)
print("Connected!\n")

# Check sudo access
print("Testing sudo...")
r = run(c, "echo 'examplenaspass' | sudo -S whoami 2>/dev/null")
print(f"sudo: {r}")

# Check available tools
print("\nChecking tools...")
for tool in ["sshpass", "nmap", "expect", "python3", "nc"]:
    r = run(c, f"which {tool} 2>/dev/null || echo '{tool} NOT FOUND'")
    print(f"  {tool}: {r}")

# Install sshpass via sudo
print("\nInstalling sshpass...")
r = run(c, "echo 'examplenaspass' | sudo -S apt-get install -y -qq sshpass 2>&1 | tail -5")
print(r)

# Install nmap
print("\nInstalling nmap...")
r = run(c, "echo 'examplenaspass' | sudo -S apt-get install -y -qq nmap 2>&1 | tail -5")
print(r)

SSH_OPEN = ["192.168.1.14", "192.168.1.21", "192.168.1.46", "192.168.1.49",
            "192.168.1.57", "192.168.1.100", "192.168.1.102"]

ALL_IPS = "192.168.1.8 192.168.1.9 192.168.1.14 192.168.1.21 192.168.1.43 192.168.1.45 192.168.1.46 192.168.1.49 192.168.1.50 192.168.1.53 192.168.1.54 192.168.1.55 192.168.1.56 192.168.1.57 192.168.1.58 192.168.1.59 192.168.1.61 192.168.1.62 192.168.1.75 192.168.1.76 192.168.1.78 192.168.1.100 192.168.1.102"

# Check if sshpass is available now
r = run(c, "which sshpass 2>/dev/null")
if "sshpass" in r:
    print(f"\nsshpass available at: {r}")
    # Run identification
    script = """#!/bin/bash
identify() {
    local ip=$1
    for user in god mllab root admin; do
        for pass in legacypass01 legacypass02 legacypass03 legacypass04 legacypass05 legacypass06 legacypass16 legacypass07 legacypass08 legacypass09 legacypass10 legacypass11 legacypass12 legacypass13 legacypass14 legacypass15 examplenaspass exampleswitchpass examplewifipass; do
            result=$(sshpass -p "$pass" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 -o PreferredAuthentications=password "$user@$ip" 'hostname 2>/dev/null; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null; lscpu 2>/dev/null | grep "Model name" | sed "s/.*: *//"' 2>/dev/null)
            if [ $? -eq 0 ] && [ -n "$result" ]; then
                echo "MATCH|$ip|$user|$pass|$(echo $result | tr '\\n' '|')"
                return 0
            fi
        done
    done
    echo "FAIL|$ip"
}

"""
    for ip in SSH_OPEN:
        script += f"identify {ip} &\n"
    script += "wait\necho ALLDONE"

    run(c, f"cat > /tmp/identify.sh << 'ENDSCRIPT'\n{script}\nENDSCRIPT\nchmod +x /tmp/identify.sh")
    print("\n" + "=" * 60)
    print("Running sshpass identification from NAS (parallel)...")
    print("=" * 60)
    r = run(c, "bash /tmp/identify.sh 2>/dev/null", timeout=180)
    print(r)
else:
    print("sshpass not available, trying Python pexpect or expect...")
    # Try expect
    r = run(c, "which expect 2>/dev/null")
    if "expect" in r:
        print(f"expect available at: {r}")
    else:
        # Use Python3 with subprocess
        print("Using Python3 subprocess approach...")

# Run nmap if available
r = run(c, "which nmap 2>/dev/null")
if "nmap" in r:
    print("\n" + "=" * 60)
    print("Running nmap OS detection from NAS...")
    print("=" * 60)
    r = run(c, f"echo 'examplenaspass' | sudo -S nmap -sV -O --osscan-guess -T4 {ALL_IPS} 2>&1 | head -400", timeout=180)
    print(r[:5000])
else:
    # Fallback: port scan + SSH banner grab
    print("\n" + "=" * 60)
    print("Fallback: port scan + SSH banner from NAS")
    print("=" * 60)
    r = run(c, f"""
for ip in {ALL_IPS}; do
    echo -n "$ip: "
    # SSH banner
    banner=$(timeout 2 bash -c "cat < /dev/tcp/$ip/22" 2>/dev/null | head -1)
    if [ -n "$banner" ]; then
        echo "SSH=$banner"
    else
        echo "no_ssh"
    fi
done
""", timeout=60)
    print(r)

c.close()
print("\n=== DONE ===")
