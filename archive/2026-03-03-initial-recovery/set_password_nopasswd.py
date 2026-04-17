#!/usr/bin/env python3
"""Set all server passwords to examplepass and enable NOPASSWD sudo."""
import paramiko
import sys

NEW_PW = "examplepass"

servers = [
    ("192.168.1.106", "admin",   "legacypass06", "server6"),
    ("192.168.1.120", "ops", "examplepass",        "server20"),
    ("192.168.1.122", "ops", "examplepass",        "server22"),
    ("192.168.1.123", "ops", "examplepass",        "Pro6000"),
    ("192.168.1.129", "admin",   "examplenaspass",     "NAS"),
]

for ip, user, old_pw, name in servers:
    print(f"--- {name} ({ip}, user={user}) ---")
    try:
        j = paramiko.SSHClient()
        j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        j.connect(ip, username=user, password=old_pw, timeout=5)

        # 1. Change password if different
        if old_pw != NEW_PW:
            cmd = f"echo '{old_pw}' | sudo -S bash -c \"echo '{user}:{NEW_PW}' | chpasswd\" 2>&1"
            _, out, _ = j.exec_command(cmd, timeout=8)
            result = out.read().decode().strip()
            # Filter out the [sudo] prompt line
            lines = [l for l in result.split("\n") if not l.startswith("[sudo]")]
            clean = "\n".join(lines).strip()
            if "error" in clean.lower() or "fail" in clean.lower():
                print(f"  Password change FAILED: {clean}")
            else:
                print(f"  Password changed: {old_pw} -> {NEW_PW}")
        else:
            print(f"  Password already {NEW_PW}")

        # 2. Set NOPASSWD sudo
        sudoers_line = f"{user} ALL=(ALL) NOPASSWD: ALL"
        sudoers_file = f"/etc/sudoers.d/{user}-nopasswd"
        cmd = (
            f"echo '{old_pw}' | sudo -S bash -c \""
            f"echo '{sudoers_line}' > {sudoers_file} && "
            f"chmod 440 {sudoers_file} && "
            f"visudo -cf {sudoers_file}"
            f"\" 2>&1"
        )
        _, out, _ = j.exec_command(cmd, timeout=8)
        result = out.read().decode().strip()
        if "parsed OK" in result.lower():
            print(f"  NOPASSWD sudo: OK ({sudoers_file})")
        else:
            print(f"  NOPASSWD sudo result: {result}")

        j.close()

    except Exception as e:
        print(f"  ERROR: {e}")
    print()

# Verification round
print("=" * 60)
print("VERIFICATION (reconnect with new password)")
print("=" * 60)

verify_servers = [
    ("192.168.1.106", "admin",   "server6"),
    ("192.168.1.120", "ops", "server20"),
    ("192.168.1.122", "ops", "server22"),
    ("192.168.1.123", "ops", "Pro6000"),
    ("192.168.1.129", "admin",   "NAS"),
]

for ip, user, name in verify_servers:
    try:
        j = paramiko.SSHClient()
        j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        j.connect(ip, username=user, password=NEW_PW, timeout=5)
        _, out, _ = j.exec_command("sudo -n whoami 2>&1", timeout=5)
        sudo_result = out.read().decode().strip()
        if sudo_result == "root":
            print(f"  {name:12s}  login(pw={NEW_PW}): OK  sudo NOPASSWD: OK")
        else:
            print(f"  {name:12s}  login(pw={NEW_PW}): OK  sudo NOPASSWD: FAIL ({sudo_result[:40]})")
        j.close()
    except Exception as e:
        print(f"  {name:12s}  login FAILED: {e}")

print("\n=== DONE ===")
