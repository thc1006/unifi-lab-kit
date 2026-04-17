"""Unit test: the EdgeOS command builder emits the expected shape.

Uses a hand-built Settings object to avoid needing a real .env during tests.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mllab_net.config import ServerEntry, Settings  # noqa: E402
from mllab_net.usg import build_command_sequence  # noqa: E402


def _fake_settings() -> Settings:
    return Settings(
        wan_ip="203.0.113.10",
        wan_ip_alias="203.0.113.11",
        wan_gateway="203.0.113.1",
        wan_netmask="255.255.255.0",
        lan_subnet="192.168.1.0/24",
        lan_gateway="192.168.1.1",
        dns_primary="1.1.1.1",
        dns_secondary="8.8.8.8",
        usg_ip="192.168.1.1",
        usg_user="admin",
        usg_pass="x",
        usg_mac="",
        controller_host="192.168.1.129",
        controller_https_port=8443,
        controller_inform_port=8080,
        controller_user="admin",
        controller_pass="x",
        controller_docker_name="unifi",
        nas_ip="192.168.1.129",
        nas_user="admin",
        nas_pass="x",
        server_primary_user="admin",
        server_secondary_user="ops",
        server_pass="x",
        admin_ssh_pubkey="ssh-ed25519 AAAA test@test",
        samba_workgroup="WG",
        samba_netbios="NAS",
        samba_hosts_allow="192.168.1.0/24",
    )


def _fake_servers() -> list[ServerEntry]:
    return [
        ServerEntry("s1", "192.168.1.101", 12010, "", "primary", "dhcp_reservation"),
        ServerEntry("s2", "192.168.1.102", 12020, "", "secondary", "static_netplan"),
    ]


def test_sequence_starts_with_configure_and_ends_with_exit() -> None:
    seq = build_command_sequence(_fake_settings(), _fake_servers())
    cmds = [c for c, _ in seq]
    assert cmds[0] == "configure"
    assert cmds[-1] == "exit"
    assert "commit" in cmds
    assert "save" in cmds


def test_sequence_emits_rule_per_server() -> None:
    servers = _fake_servers()
    seq = build_command_sequence(_fake_settings(), servers)
    rule_descriptions = [c for c, _ in seq if "description" in c]
    assert len(rule_descriptions) == len(servers)
    assert "s1-ssh" in rule_descriptions[0]
    assert "s2-ssh" in rule_descriptions[1]


def test_sequence_emits_wan_alias_when_configured() -> None:
    s = _fake_settings()
    seq = build_command_sequence(s, _fake_servers())
    joined = "\n".join(c for c, _ in seq)
    assert s.wan_ip in joined
    assert s.wan_ip_alias in joined
