#!/usr/bin/env python3
"""Fix server21: change password, set NOPASSWD, deploy SSH key."""
import paramiko
import time

IP = "192.168.1.121"
USER = "ops"
OLD_PW = "ops"
NEW_PW = "examplepass"
PUB_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEXAMPLE0000000000000000000000000000000000 admin@example.com"

# Connect via NAS to avoid rate limit from laptop
nas = paramiko.SSHClient()
nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
nas.connect("192.168.1.129", username="admin", password="examplepass", timeout=5)
print("Connected to NAS")

# Phase 1: Set NOPASSWD first (with old password)
print("\n1. Setting NOPASSWD...")
cmd = (
    f"sshpass -p '{OLD_PW}' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 {USER}@{IP} "
    f"\"echo '{OLD_PW}' | sudo -S bash -c \\\"echo '{USER} ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/{USER}-nopasswd && "
    f"chmod 440 /etc/sudoers.d/{USER}-nopasswd && "
    f"visudo -cf /etc/sudoers.d/{USER}-nopasswd\\\"\" 2>&1"
)
_, out, _ = nas.exec_command(cmd, timeout=15)
print(f"  {out.read().decode().strip()}")

# Phase 2: Change password (using NOPASSWD sudo)
print("\n2. Changing password...")
cmd = (
    f"sshpass -p '{OLD_PW}' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 {USER}@{IP} "
    f"\"sudo bash -c \\\"echo '{USER}:{NEW_PW}' | chpasswd\\\"\" 2>&1"
)
_, out, _ = nas.exec_command(cmd, timeout=15)
result = out.read().decode().strip()
print(f"  {result if result else 'OK'}")

# Phase 3: Deploy SSH key
print("\n3. Deploying SSH key...")
cmd = (
    f"sshpass -p '{NEW_PW}' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 {USER}@{IP} "
    f"\"mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
    f"echo '{PUB_KEY}' >> ~/.ssh/authorized_keys && "
    f"sort -u ~/.ssh/authorized_keys -o ~/.ssh/authorized_keys && "
    f"chmod 600 ~/.ssh/authorized_keys && echo KEY_OK\" 2>&1"
)
_, out, _ = nas.exec_command(cmd, timeout=15)
print(f"  {out.read().decode().strip()}")

# Phase 4: Verify everything
print("\n4. Verification...")
cmd = (
    f"sshpass -p '{NEW_PW}' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 {USER}@{IP} "
    f"'echo LOGIN_OK; sudo -n whoami; hostname; "
    f"nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo NO-GPU; "
    f"grep hctsai ~/.ssh/authorized_keys > /dev/null && echo KEY_OK || echo KEY_MISSING' 2>&1"
)
_, out, _ = nas.exec_command(cmd, timeout=15)
print(f"  {out.read().decode().strip()}")

nas.close()
print("\n=== DONE ===")
