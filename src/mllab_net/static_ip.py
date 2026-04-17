"""Convert every inventory server to a static IP so reboots are predictable.

Auto-detects whether a host uses netplan or NetworkManager and writes the
appropriate config. Skips hosts that are already static.

    $ python -m mllab_net.static_ip
"""
from __future__ import annotations

import sys
import time

from .config import Settings, load_servers
from ._ssh import exec_capture, ssh_connect, tcp_probe


NETPLAN_TEMPLATE = """network:
  version: 2
  ethernets:
    {iface}:
      dhcp4: no
      addresses:
        - {ip}/24
      routes:
        - to: default
          via: {gw}
      nameservers:
        addresses: [{dns1}, {dns2}]
"""


def apply_one(host: str, user: str, password: str, settings: Settings, target_ip: str, ip_mode: str) -> None:
    with ssh_connect(host, user, password) as c:
        nm_active = exec_capture(c, "systemctl is-active NetworkManager 2>/dev/null", timeout=5) == "active"
        iface = exec_capture(c, "ip route | awk '/default/{print $5; exit}'", timeout=5) or "eth0"

        nm_method = exec_capture(
            c, "nmcli -t -f ipv4.method con show --active 2>/dev/null | head -1", timeout=5,
        )
        netplan_static = exec_capture(
            c, "cat /etc/netplan/*.yaml 2>/dev/null | grep -c 'dhcp4: no' || echo 0", timeout=5,
        )
        if "manual" in nm_method or netplan_static != "0":
            print(f"  {host} already static, skipping.")
            return

        print(f"  iface={iface} nm_active={nm_active}")

        if nm_active or ip_mode == "static_nmcli":
            con_name = exec_capture(c, "nmcli -t -f NAME con show --active | head -1", timeout=5)
            if not con_name:
                print(f"  {host} no active NetworkManager connection; skipping.")
                return
            cmd = (
                f"echo '{password}' | sudo -S nmcli con mod '{con_name}' "
                f"ipv4.method manual "
                f"ipv4.addresses {target_ip}/24 "
                f"ipv4.gateway {settings.lan_gateway} "
                f"ipv4.dns '{settings.dns_primary},{settings.dns_secondary}'"
            )
            out = exec_capture(c, cmd, timeout=15)
            print(f"  nmcli: {out or 'OK'}")
            if host == target_ip:
                exec_capture(c, f"echo '{password}' | sudo -S nmcli con up '{con_name}'", timeout=15)
            else:
                # starting an async session because connection will drop on IP change
                ch = c.get_transport().open_session()
                ch.exec_command(f"echo '{password}' | sudo -S nmcli con up '{con_name}'")
        else:
            netplan_file = exec_capture(c, "ls /etc/netplan/*.yaml 2>/dev/null | head -1", timeout=5)
            if not netplan_file:
                netplan_file = "/etc/netplan/01-static.yaml"
            content = NETPLAN_TEMPLATE.format(
                iface=iface, ip=target_ip, gw=settings.lan_gateway,
                dns1=settings.dns_primary, dns2=settings.dns_secondary,
            )
            exec_capture(c, f"echo '{password}' | sudo -S cp {netplan_file} {netplan_file}.bak 2>/dev/null", timeout=5)
            write = (
                f"echo '{password}' | sudo -S bash -c 'cat > {netplan_file}' << 'NPEOF'\n"
                f"{content}NPEOF"
            )
            exec_capture(c, write, timeout=5)
            if host == target_ip:
                exec_capture(c, f"echo '{password}' | sudo -S netplan apply", timeout=15)
            else:
                ch = c.get_transport().open_session()
                ch.exec_command(f"echo '{password}' | sudo -S netplan apply")


def main(argv: list[str] | None = None) -> int:
    settings = Settings.load()
    servers = load_servers()

    print(f"Converting {len(servers)} server(s) to static IP…")
    for srv in servers:
        print(f"\n--- {srv.name} (current {srv.internal_ip} → target {srv.internal_ip}) ---")
        user = srv.ssh_user(settings)
        try:
            apply_one(srv.internal_ip, user, settings.server_pass,
                      settings, srv.internal_ip, srv.ip_mode)
        except Exception as e:
            print(f"  ERROR: {e}")

    print("\nWaiting 5 s, then verifying reachability…")
    time.sleep(5)
    for srv in servers:
        ok, _ = tcp_probe(srv.internal_ip, 22)
        print(f"  {srv.name:12s} {srv.internal_ip:>15}  {'OK' if ok else 'DOWN'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
