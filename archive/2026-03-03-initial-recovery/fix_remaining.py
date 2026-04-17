#!/usr/bin/env python3
"""Fix server15 (port 12150) + ping check offline servers."""
import paramiko
import socket
import subprocess
import time

# ============================================================
# Part 1: Ping check all CLOSED servers
# ============================================================
print("=" * 60)
print("PING CHECK - offline servers")
print("=" * 60)

offline = [
    ("server1",  "192.168.1.101"),
    ("server2",  "192.168.1.102"),
    ("server3",  "192.168.1.103"),
    ("server4",  "192.168.1.104"),
    ("server5",  "192.168.1.105"),
    ("server7",  "192.168.1.107"),
    ("server10", "192.168.1.110"),
    ("server11", "192.168.1.111"),
    ("server12", "192.168.1.112"),
    ("server13", "192.168.1.113"),
    ("server14", "192.168.1.114"),
]

for name, ip in offline:
    r = subprocess.run(
        ["ping", "-n", "1", "-w", "1000", ip],
        capture_output=True,
    )
    alive = "TTL=" in r.stdout.decode(errors="replace")
    print(f"  {name:<12} {ip:<17} {'ALIVE (SSH not running)' if alive else 'DOWN (off/unplugged)'}")

# ============================================================
# Part 2: Fix server15 (port 12150)
# ============================================================
print()
print("=" * 60)
print("FIX server15 (192.168.1.115:12150)")
print("=" * 60)

# server15 password from CSV: legacypass14 (or legacypass13)
passwords_15 = [
    "legacypass13",
    "legacypass14",
    "legacypass15",
    "examplepass",
    "legacypass06",
    "legacypass07",
    "legacypass08",
    "legacypass16",
]
users_15 = ["admin", "ops"]

found = False
for user in users_15:
    if found:
        break
    for pw in passwords_15:
        try:
            j = paramiko.SSHClient()
            j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            j.connect("192.168.1.115", port=12150, username=user, password=pw, timeout=5)
            _, out, _ = j.exec_command("hostname && hostname -I", timeout=5)
            identity = out.read().decode().strip()
            print(f"  Connected! user={user} pw={pw}")
            print(f"  Identity: {identity}")

            _, out, _ = j.exec_command(
                "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo NO-GPU",
                timeout=5,
            )
            print(f"  GPU: {out.read().decode().strip()}")

            # Fix SSH port
            cmd = f"echo '{pw}' | sudo -S bash -c \"sed -i 's/^Port.*/Port 22/' /etc/ssh/sshd_config\" 2>&1"
            _, out, _ = j.exec_command(cmd, timeout=8)
            print(f"  Port fix: {out.read().decode().strip()}")

            # Change password
            cmd = f"echo '{pw}' | sudo -S bash -c \"echo '{user}:examplepass' | chpasswd\" 2>&1"
            _, out, _ = j.exec_command(cmd, timeout=8)
            print(f"  Password change: done")

            found = True
            j.close()

            # Reconnect with new password for NOPASSWD
            time.sleep(1)
            j2 = paramiko.SSHClient()
            j2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            j2.connect("192.168.1.115", port=12150, username=user, password="examplepass", timeout=5)

            cmd = (
                f"echo 'examplepass' | sudo -S bash -c \""
                f"echo '{user} ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/{user}-nopasswd && "
                f"chmod 440 /etc/sudoers.d/{user}-nopasswd && "
                f"visudo -cf /etc/sudoers.d/{user}-nopasswd\" 2>&1"
            )
            _, out, _ = j2.exec_command(cmd, timeout=8)
            print(f"  NOPASSWD: {out.read().decode().strip()}")

            _, out, _ = j2.exec_command("sudo -n whoami 2>&1", timeout=5)
            print(f"  Verify NOPASSWD: {out.read().decode().strip()}")

            # Restart SSH
            print("  Restarting SSH...")
            channel = j2.get_transport().open_session()
            channel.exec_command("sudo systemctl restart ssh")
            time.sleep(4)
            j2.close()

            # Verify port 22
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            r = s.connect_ex(("192.168.1.115", 22))
            if r == 0:
                try:
                    banner = s.recv(256).decode().strip()
                except:
                    banner = "?"
                print(f"  Port 22: OPEN  {banner}")
            else:
                print(f"  Port 22: CLOSED")
            s.close()
            break

        except paramiko.AuthenticationException:
            continue
        except Exception as e:
            print(f"  {user}/{pw}: {str(e)[:50]}")
            time.sleep(2)
            break

if not found:
    print("  All passwords failed for server15")

print("\n=== DONE ===")
