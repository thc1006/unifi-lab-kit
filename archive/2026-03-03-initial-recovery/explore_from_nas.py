#!/usr/bin/env python3
"""SSH into NAS (which has SSH keys) and jump to all other servers to identify them."""
import paramiko

NAS_IP = "192.168.1.29"
NAS_USER = "admin"
NAS_PASS = "examplenaspass"

# All client IPs from Controller (excluding NAS, controller, switch)
ALL_IPS = [
    "192.168.1.6", "192.168.1.8", "192.168.1.9",
    "192.168.1.14", "192.168.1.21",
    "192.168.1.43", "192.168.1.45", "192.168.1.46",
    "192.168.1.49", "192.168.1.50", "192.168.1.53",
    "192.168.1.54", "192.168.1.55", "192.168.1.56",
    "192.168.1.57", "192.168.1.58", "192.168.1.59",
    "192.168.1.61", "192.168.1.62", "192.168.1.75",
    "192.168.1.76", "192.168.1.78", "192.168.1.100",
    "192.168.1.102",
]


def run_cmd(client, cmd, timeout=15):
    try:
        _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        return out
    except Exception as e:
        return f"[ERROR]: {e}"


print(f"Connecting to NAS ({NAS_USER}@{NAS_IP})...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(NAS_IP, username=NAS_USER, password=NAS_PASS, timeout=15)
print("Connected to NAS!\n")

# First check NAS's SSH key and known_hosts
print("=" * 60)
print("NAS SSH keys and Docker containers")
print("=" * 60)
print(run_cmd(client, "ls -la ~/.ssh/"))
print()
print("Docker containers on NAS:")
print(run_cmd(client, "sudo docker ps --format '{{.Names}} {{.Ports}}' 2>/dev/null || docker ps --format '{{.Names}} {{.Ports}}' 2>/dev/null"))
print()

# Try to SSH from NAS to every IP using key auth first, then password
print("=" * 60)
print("Jumping from NAS to all IPs (key auth + known passwords)")
print("=" * 60)

for ip in ALL_IPS:
    # Try key-based auth first (BatchMode=yes means no password prompt)
    result = run_cmd(client,
        f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 -o BatchMode=yes admin@{ip} "
        f"'echo HOSTNAME=$(hostname) && "
        f"echo GPU=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo NONE) && "
        f"echo CPU=$(lscpu 2>/dev/null | grep \"Model name\" | sed \"s/.*: *//\") && "
        f"echo MEM=$(free -h 2>/dev/null | grep Mem | awk \"{{print \\$2}}\") && "
        f"echo IP=$(ip -4 addr show 2>/dev/null | grep \"inet \" | grep -v 127.0.0.1 | head -1 | awk \"{{print \\$2}}\") && "
        f"echo MAC=$(ip link show 2>/dev/null | grep \"link/ether\" | head -1 | awk \"{{print \\$2}}\")' 2>&1",
        timeout=10
    )

    if "HOSTNAME=" in result:
        print(f"\n  {ip}: KEY AUTH SUCCESS!")
        for line in result.split("\n"):
            if line.strip():
                print(f"    {line.strip()}")
    elif "Permission denied" in result or "Host key" in result:
        # Key auth failed, note it
        print(f"  {ip}: key auth failed, trying password...", end=" ", flush=True)
        # Try with sshpass or expect if available
        result2 = run_cmd(client,
            f"sshpass -p 'exampleswitchpass' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 admin@{ip} "
            f"'hostname && nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null' 2>&1 | head -5",
            timeout=10
        )
        if "hostname" not in result2.lower() and "denied" not in result2.lower() and "error" not in result2.lower():
            print(f"got: {result2[:100]}")
        else:
            print("also failed")
    elif "Connection refused" in result:
        print(f"  {ip}: SSH refused")
    elif "timed out" in result or "No route" in result:
        print(f"  {ip}: unreachable")
    else:
        short = result[:80].replace("\n", " ")
        print(f"  {ip}: {short}")

print()

# Also try SSH from server6
print("=" * 60)
print("Now trying from server6 (different SSH key)")
print("=" * 60)

s6 = paramiko.SSHClient()
s6.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s6.connect("192.168.1.6", username="admin", password="legacypass06", timeout=15)
print("Connected to server6!\n")

# Check Docker containers on server6
print("Docker containers on server6:")
print(run_cmd(s6, "sudo docker ps --format '{{.Names}} {{.Ports}}' 2>/dev/null || docker ps --format '{{.Names}} {{.Ports}}' 2>/dev/null"))
print()

for ip in ALL_IPS:
    if ip == "192.168.1.6":
        continue
    result = run_cmd(s6,
        f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 -o BatchMode=yes admin@{ip} "
        f"'echo HOSTNAME=$(hostname) GPU=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo NONE)' 2>&1",
        timeout=10
    )
    if "HOSTNAME=" in result:
        print(f"  {ip}: {result.strip()}")
    elif "refused" in result.lower():
        print(f"  {ip}: refused")
    elif "denied" in result.lower():
        # skip - already tried
        pass

s6.close()
client.close()
print("\n=== DONE ===")
