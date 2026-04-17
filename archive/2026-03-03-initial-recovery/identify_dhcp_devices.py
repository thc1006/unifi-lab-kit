#!/usr/bin/env python3
"""Identify new devices in DHCP range with SSH open."""
import paramiko
import time

ssh_devices = [
    ("192.168.1.200", 22),
    ("192.168.1.205", 22),
    ("192.168.1.206", 22),
    ("192.168.1.215", 22),
]

users = ["admin", "ops", "root"]
passwords = [
    "examplepass",
    "legacypass06",
    "legacypass07",
    "legacypass08",
    "legacypass16",
    "legacypass09",
    "legacypass10",
    "legacypass11",
    "legacypass12",
    "legacypass13",
    "legacypass04",
    "legacypass05",
    "legacypass02",
    "legacypass03",
    "legacypass01",
    "legacypass14",
    "legacypass15",
    "examplenaspass",
    "exampleswitchpass",
]

for ip, port in ssh_devices:
    print(f"=== {ip}:{port} ===")
    found = False
    for user in users:
        if found:
            break
        for pw in passwords:
            try:
                j = paramiko.SSHClient()
                j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                j.connect(ip, port=port, username=user, password=pw, timeout=5,
                         banner_timeout=5, auth_timeout=5)
                _, out, _ = j.exec_command("hostname", timeout=3)
                hostname = out.read().decode().strip()
                _, out, _ = j.exec_command("hostname -I", timeout=3)
                ips = out.read().decode().strip()
                _, out, _ = j.exec_command(
                    "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo NO-GPU",
                    timeout=5,
                )
                gpu = out.read().decode().strip()
                _, out, _ = j.exec_command("cat /proc/cpuinfo | grep 'model name' | head -1", timeout=3)
                cpu = out.read().decode().strip().split(":")[-1].strip() if out else "?"
                _, out, _ = j.exec_command("free -h | grep Mem | awk '{print $2}'", timeout=3)
                ram = out.read().decode().strip()
                _, out, _ = j.exec_command("ip link show | grep 'link/ether' | head -1 | awk '{print $2}'", timeout=3)
                mac = out.read().decode().strip()

                print(f"  user={user}  pw={pw}")
                print(f"  hostname={hostname}  IPs={ips}")
                print(f"  CPU={cpu}")
                print(f"  RAM={ram}  GPU={gpu}")
                print(f"  MAC={mac}")
                j.close()
                found = True
                break
            except paramiko.AuthenticationException:
                continue
            except Exception as e:
                print(f"  {user}/{pw}: {str(e)[:40]}")
                time.sleep(2)
                break
    if not found:
        print("  All passwords failed")
    print()
