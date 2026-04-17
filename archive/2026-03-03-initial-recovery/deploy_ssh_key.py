#!/usr/bin/env python3
"""Deploy SSH public key to all accessible servers."""
import paramiko

PUB_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEXAMPLE0000000000000000000000000000000000 admin@example.com"

servers = [
    ("192.168.1.106", "admin",   "examplepass", "server6"),
    ("192.168.1.108", "admin",   "examplepass", "server8"),
    ("192.168.1.109", "admin",   "examplepass", "server9"),
    ("192.168.1.115", "admin",   "examplepass", "server15"),
    ("192.168.1.120", "ops", "examplepass", "server20"),
    ("192.168.1.122", "ops", "examplepass", "server22"),
    ("192.168.1.123", "ops", "examplepass", "Pro6000"),
    ("192.168.1.129", "admin",   "examplepass", "NAS"),
]

for ip, user, pw, name in servers:
    print(f"--- {name} ({ip}, user={user}) ---")
    try:
        j = paramiko.SSHClient()
        j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        j.connect(ip, username=user, password=pw, timeout=5)

        cmd = (
            f"mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
            f"touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && "
            f"grep -qF '{PUB_KEY}' ~/.ssh/authorized_keys 2>/dev/null || "
            f"echo '{PUB_KEY}' >> ~/.ssh/authorized_keys && "
            f"echo OK"
        )
        _, out, _ = j.exec_command(cmd, timeout=8)
        result = out.read().decode().strip()
        print(f"  Key deploy: {result}")

        # Verify
        _, out, _ = j.exec_command("cat ~/.ssh/authorized_keys | grep hctsai", timeout=5)
        verify = out.read().decode().strip()
        if "hctsai" in verify:
            print(f"  Verify: OK")
        else:
            print(f"  Verify: MISSING")

        j.close()
    except Exception as e:
        print(f"  ERROR: {e}")
    print()

print("=== DONE ===")
