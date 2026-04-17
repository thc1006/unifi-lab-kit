#!/usr/bin/env python3
"""Set static IPs on ALL servers to ensure persistence after reboot."""
import paramiko
import time
import socket

GATEWAY = "192.168.1.1"
DNS = "1.1.1.1, 8.8.8.8"

# server11 already static (nmcli), server13 already static (netplan)
servers = [
    ("192.168.1.106", "admin",   "examplepass", "server6",  "192.168.1.106"),
    ("192.168.1.108", "admin",   "examplepass", "server8",  "192.168.1.108"),
    ("192.168.1.109", "admin",   "examplepass", "server9",  "192.168.1.109"),
    ("192.168.1.115", "admin",   "examplepass", "server15", "192.168.1.115"),
    ("192.168.1.120", "ops", "examplepass", "server20", "192.168.1.120"),
    ("192.168.1.121", "ops", "examplepass", "server21", "192.168.1.121"),
    ("192.168.1.122", "ops", "examplepass", "server22", "192.168.1.122"),
    ("192.168.1.123", "ops", "examplepass", "Pro6000",  "192.168.1.123"),
    ("192.168.1.129", "admin",   "examplepass", "NAS",      "192.168.1.129"),
]

for current_ip, user, pw, name, target_ip in servers:
    print(f"--- {name} ({current_ip} -> {target_ip}) ---")
    try:
        j = paramiko.SSHClient()
        j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        j.connect(current_ip, username=user, password=pw, timeout=5)

        # Detect network manager type
        _, out, _ = j.exec_command("systemctl is-active NetworkManager 2>/dev/null", timeout=5)
        nm_active = out.read().decode().strip() == "active"

        # Get interface name
        _, out, _ = j.exec_command("ip route | grep default | head -1 | awk '{print $5}'", timeout=5)
        iface = out.read().decode().strip()

        # Check if already static
        _, out, _ = j.exec_command(
            f"nmcli -t -f ipv4.method con show --active 2>/dev/null | head -1", timeout=5
        )
        current_method = out.read().decode().strip()

        _, out, _ = j.exec_command(
            "cat /etc/netplan/*.yaml 2>/dev/null | grep 'dhcp4: no' | wc -l", timeout=5
        )
        netplan_static = out.read().decode().strip()

        if current_method == "ipv4.method:manual" or netplan_static != "0":
            print(f"  Already static, skipping")
            j.close()
            continue

        print(f"  Interface: {iface}, NM: {nm_active}")

        if nm_active:
            # Use nmcli (like server11)
            _, out, _ = j.exec_command(
                "nmcli -t -f NAME con show --active | head -1", timeout=5
            )
            con_name = out.read().decode().strip()
            print(f"  Connection: {con_name}")

            if con_name:
                cmd = (
                    f"sudo nmcli con mod '{con_name}' "
                    f"ipv4.method manual "
                    f"ipv4.addresses {target_ip}/24 "
                    f"ipv4.gateway {GATEWAY} "
                    f"ipv4.dns '1.1.1.1,8.8.8.8'"
                )
                _, out, _ = j.exec_command(cmd, timeout=10)
                result = out.read().decode().strip()
                print(f"  nmcli set: {result or 'OK'}")

                # Apply (will disconnect if IP changes)
                if current_ip == target_ip:
                    j.exec_command(f"sudo nmcli con up '{con_name}'", timeout=10)
                    print(f"  Applied (same IP)")
                else:
                    channel = j.get_transport().open_session()
                    channel.exec_command(f"sudo nmcli con up '{con_name}'")
                    print(f"  Applied (IP change, reconnecting...)")
        else:
            # Use netplan (like server13)
            netplan_config = f"""network:
  version: 2
  ethernets:
    {iface}:
      dhcp4: no
      addresses:
        - {target_ip}/24
      routes:
        - to: default
          via: {GATEWAY}
      nameservers:
        addresses: [{DNS}]
"""
            # Find netplan file
            _, out, _ = j.exec_command("ls /etc/netplan/*.yaml | head -1", timeout=5)
            netplan_file = out.read().decode().strip()
            if not netplan_file:
                netplan_file = "/etc/netplan/01-static.yaml"

            # Backup
            j.exec_command(f"sudo cp {netplan_file} {netplan_file}.bak 2>/dev/null", timeout=5)

            # Write
            write_cmd = f"sudo bash -c 'cat > {netplan_file}' << 'NPEOF'\n{netplan_config}NPEOF"
            j.exec_command(write_cmd, timeout=5)
            time.sleep(1)

            if current_ip == target_ip:
                j.exec_command("sudo netplan apply", timeout=10)
                print(f"  Netplan applied (same IP)")
            else:
                channel = j.get_transport().open_session()
                channel.exec_command("sudo netplan apply")
                print(f"  Netplan applied (IP change)")

        j.close()

        # Verify
        time.sleep(3)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        r = s.connect_ex((target_ip, 22))
        print(f"  Verify {target_ip}:22: {'OK' if r == 0 else 'WAITING...'}")
        s.close()

    except Exception as e:
        print(f"  ERROR: {e}")
    print()

# Final verification
print("=" * 60)
print("FINAL VERIFICATION")
print("=" * 60)

all_servers = [
    ("192.168.1.106", "server6"),
    ("192.168.1.108", "server8"),
    ("192.168.1.109", "server9"),
    ("192.168.1.111", "server11"),
    ("192.168.1.113", "server13"),
    ("192.168.1.115", "server15"),
    ("192.168.1.120", "server20"),
    ("192.168.1.121", "server21"),
    ("192.168.1.122", "server22"),
    ("192.168.1.123", "Pro6000"),
    ("192.168.1.129", "NAS"),
]

time.sleep(5)
for ip, name in all_servers:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    r = s.connect_ex((ip, 22))
    print(f"  {name:12s} {ip:>15}  {'OK' if r == 0 else 'DOWN'}")
    s.close()

print("\n=== DONE ===")
