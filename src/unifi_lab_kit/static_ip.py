"""Convert every inventory server to a static IP so reboots are predictable.

Auto-detects whether a host uses netplan or NetworkManager and writes the
appropriate config. Skips hosts that are already static.

    $ python -m unifi_lab_kit.static_ip
"""
from __future__ import annotations

import shlex
import sys
import time

from ._ssh import exec_capture, ssh_connect, tcp_probe
from .config import Settings, load_servers

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


def _sudo(password: str, cmd: str) -> str:
    return f"echo {shlex.quote(password)} | sudo -S -p '' {cmd}"


def _run_async_then_wait(client, cmd: str, wait: float = 3.0) -> None:
    """Launch `cmd` over a fresh channel, block briefly so the command has
    time to take effect before the outer SSH session is torn down.

    Used for `nmcli con up` and `netplan apply` when the interface is about
    to change IP — the foreground SSH connection will drop, so we have to
    start the command and give the kernel long enough to apply it.
    """
    ch = client.get_transport().open_session()
    ch.exec_command(cmd)
    # Poll for the command to finish OR for the session to drop (because
    # the interface went down). Either outcome is fine — we just need to
    # avoid returning while the command is still queued.
    deadline = time.time() + wait
    while time.time() < deadline:
        if ch.exit_status_ready():
            return
        time.sleep(0.2)


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

        gw_q = shlex.quote(settings.lan_gateway)
        dns_q = shlex.quote(f"{settings.dns_primary},{settings.dns_secondary}")

        if nm_active or ip_mode == "static_nmcli":
            con_name = exec_capture(c, "nmcli -t -f NAME con show --active | head -1", timeout=5)
            if not con_name:
                print(f"  {host} no active NetworkManager connection; skipping.")
                return
            con_q = shlex.quote(con_name)
            cmd = _sudo(
                password,
                f"nmcli con mod {con_q} "
                f"ipv4.method manual "
                f"ipv4.addresses {shlex.quote(target_ip + '/24')} "
                f"ipv4.gateway {gw_q} "
                f"ipv4.dns {dns_q}",
            )
            out = exec_capture(c, cmd, timeout=15)
            print(f"  nmcli: {out or 'OK'}")
            up_cmd = _sudo(password, f"nmcli con up {con_q}")
            if host == target_ip:
                exec_capture(c, up_cmd, timeout=15)
            else:
                # IP is about to change; foreground channel will die.
                # Detach onto a separate channel and wait so the command
                # has actually reached the kernel before we tear down.
                _run_async_then_wait(c, up_cmd)
        else:
            netplan_file = exec_capture(c, "ls /etc/netplan/*.yaml 2>/dev/null | head -1", timeout=5)
            if not netplan_file:
                netplan_file = "/etc/netplan/01-static.yaml"
            content = NETPLAN_TEMPLATE.format(
                iface=iface, ip=target_ip, gw=settings.lan_gateway,
                dns1=settings.dns_primary, dns2=settings.dns_secondary,
            )
            netplan_q = shlex.quote(netplan_file)
            exec_capture(c, _sudo(password, f"cp {netplan_q} {netplan_q}.bak") + " 2>/dev/null", timeout=5)
            cat_redirect = shlex.quote(f"cat > {netplan_file}")
            write = (
                f"{_sudo(password, f'bash -c {cat_redirect}')} << 'NPEOF'\n"
                f"{content}NPEOF"
            )
            exec_capture(c, write, timeout=5)
            apply_cmd = _sudo(password, "netplan apply")
            if host == target_ip:
                exec_capture(c, apply_cmd, timeout=15)
            else:
                _run_async_then_wait(c, apply_cmd)


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
