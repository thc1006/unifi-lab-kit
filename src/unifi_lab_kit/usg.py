"""Configure the USG: static WAN, port-forward rules, NAT hairpin, then save.

All state comes from .env + inventory/hosts.yml. Idempotent: safe to re-run.

    $ python -m unifi_lab_kit.usg
"""
from __future__ import annotations

import argparse
import sys

from ._ssh import interactive_shell_commands, ssh_connect, tcp_probe
from .config import Settings, load_servers


def build_command_sequence(settings: Settings, servers: list) -> list[tuple[str, float]]:
    """Assemble the EdgeOS CLI batch for WAN + port-forwards.

    Uses long settle times on configure/commit/save because EdgeOS is slow
    and we must not race a half-committed state.
    """
    cmds: list[tuple[str, float]] = [
        ("configure", 3.0),
        # WAN → static
        ("delete interfaces ethernet eth0 address dhcp", 1.5),
        ("delete interfaces ethernet eth0 dhcp-options", 1.5),
        (f"set interfaces ethernet eth0 address {settings.wan_ip}/24", 1.5),
        (f"set protocols static route 0.0.0.0/0 next-hop {settings.wan_gateway}", 1.5),
        (f"set system name-server {settings.dns_primary}", 1.0),
        (f"set system name-server {settings.dns_secondary}", 1.0),
        # Optional second public IP (alias)
    ]
    if settings.wan_ip_alias:
        cmds.append((f"set interfaces ethernet eth0 address {settings.wan_ip_alias}/24", 1.5))

    # Wipe every existing port-forward rule so we re-emit cleanly
    cmds.append(("delete port-forward", 2.0))

    # Globals
    cmds.extend([
        ("set port-forward auto-firewall enable", 1.0),
        ("set port-forward hairpin-nat enable", 1.0),
        ("set port-forward lan-interface eth1", 1.0),
        ("set port-forward wan-interface eth0", 1.0),
    ])

    # Individual rules from inventory
    for idx, srv in enumerate(servers, start=1):
        desc = f"{srv.name}-ssh"
        cmds.extend([
            (f"set port-forward rule {idx} description {desc}", 0.8),
            (f"set port-forward rule {idx} forward-to address {srv.internal_ip}", 0.8),
            (f"set port-forward rule {idx} forward-to port 22", 0.8),
            (f"set port-forward rule {idx} original-port {srv.external_port}", 0.8),
            (f"set port-forward rule {idx} protocol tcp", 0.8),
        ])

    cmds.extend([
        ("commit", 10.0),
        ("save", 3.0),
        ("exit", 2.0),
    ])
    return cmds


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-verify", action="store_true", help="Skip the post-commit TCP probe.")
    parser.add_argument("--reset", action="store_true", help="Wipe port-forwards and WAN back to DHCP (dangerous).")
    args = parser.parse_args(argv)

    settings = Settings.load()
    servers = load_servers()

    if args.reset:
        commands: list[tuple[str, float]] = [
            ("configure", 3.0),
            ("delete port-forward", 2.0),
            ("set interfaces ethernet eth0 address dhcp", 1.5),
            ("delete protocols static route 0.0.0.0/0", 1.5),
            ("commit", 10.0),
            ("save", 3.0),
            ("exit", 2.0),
        ]
    else:
        commands = build_command_sequence(settings, servers)

    print(f"USG host   : {settings.usg_ip}")
    print(f"WAN target : {settings.wan_ip} (gateway {settings.wan_gateway})")
    print(f"Rules      : {len(servers)}" + (" (reset)" if args.reset else ""))

    with ssh_connect(settings.usg_ip, settings.usg_user, settings.usg_pass) as c:
        print("Connected. Running EdgeOS batch…")
        outputs = interactive_shell_commands(c, commands)

    errors = [o for o in outputs if "error" in o.lower() and "commit" in o.lower()]
    if errors:
        print("WARNING: commit reported errors:")
        for o in errors:
            print(o[-400:])

    if args.skip_verify or args.reset:
        return 0

    print("\nProbing port-forwards on WAN…")
    any_fail = False
    for srv in servers:
        open_, banner = tcp_probe(settings.wan_ip, srv.external_port)
        print(f"  :{srv.external_port:<5} {srv.name:12s}  {'OK' if open_ else 'CLOSED'}  {banner}")
        if not open_:
            any_fail = True
    return 0 if not any_fail else 2


if __name__ == "__main__":
    sys.exit(main())
