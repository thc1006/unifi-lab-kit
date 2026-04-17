#!/usr/bin/env python3
"""Fix server8: change SSH port back to 22, set password, enable NOPASSWD."""
import paramiko

IP = "192.168.1.108"
PORT = 12080
USER = "admin"
OLD_PW = "legacypass07"
NEW_PW = "examplepass"

j = paramiko.SSHClient()
j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
j.connect(IP, port=PORT, username=USER, password=OLD_PW, timeout=5)
print(f"Connected to server8 at {IP}:{PORT}")

# 1. Confirm identity
_, out, _ = j.exec_command("hostname && hostname -I", timeout=5)
print(f"Identity: {out.read().decode().strip()}")

_, out, _ = j.exec_command(
    "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo NO-GPU",
    timeout=5,
)
print(f"GPU: {out.read().decode().strip()}")

# 2. Change SSH port from 12080 to 22
print("\nChanging SSH port 12080 -> 22...")
cmd = (
    f"echo '{OLD_PW}' | sudo -S bash -c \""
    "sed -i 's/^Port 12080/Port 22/' /etc/ssh/sshd_config && "
    "grep -i '^Port' /etc/ssh/sshd_config"
    '"  2>&1'
)
_, out, _ = j.exec_command(cmd, timeout=8)
result = out.read().decode().strip()
print(f"  sshd_config: {result}")

# 3. Change password
print(f"\nChanging password: {OLD_PW} -> {NEW_PW}...")
cmd = f"echo '{OLD_PW}' | sudo -S bash -c \"echo '{USER}:{NEW_PW}' | chpasswd\" 2>&1"
_, out, _ = j.exec_command(cmd, timeout=8)
result = out.read().decode().strip()
lines = [l for l in result.split("\n") if not l.startswith("[sudo]")]
print(f"  {' '.join(lines).strip() or 'OK'}")

# 4. Set NOPASSWD sudo
print("\nSetting NOPASSWD sudo...")
sudoers_line = f"{USER} ALL=(ALL) NOPASSWD: ALL"
sudoers_file = f"/etc/sudoers.d/{USER}-nopasswd"
cmd = (
    f"echo '{OLD_PW}' | sudo -S bash -c \""
    f"echo '{sudoers_line}' > {sudoers_file} && "
    f"chmod 440 {sudoers_file} && "
    f"visudo -cf {sudoers_file}"
    '" 2>&1'
)
_, out, _ = j.exec_command(cmd, timeout=8)
result = out.read().decode().strip()
print(f"  {result}")

# 5. Restart SSH (will disconnect us)
print("\nRestarting SSH on port 22...")
channel = j.get_transport().open_session()
channel.exec_command(f"echo '{OLD_PW}' | sudo -S systemctl restart ssh")
import time
time.sleep(3)
j.close()

# 6. Verify - connect on port 22 with new password
print("\nVerifying connection on port 22 with new password...")
j2 = paramiko.SSHClient()
j2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    j2.connect(IP, port=22, username=USER, password=NEW_PW, timeout=5)
    _, out, _ = j2.exec_command("sudo -n whoami 2>&1", timeout=5)
    sudo_check = out.read().decode().strip()
    print(f"  SSH port 22: OK")
    print(f"  Password examplepass: OK")
    print(f"  NOPASSWD sudo: {'OK' if sudo_check == 'root' else 'FAIL: ' + sudo_check}")
    j2.close()
except Exception as e:
    print(f"  FAIL: {e}")

print("\n=== DONE ===")
