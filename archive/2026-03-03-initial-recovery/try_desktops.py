#!/usr/bin/env python3
"""Try SSH to student desktops and all IPs using server6 as jump host."""
import paramiko

# Connect to server6 (known working)
print("Connecting to server6...")
s6 = paramiko.SSHClient()
s6.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s6.connect("192.168.1.6", username="admin", password="legacypass06", timeout=15)
print("Connected!\n")


def run(cmd, timeout=15):
    try:
        _, o, e = s6.exec_command(cmd, timeout=timeout)
        return o.read().decode("utf-8", errors="replace").strip()
    except Exception as ex:
        return f"[ERR] {ex}"


# First: list all Docker containers and their port mappings on server6
print("=" * 60)
print("Docker containers on server6:")
print("=" * 60)
print(run("docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null"))
print()

# Check /etc/hosts for any server mappings
print("=" * 60)
print("ARP table from server6 (who's on the network?):")
print("=" * 60)
print(run("ip neigh show | sort -t. -k4 -n"))
print()

# Try to find other servers by scanning common ports
print("=" * 60)
print("Quick port scan for SSH from server6:")
print("=" * 60)
# Use bash to quickly check SSH on all IPs
result = run("""
for i in 6 8 9 14 21 43 45 46 49 50 53 54 55 56 57 58 59 61 62 75 76 78 100 102; do
    timeout 2 bash -c "echo '' > /dev/tcp/192.168.1.$i/22" 2>/dev/null && echo "192.168.1.$i SSH_OPEN" || echo "192.168.1.$i SSH_CLOSED"
done
""", timeout=60)
print(result)
print()

# From server6, try key auth to all IPs
print("=" * 60)
print("SSH key auth from server6 to all IPs:")
print("=" * 60)
for last_octet in [8, 9, 14, 21, 43, 45, 46, 49, 50, 53, 54, 55, 56, 57, 58, 59, 61, 62, 75, 76, 78, 100, 102]:
    ip = f"192.168.1.{last_octet}"
    result = run(
        f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 -o BatchMode=yes admin@{ip} "
        f"'hostname 2>/dev/null && nvidia-smi -L 2>/dev/null | head -2' 2>&1 | head -5",
        timeout=8
    )
    if "denied" in result.lower() or "refused" in result.lower() or "timed out" in result.lower():
        # Try with mllab user
        result2 = run(
            f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 -o BatchMode=yes ops@{ip} "
            f"'hostname 2>/dev/null' 2>&1 | head -3",
            timeout=8
        )
        if "denied" not in result2.lower() and "refused" not in result2.lower() and result2.strip():
            print(f"  {ip}: mllab key auth -> {result2[:100]}")
        else:
            short = result[:60].replace('\n', ' ')
            print(f"  {ip}: {short}")
    else:
        lines = result.strip().replace('\n', ' | ')
        print(f"  {ip}: {lines[:120]}")

# Also try to read /etc/hosts or any config files that might list servers
print()
print("=" * 60)
print("Searching for server config files on server6:")
print("=" * 60)
for path in [
    "/etc/hosts",
    "/root/.ssh/config",
    "/home/*/.ssh/config",
    "/etc/ansible/hosts",
]:
    content = run(f"cat {path} 2>/dev/null | head -30")
    if content and "No such file" not in content:
        print(f"\n--- {path} ---")
        print(content)

s6.close()
print("\n=== DONE ===")
