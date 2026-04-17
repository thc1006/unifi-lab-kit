#!/usr/bin/env python3
"""Quick check SSH status + banner on .30 and .31."""
import paramiko

j = paramiko.SSHClient()
j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
j.connect("192.168.1.100", username="ops", password="examplepass", timeout=5)

for ip in ["192.168.1.30", "192.168.1.31"]:
    o = ip.split(".")[-1]
    # Port check
    _, out, _ = j.exec_command(f"bash -c '(echo >/dev/tcp/{ip}/22) 2>/dev/null && echo OPEN || echo CLOSED'", timeout=5)
    port = out.read().decode().strip()
    # Banner
    _, out, _ = j.exec_command(f"bash -c 'echo | nc -w2 {ip} 22 2>/dev/null || echo NO_BANNER'", timeout=5)
    banner = out.read().decode().strip()
    print(f".{o}: SSH={port}  Banner={banner}")

j.close()
