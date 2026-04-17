#!/usr/bin/env python3
"""
Set static IPs on server11 and server13 via netplan.
Safe approach: write config + schedule revert + apply + verify.
"""
import paramiko
import socket
import time

SERVERS = [
    {
        "name": "server11",
        "current_ip": "192.168.1.220",
        "target_ip": "192.168.1.111",
        "user": "admin",
        "pw": "examplepass",
    },
    {
        "name": "server13",
        "current_ip": "192.168.1.202",
        "target_ip": "192.168.1.113",
        "user": "admin",
        "pw": "examplepass",
    },
]

GATEWAY = "192.168.1.1"
DNS = "1.1.1.1, 8.8.8.8"

for srv in SERVERS:
    name = srv["name"]
    current = srv["current_ip"]
    target = srv["target_ip"]
    user = srv["user"]
    pw = srv["pw"]

    print("=" * 60)
    print(f"{name}: {current} -> {target}")
    print("=" * 60)

    j = paramiko.SSHClient()
    j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    j.connect(current, username=user, password=pw, timeout=5)
    print(f"  Connected to {current}")

    # 1. Find the primary network interface
    _, out, _ = j.exec_command(
        "ip route | grep default | head -1 | awk '{print $5}'", timeout=5
    )
    iface = out.read().decode().strip()
    print(f"  Interface: {iface}")

    # 2. Check current netplan config
    _, out, _ = j.exec_command("ls /etc/netplan/", timeout=5)
    netplan_files = out.read().decode().strip()
    print(f"  Netplan files: {netplan_files}")

    _, out, _ = j.exec_command("cat /etc/netplan/*.yaml 2>/dev/null", timeout=5)
    current_config = out.read().decode().strip()
    print(f"  Current config:\n    {current_config.replace(chr(10), chr(10) + '    ')}")

    # 3. Backup existing config
    j.exec_command("sudo cp /etc/netplan/*.yaml /etc/netplan/backup.yaml.bak 2>/dev/null", timeout=5)

    # 4. Write new netplan config with static IP
    # Keep DHCP as fallback: if static doesn't work, server still reachable
    netplan_config = f"""network:
  version: 2
  ethernets:
    {iface}:
      dhcp4: no
      addresses:
        - {target}/24
      routes:
        - to: default
          via: {GATEWAY}
      nameservers:
        addresses: [{DNS}]
"""

    print(f"\n  New config:")
    print(f"    {netplan_config.replace(chr(10), chr(10) + '    ')}")

    # 5. Write config file
    # Find the actual netplan filename
    _, out, _ = j.exec_command("ls /etc/netplan/*.yaml | head -1", timeout=5)
    netplan_file = out.read().decode().strip()
    if not netplan_file:
        netplan_file = "/etc/netplan/01-static.yaml"

    # Write via heredoc
    write_cmd = f"""sudo bash -c 'cat > {netplan_file} << NETPLANEOF
{netplan_config}NETPLANEOF'"""
    j.exec_command(write_cmd, timeout=5)
    time.sleep(1)

    # Verify written correctly
    _, out, _ = j.exec_command(f"cat {netplan_file}", timeout=5)
    written = out.read().decode().strip()
    print(f"\n  Written to {netplan_file}:")
    print(f"    {written.replace(chr(10), chr(10) + '    ')}")

    # 6. Safety: schedule a revert in case network dies
    # After 120s, restore backup and reboot
    revert_cmd = (
        f"sudo bash -c 'nohup sh -c \""
        f"sleep 120 && "
        f"cp /etc/netplan/backup.yaml.bak {netplan_file} && "
        f"netplan apply"
        f"\" > /tmp/netplan_revert.log 2>&1 &'"
    )
    j.exec_command(revert_cmd, timeout=5)
    print("  Safety revert scheduled (120s)")

    # 7. Apply netplan (this will disconnect us)
    print(f"\n  Applying netplan... (will disconnect from {current})")
    channel = j.get_transport().open_session()
    channel.exec_command("sudo netplan apply")
    time.sleep(5)
    j.close()

    # 8. Check new IP
    print(f"  Checking {target}...")
    for attempt in range(8):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        r = s.connect_ex((target, 22))
        if r == 0:
            try:
                banner = s.recv(256).decode().strip()
            except:
                banner = "?"
            s.close()

            # Verify identity
            j2 = paramiko.SSHClient()
            j2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            j2.connect(target, username=user, password=pw, timeout=5)
            _, out, _ = j2.exec_command("hostname && hostname -I", timeout=5)
            identity = out.read().decode().strip()

            # Cancel the revert timer
            j2.exec_command("sudo pkill -f 'sleep 120'", timeout=5)

            print(f"  SUCCESS! {target} -> {identity}")
            print(f"  Revert timer cancelled")

            # Verify internet still works
            _, out, _ = j2.exec_command(
                "ping -c 1 -W 3 8.8.8.8 2>&1 | tail -1", timeout=8
            )
            print(f"  Internet: {out.read().decode().strip()}")
            j2.close()
            break
        s.close()
        print(f"  Attempt {attempt+1}: waiting 5s...")
        time.sleep(5)
    else:
        print(f"  FAILED! {target} not reachable. Checking old IP...")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        r = s.connect_ex((current, 22))
        if r == 0:
            print(f"  Old IP {current} still works (revert may have triggered)")
        else:
            print(f"  WARNING: Both IPs unreachable! Wait 120s for auto-revert")
        s.close()

    print()

print("=== ALL DONE ===")
