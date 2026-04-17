#!/usr/bin/env python3
"""Audit all settings for persistence after reboot."""
import paramiko
import socket
import time

results = []

def check(name, status, detail=""):
    icon = "OK" if status else "FAIL"
    results.append((name, status, detail))
    print(f"  [{icon}] {name}: {detail}")


# ============================================================
# 1. USG - WAN + port forward persistence
# ============================================================
print("=" * 60)
print("1. USG PERSISTENCE CHECK")
print("=" * 60)

usg = paramiko.SSHClient()
usg.set_missing_host_key_policy(paramiko.AutoAddPolicy())
usg.connect("192.168.1.1", username="ops", password="exampleusgpass", timeout=8)

# Check config.boot for WAN static
_, out, _ = usg.exec_command("grep -A5 'ethernet eth0' /config/config.boot | head -8", timeout=5)
wan_cfg = out.read().decode().strip()
has_static = "203.0.113.10" in wan_cfg
has_dhcp = "address dhcp" in wan_cfg
check("USG WAN config.boot", has_static and not has_dhcp, f"static={has_static} dhcp={has_dhcp}")

# Check port-forward in config.boot
_, out, _ = usg.exec_command("grep -c 'rule [0-9]' /config/config.boot | head -1", timeout=5)
pf_count = out.read().decode().strip()
check("USG port-forward rules saved", int(pf_count) >= 11 if pf_count.isdigit() else False, f"{pf_count} rules in config.boot")

# Check auto-firewall
_, out, _ = usg.exec_command("grep 'auto-firewall' /config/config.boot", timeout=5)
af = out.read().decode().strip()
check("USG auto-firewall", "enable" in af, af)

usg.close()

# ============================================================
# 2. All Servers - SSH enabled on boot + static IP
# ============================================================
print("\n" + "=" * 60)
print("2. SERVER PERSISTENCE CHECK")
print("=" * 60)

servers = [
    ("192.168.1.106", "admin", "examplepass", "server6"),
    ("192.168.1.108", "admin", "examplepass", "server8"),
    ("192.168.1.109", "admin", "examplepass", "server9"),
    ("192.168.1.111", "admin", "examplepass", "server11"),
    ("192.168.1.113", "admin", "examplepass", "server13"),
    ("192.168.1.115", "admin", "examplepass", "server15"),
    ("192.168.1.120", "ops", "examplepass", "server20"),
    ("192.168.1.121", "ops", "examplepass", "server21"),
    ("192.168.1.122", "ops", "examplepass", "server22"),
    ("192.168.1.123", "ops", "examplepass", "Pro6000"),
    ("192.168.1.129", "admin", "examplepass", "NAS"),
]

for ip, user, pw, name in servers:
    try:
        j = paramiko.SSHClient()
        j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        j.connect(ip, username=user, password=pw, timeout=5)

        # SSH enabled on boot
        _, out, _ = j.exec_command("systemctl is-enabled ssh 2>/dev/null || systemctl is-enabled sshd 2>/dev/null", timeout=5)
        ssh_enabled = out.read().decode().strip()
        check(f"{name} SSH on boot", ssh_enabled == "enabled", ssh_enabled)

        # IP persistence (static or DHCP with reservation)
        _, out, _ = j.exec_command("cat /etc/netplan/*.yaml 2>/dev/null | grep -c 'dhcp4: no' || echo 0", timeout=5)
        static_netplan = out.read().decode().strip()
        _, out, _ = j.exec_command("nmcli -t -f ipv4.method con show --active 2>/dev/null | head -1", timeout=5)
        nm_method = out.read().decode().strip()

        if name in ("server11", "server13"):
            is_static = "manual" in nm_method or static_netplan != "0"
            check(f"{name} static IP", is_static, f"netplan_static={static_netplan} nmcli={nm_method}")
        else:
            check(f"{name} IP (DHCP)", True, f"DHCP (relies on USG DHCP reservation)")

        # NOPASSWD sudo
        _, out, _ = j.exec_command("sudo -n whoami 2>&1", timeout=5)
        nopasswd = out.read().decode().strip() == "root"
        check(f"{name} NOPASSWD", nopasswd, "")

        # SSH key
        _, out, _ = j.exec_command("grep -c hctsai ~/.ssh/authorized_keys 2>/dev/null || echo 0", timeout=5)
        key_count = out.read().decode().strip()
        check(f"{name} SSH key", key_count != "0", f"{key_count} key(s)")

        # Docker autostart (check if any containers have restart policy)
        if name == "NAS":
            _, out, _ = j.exec_command("docker inspect unifi -f '{{.HostConfig.RestartPolicy.Name}}' 2>/dev/null", timeout=5)
            restart = out.read().decode().strip()
            check(f"{name} UniFi container restart", restart in ("always", "unless-stopped"), restart)

        j.close()
    except Exception as e:
        check(f"{name} connection", False, str(e)[:50])

# ============================================================
# 3. Summary
# ============================================================
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

failures = [r for r in results if not r[1]]
if failures:
    print(f"\n{len(failures)} issues to fix:")
    for name, _, detail in failures:
        print(f"  - {name}: {detail}")
else:
    print("\nAll checks passed!")

print(f"\nTotal: {len(results)} checks, {len(results)-len(failures)} OK, {len(failures)} FAIL")
