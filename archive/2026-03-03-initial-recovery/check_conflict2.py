#!/usr/bin/env python3
"""Simple IP conflict check."""
import paramiko

j = paramiko.SSHClient()
j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
j.connect("192.168.1.29", username="admin", password="examplenaspass", timeout=5)

cmds = [
    # Ping .34 then check ARP
    ("ping+arp", "ping -c 1 -W 1 203.0.113.10 >/dev/null 2>&1; ip neigh show to 203.0.113.10 2>/dev/null; arp -an 2>/dev/null | grep 144.34"),
    # Check server6 still on network?
    ("server6 .6 ping", "ping -c 1 -W 1 192.168.1.6 2>&1 | tail -2"),
    # Internet works?
    ("internet", "ping -c 1 -W 2 8.8.8.8 2>&1 | tail -2"),
    # Check UniFi Controller alerts (local curl)
    ("alerts", "curl -sk -X POST https://localhost:8443/api/login -H 'Content-Type: application/json' -d '{\"username\":\"admin@example.com\",\"password\":\"exampleunifipass\",\"ubic_2fa_token\":\"418966\"}' -c /tmp/uc 2>/dev/null && curl -sk -b /tmp/uc 'https://localhost:8443/api/s/default/stat/alarm?_limit=3&_sort=-time' 2>/dev/null | python3 -m json.tool 2>/dev/null | head -30 || echo 'alert fetch failed'"),
]

for label, cmd in cmds:
    try:
        _, out, _ = j.exec_command(cmd, timeout=10)
        result = out.read().decode().strip()
        print(f"=== {label} ===")
        print(result if result else "(empty)")
        print()
    except Exception as e:
        print(f"=== {label} === TIMEOUT\n")

j.close()
