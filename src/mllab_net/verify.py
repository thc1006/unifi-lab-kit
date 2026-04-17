"""Post-deploy audit: WAN persistence on USG, port-forwards, SSH+sudo+key on every server.

    $ python -m mllab_net.verify
"""
from __future__ import annotations

import sys

from .config import Settings, load_servers
from ._ssh import exec_capture, ssh_connect, tcp_probe


def check_usg(settings: Settings) -> list[tuple[str, bool, str]]:
    rows: list[tuple[str, bool, str]] = []
    try:
        with ssh_connect(settings.usg_ip, settings.usg_user, settings.usg_pass) as c:
            wan_cfg = exec_capture(c, "grep -A5 'ethernet eth0' /config/config.boot | head -8", timeout=5)
            has_static = settings.wan_ip in wan_cfg
            has_dhcp = "address dhcp" in wan_cfg
            rows.append(("USG WAN config.boot", has_static and not has_dhcp,
                         f"static={has_static} dhcp={has_dhcp}"))

            pf_count = exec_capture(c, "grep -c 'rule [0-9]' /config/config.boot || echo 0", timeout=5)
            want = len(load_servers())
            count_ok = pf_count.isdigit() and int(pf_count) >= want
            rows.append(("USG port-forward persisted", count_ok, f"{pf_count} rules (want >= {want})"))

            af = exec_capture(c, "grep 'auto-firewall' /config/config.boot", timeout=5)
            rows.append(("USG auto-firewall", "enable" in af, af))
    except Exception as e:
        rows.append(("USG reachable", False, str(e)[:80]))
    return rows


def check_server(settings: Settings, srv) -> list[tuple[str, bool, str]]:
    rows: list[tuple[str, bool, str]] = []
    try:
        user = srv.ssh_user(settings)
        with ssh_connect(srv.internal_ip, user, settings.server_pass) as c:
            ssh_enabled = exec_capture(
                c, "systemctl is-enabled ssh 2>/dev/null || systemctl is-enabled sshd 2>/dev/null",
                timeout=5,
            )
            rows.append((f"{srv.name} SSH on boot", ssh_enabled == "enabled", ssh_enabled))

            if srv.ip_mode.startswith("static"):
                nm_method = exec_capture(
                    c, "nmcli -t -f ipv4.method con show --active 2>/dev/null | head -1", timeout=5,
                )
                netplan_static = exec_capture(
                    c, "cat /etc/netplan/*.yaml 2>/dev/null | grep -c 'dhcp4: no' || echo 0", timeout=5,
                )
                is_static = "manual" in nm_method or netplan_static != "0"
                rows.append((f"{srv.name} static IP", is_static, f"nmcli={nm_method} netplan={netplan_static}"))

            nopasswd = exec_capture(c, "sudo -n whoami 2>&1", timeout=5).strip() == "root"
            rows.append((f"{srv.name} NOPASSWD sudo", nopasswd, ""))

            key_count = exec_capture(c, "grep -c 'ssh-' ~/.ssh/authorized_keys 2>/dev/null || echo 0", timeout=5)
            rows.append((f"{srv.name} SSH key present", key_count != "0", f"{key_count} key(s)"))
    except Exception as e:
        rows.append((f"{srv.name} reachable", False, str(e)[:80]))
    return rows


def check_external_portforwards(settings: Settings, servers: list) -> list[tuple[str, bool, str]]:
    rows: list[tuple[str, bool, str]] = []
    for srv in servers:
        ok, banner = tcp_probe(settings.wan_ip, srv.external_port)
        rows.append((f"WAN:{srv.external_port} → {srv.name}", ok, banner))
    return rows


def main(argv: list[str] | None = None) -> int:
    settings = Settings.load()
    servers = load_servers()

    all_rows: list[tuple[str, bool, str]] = []

    print("=" * 60)
    print("USG persistence")
    print("=" * 60)
    for row in check_usg(settings):
        name, ok, detail = row
        print(f"  [{'OK' if ok else 'FAIL'}] {name}  {detail}")
        all_rows.append(row)

    print("\n" + "=" * 60)
    print("Per-server audit")
    print("=" * 60)
    for srv in servers:
        for row in check_server(settings, srv):
            name, ok, detail = row
            print(f"  [{'OK' if ok else 'FAIL'}] {name}  {detail}")
            all_rows.append(row)

    print("\n" + "=" * 60)
    print("WAN port-forward reachability")
    print("=" * 60)
    for row in check_external_portforwards(settings, servers):
        name, ok, detail = row
        print(f"  [{'OK' if ok else 'FAIL'}] {name}  {detail}")
        all_rows.append(row)

    failures = [r for r in all_rows if not r[1]]
    print(f"\nSummary: {len(all_rows) - len(failures)} OK, {len(failures)} FAIL.")
    return 0 if not failures else 2


if __name__ == "__main__":
    sys.exit(main())
