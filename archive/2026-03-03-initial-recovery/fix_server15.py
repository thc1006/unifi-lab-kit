#!/usr/bin/env python3
"""Fix server15 properly - two-phase approach."""
import paramiko
import time
import socket

IP = "192.168.1.115"
PORT = 12150
USER = "admin"
OLD_PW = "legacypass13"
NEW_PW = "examplepass"

# Phase 1: Set NOPASSWD first (with old password), then change password
print("Phase 1: Set NOPASSWD with old password")
j = paramiko.SSHClient()
j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
j.connect(IP, port=PORT, username=USER, password=OLD_PW, timeout=5)
print(f"  Connected to server15 at {IP}:{PORT}")

# NOPASSWD first
cmd = (
    f"echo '{OLD_PW}' | sudo -S bash -c \""
    f"echo '{USER} ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/{USER}-nopasswd && "
    f"chmod 440 /etc/sudoers.d/{USER}-nopasswd && "
    f"visudo -cf /etc/sudoers.d/{USER}-nopasswd\" 2>&1"
)
_, out, _ = j.exec_command(cmd, timeout=8)
print(f"  NOPASSWD: {out.read().decode().strip()}")

# Verify NOPASSWD
_, out, _ = j.exec_command("sudo -n whoami 2>&1", timeout=5)
nopasswd_ok = out.read().decode().strip()
print(f"  Verify: {nopasswd_ok}")

if nopasswd_ok == "root":
    # Now change password (sudo works without password)
    j.exec_command(f"sudo bash -c \"echo '{USER}:{NEW_PW}' | chpasswd\"", timeout=8)
    time.sleep(1)
    print(f"  Password changed to {NEW_PW}")

    # Fix SSH port
    j.exec_command("sudo bash -c \"sed -i 's/^Port.*/Port 22/' /etc/ssh/sshd_config\"", timeout=8)
    time.sleep(1)
    _, out, _ = j.exec_command("grep -i ^Port /etc/ssh/sshd_config", timeout=5)
    print(f"  SSH port: {out.read().decode().strip()}")

    # Restart SSH
    print("  Restarting SSH...")
    channel = j.get_transport().open_session()
    channel.exec_command("sudo systemctl restart ssh")
    time.sleep(4)
    j.close()

    # Verify
    print("\nPhase 2: Verify")
    j2 = paramiko.SSHClient()
    j2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        j2.connect(IP, port=22, username=USER, password=NEW_PW, timeout=5)
        _, out, _ = j2.exec_command("hostname", timeout=3)
        print(f"  hostname: {out.read().decode().strip()}")
        _, out, _ = j2.exec_command("sudo -n whoami", timeout=3)
        print(f"  NOPASSWD: {out.read().decode().strip()}")
        _, out, _ = j2.exec_command(
            "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null",
            timeout=5,
        )
        print(f"  GPU: {out.read().decode().strip()}")
        j2.close()
        print("\n  ALL OK!")
    except Exception as e:
        print(f"  Port 22 verify failed: {e}")
        # Try old port
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        for p in [22, 12150]:
            r = s.connect_ex((IP, p))
            print(f"  Port {p}: {'OPEN' if r == 0 else 'CLOSED'}")
            s.close()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
else:
    print("  NOPASSWD failed, trying alternate approach...")
    j.close()

print("\n=== DONE ===")
