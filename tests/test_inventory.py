"""Smoke-check: the example inventory parses and carries the expected shape.

Intentionally does NOT load .env / Settings, so tests work on a fresh clone.
"""
from __future__ import annotations

import sys
from pathlib import Path

# The test runs without the package installed (pytest path hack driven by pyproject)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml  # noqa: E402


def test_example_inventory_parses() -> None:
    path = ROOT / "inventory" / "hosts.example.yml"
    assert path.exists(), "inventory/hosts.example.yml missing"
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert "gateway" in data
    assert "controller" in data
    assert "servers" in data
    assert isinstance(data["servers"], list)
    assert len(data["servers"]) > 0


def test_example_inventory_server_entries_are_well_formed() -> None:
    path = ROOT / "inventory" / "hosts.example.yml"
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    for s in data["servers"]:
        assert "name" in s
        assert "internal_ip" in s
        assert "external_port" in s
        assert s["external_port"] >= 1024
        assert s["user_profile"] in {"primary", "secondary"}
        assert s["ip_mode"] in {"dhcp_reservation", "static_netplan", "static_nmcli"}


def test_example_inventory_port_convention() -> None:
    """External port follows 12000 + (last_octet mod 100) * 10 slot convention.

    So .106 -> 12060, .123 -> 12230, .111 -> 12110. The NAS (.129) is
    intentionally NOT in the ``servers:`` list and is exempt.
    """
    path = ROOT / "inventory" / "hosts.example.yml"
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    for s in data["servers"]:
        last = int(s["internal_ip"].rsplit(".", 1)[-1])
        expected = 12000 + (last % 100) * 10
        assert s["external_port"] == expected, (
            f"{s['name']}: expected external_port {expected}, got {s['external_port']}"
        )
