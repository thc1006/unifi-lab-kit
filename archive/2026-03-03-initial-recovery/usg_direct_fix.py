#!/usr/bin/env python3
"""Directly fix port-forward on USG via EdgeOS CLI. Delete old, add new."""
import paramiko
import time
import socket

j = paramiko.SSHClient()
j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
j.connect("192.168.1.1", username="ops", password="exampleusgpass", timeout=8)
print("Connected to USG")

shell = j.invoke_shell(width=200, height=50)
time.sleep(2)
shell.recv(4096)


def cmd(c, wait=2):
    shell.send(c + "\n")
    time.sleep(wait)
    out = ""
    while shell.recv_ready():
        out += shell.recv(8192).decode(errors="replace")
    return out


# Enter configure mode
cmd("configure", 3)

# Delete ALL existing port-forward
print("Deleting all old port-forward rules...")
cmd("delete port-forward", 3)

# Create clean port-forward config
print("Creating new rules...")
cmd("set port-forward auto-firewall enable")
cmd("set port-forward hairpin-nat enable")
cmd("set port-forward wan-interface eth0")
cmd("set port-forward lan-interface eth1")

rules = [
    (1,  "srv6-ssh",  12060, "192.168.1.106", 22),
    (2,  "srv8-ssh",  12080, "192.168.1.108", 22),
    (3,  "srv9-ssh",  12090, "192.168.1.109", 22),
    (4,  "srv11-ssh", 12110, "192.168.1.111", 22),
    (5,  "srv13-ssh", 12130, "192.168.1.113", 22),
    (6,  "srv15-ssh", 12150, "192.168.1.115", 22),
    (7,  "srv20-ssh", 12200, "192.168.1.120", 22),
    (8,  "srv21-ssh", 12210, "192.168.1.121", 22),
    (9,  "srv22-ssh", 12220, "192.168.1.122", 22),
    (10, "pro6k-ssh", 12230, "192.168.1.123", 22),
    (11, "nas-ssh",   12990, "192.168.1.129", 22),
]

for idx, name, src_port, fwd_ip, fwd_port in rules:
    cmd(f"set port-forward rule {idx} description {name}")
    cmd(f"set port-forward rule {idx} forward-to address {fwd_ip}")
    cmd(f"set port-forward rule {idx} forward-to port {fwd_port}")
    cmd(f"set port-forward rule {idx} original-port {src_port}")
    cmd(f"set port-forward rule {idx} protocol tcp")
    print(f"  {idx}: :{src_port} -> {fwd_ip}:{fwd_port}")

# Commit
print("\nCommitting...")
result = cmd("commit", 15)
# Check for errors
if "Nothing to commit" in result:
    print("  Nothing to commit (already applied)")
elif "error" in result.lower() and "warning" not in result.lower():
    print(f"  ERROR: {result[-200:]}")
else:
    print("  Committed")

# Save
print("Saving...")
cmd("save", 5)
print("  Saved")

cmd("exit", 2)

# Verify from running config
print("\nVerifying iptables...")
shell.send("sudo iptables -t nat -L UBNT_PFOR_DNAT_RULES -n 2>/dev/null | grep DNAT | head -15\n")
time.sleep(3)
out = ""
while shell.recv_ready():
    out += shell.recv(8192).decode(errors="replace")
for line in out.split("\n"):
    if "DNAT" in line and "to:" in line:
        print(f"  {line.strip()}")

shell.close()
j.close()

# Test external
print("\nTesting port forwards...")
time.sleep(5)
WAN = "203.0.113.10"
all_ok = True
for port, name in [
    (12060, "server6"), (12080, "server8"), (12090, "server9"),
    (12110, "server11"), (12130, "server13"), (12150, "server15"),
    (12200, "server20"), (12210, "server21"), (12220, "server22"),
    (12230, "Pro6000"), (12990, "NAS"),
]:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(4)
    r = s.connect_ex((WAN, port))
    if r == 0:
        try:
            banner = s.recv(256).decode().strip()[:40]
        except:
            banner = "?"
        print(f"  :{port:<5} {name:12s} OK  {banner}")
    else:
        print(f"  :{port:<5} {name:12s} CLOSED")
        all_ok = False
    s.close()

if all_ok:
    print("\n*** ALL PORT FORWARDS WORKING! ***")
else:
    print("\n*** Some still closed ***")
print("\n=== DONE ===")
