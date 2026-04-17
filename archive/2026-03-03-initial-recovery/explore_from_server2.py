#!/usr/bin/env python3
"""SSH into server2 and explore the internal network to identify other servers."""
import paramiko
import time

HOST = "192.168.1.102"
USER = "admin"
PASS = "legacypass02"


def run_cmd(client, cmd, timeout=15):
    try:
        _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        return (out + (("\n[STDERR]: " + err) if err.strip() else "")).strip()
    except Exception as e:
        return f"[ERROR]: {e}"


print(f"Connecting to {USER}@{HOST}...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)
print("Connected!\n")

commands = [
    ("hostname", "主機名稱"),
    ("cat /etc/hostname", "hostname 檔案"),
    ("uname -a", "系統資訊"),
    ("cat /etc/hosts", "hosts 檔案"),
    ("cat /etc/ssh/ssh_config 2>/dev/null | head -30", "SSH config"),
    ("ls -la ~/.ssh/ 2>/dev/null", "SSH 金鑰"),
    ("cat ~/.ssh/known_hosts 2>/dev/null | head -50", "Known hosts"),
    ("cat ~/.ssh/config 2>/dev/null", "SSH user config"),
    ("cat ~/.bash_history 2>/dev/null | grep -i ssh | tail -30", "SSH 歷史"),
    ("ip neigh show | sort", "ARP/Neighbor 表"),
    ("arp -a 2>/dev/null | sort", "ARP 表 (legacy)"),
    ("cat /etc/resolv.conf", "DNS 設定"),
    ("ip addr show | grep 'inet '", "IP 設定"),
    ("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null", "GPU 資訊"),
    ("lscpu | head -15", "CPU 資訊"),
    ("free -h | head -3", "記憶體"),
    ("df -h / /home 2>/dev/null", "磁碟空間"),
    ("cat /etc/netplan/*.yaml 2>/dev/null || cat /etc/network/interfaces 2>/dev/null || nmcli dev show 2>/dev/null | head -30", "網路設定"),
    ("getent passwd | grep -E '(god|mllab)' | head -5", "使用者帳號"),
    ("sudo -n cat /etc/shadow 2>/dev/null | grep god", "密碼 hash (if sudo)"),
]

for cmd, desc in commands:
    print(f"{'='*60}")
    print(f">>> {cmd}")
    print(f"    ({desc})")
    print(f"{'='*60}")
    result = run_cmd(client, cmd)
    print(result if result else "(empty)")
    print()

# Try to ping sweep and identify other servers
print("=" * 60)
print(">>> Ping sweep 192.168.1.1-120")
print("=" * 60)
result = run_cmd(client, """
for i in $(seq 1 120); do
    (ping -c1 -W1 192.168.1.$i > /dev/null 2>&1 && echo "192.168.1.$i ALIVE") &
done
wait
""", timeout=30)
print(result if result else "(empty)")
print()

# Try to SSH to other known IPs with same credentials
print("=" * 60)
print(">>> Try SSH from server2 to other servers (with same password)")
print("=" * 60)
other_ips = [
    "192.168.1.6", "192.168.1.8", "192.168.1.9",
    "192.168.1.43", "192.168.1.45", "192.168.1.46",
    "192.168.1.49", "192.168.1.50", "192.168.1.53",
    "192.168.1.54", "192.168.1.55", "192.168.1.56",
    "192.168.1.57", "192.168.1.58", "192.168.1.59",
    "192.168.1.61", "192.168.1.62", "192.168.1.75",
    "192.168.1.76", "192.168.1.100",
]

# Check if SSH key auth works (servers might trust each other)
for ip in other_ips:
    result = run_cmd(client,
        f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 -o BatchMode=yes admin@{ip} 'hostname && nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo NO_GPU' 2>&1 | head -5",
        timeout=10
    )
    if result and "Connection refused" not in result and "timed out" not in result and "No route" not in result:
        print(f"  {ip}: {result}")
    else:
        print(f"  {ip}: no key auth or no SSH")

client.close()
print("\n=== DONE ===")
