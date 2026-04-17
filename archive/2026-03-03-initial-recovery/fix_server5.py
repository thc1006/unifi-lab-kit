#!/usr/bin/env python3
"""Fix server5: NOPASSWD, password, SSH port, SSH key."""
import paramiko
import time
import socket

IP = "192.168.1.202"
PORT = 12050
USER = "admin"
OLD_PW = "legacypass05"
NEW_PW = "examplepass"
PUB_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEXAMPLE0000000000000000000000000000000000 admin@example.com"

j = paramiko.SSHClient()
j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
j.connect(IP, port=PORT, username=USER, password=OLD_PW, timeout=5)
print(f"Connected to server5 at {IP}:{PORT}")

# Identity
_, out, _ = j.exec_command("hostname && hostname -I", timeout=5)
print(f"Identity: {out.read().decode().strip()}")
_, out, _ = j.exec_command("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo NO-GPU", timeout=5)
print(f"GPU: {out.read().decode().strip()}")
_, out, _ = j.exec_command("cat /proc/cpuinfo | grep 'model name' | head -1", timeout=5)
print(f"CPU: {out.read().decode().strip()}")
_, out, _ = j.exec_command("free -h | grep Mem | awk '{print $2}'", timeout=5)
print(f"RAM: {out.read().decode().strip()}")
_, out, _ = j.exec_command("ip link show | grep 'link/ether' | head -1 | awk '{print $2}'", timeout=5)
mac = out.read().decode().strip()
print(f"MAC: {mac}")

# 1. NOPASSWD first
print("\n1. Setting NOPASSWD...")
cmd = (
    f"echo '{OLD_PW}' | sudo -S bash -c \""
    f"echo '{USER} ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/{USER}-nopasswd && "
    f"chmod 440 /etc/sudoers.d/{USER}-nopasswd && "
    f"visudo -cf /etc/sudoers.d/{USER}-nopasswd\" 2>&1"
)
_, out, _ = j.exec_command(cmd, timeout=8)
print(f"  {out.read().decode().strip()}")

_, out, _ = j.exec_command("sudo -n whoami 2>&1", timeout=5)
nopasswd = out.read().decode().strip()
print(f"  Verify: {nopasswd}")

if nopasswd == "root":
    # 2. Change password
    print("\n2. Changing password...")
    j.exec_command(f"sudo bash -c \"echo '{USER}:{NEW_PW}' | chpasswd\"", timeout=8)
    time.sleep(1)
    print(f"  {OLD_PW} -> {NEW_PW}")

    # 3. Fix SSH port
    print("\n3. Fixing SSH port...")
    j.exec_command("sudo bash -c \"sed -i 's/^Port.*/Port 22/' /etc/ssh/sshd_config\"", timeout=8)
    time.sleep(1)
    _, out, _ = j.exec_command("grep -i ^Port /etc/ssh/sshd_config", timeout=5)
    print(f"  {out.read().decode().strip()}")

    # 4. Deploy SSH key
    print("\n4. Deploying SSH key...")
    cmd = (
        f"mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
        f"grep -qF '{PUB_KEY}' ~/.ssh/authorized_keys 2>/dev/null || "
        f"echo '{PUB_KEY}' >> ~/.ssh/authorized_keys && "
        f"chmod 600 ~/.ssh/authorized_keys && echo OK"
    )
    _, out, _ = j.exec_command(cmd, timeout=8)
    print(f"  {out.read().decode().strip()}")

    # 5. Restart SSH
    print("\n5. Restarting SSH...")
    channel = j.get_transport().open_session()
    channel.exec_command("sudo systemctl restart ssh")
    time.sleep(4)
    j.close()

    # 6. Verify
    print("\n6. Verification...")
    j2 = paramiko.SSHClient()
    j2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        j2.connect(IP, port=22, username=USER, password=NEW_PW, timeout=5)
        _, out, _ = j2.exec_command("hostname", timeout=3)
        print(f"  hostname: {out.read().decode().strip()}")
        _, out, _ = j2.exec_command("sudo -n whoami", timeout=3)
        print(f"  NOPASSWD: {out.read().decode().strip()}")
        _, out, _ = j2.exec_command("grep hctsai ~/.ssh/authorized_keys | wc -l", timeout=3)
        print(f"  SSH key: {out.read().decode().strip()} key(s)")
        j2.close()
        print("\n  ALL OK!")
    except Exception as e:
        print(f"  Port 22 failed: {e}")

    print(f"\n  MAC: {mac} (need DHCP reservation -> .105)")

print("\n=== DONE ===")
