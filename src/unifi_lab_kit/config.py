"""Single source of truth for credentials and network topology.

Loads `.env` (via python-dotenv) and `inventory/hosts.yml` (via PyYAML), then
exposes a `Settings` dataclass and a `load_inventory()` helper. Every other
module in this package imports from here — never hard-code a credential,
never hard-code an IP. If you need something that isn't surfaced here yet,
add it here first.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*_args: Any, **_kwargs: Any) -> bool:  # type: ignore[misc]
        return False

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = REPO_ROOT / ".env"
INVENTORY_PATH = REPO_ROOT / "inventory" / "hosts.yml"
INVENTORY_EXAMPLE_PATH = REPO_ROOT / "inventory" / "hosts.example.yml"


class _MissingEnv:
    """Collector used during Settings.load to aggregate missing required
    variables so we can report all of them in one error, instead of
    raising on the first one the user happens to forget."""

    def __init__(self) -> None:
        self.names: list[str] = []

    def required(self, name: str) -> str:
        val = os.environ.get(name)
        if val is None or val == "" or val.startswith("REPLACE_ME"):
            self.names.append(name)
            return ""
        return val

    @staticmethod
    def optional(name: str, default: str = "") -> str:
        val = os.environ.get(name, default)
        if val.startswith("REPLACE_ME"):
            return default
        return val


@dataclass(frozen=True)
class Settings:
    """Flat, read-only view of the .env file."""

    # WAN
    wan_ip: str
    wan_ip_alias: str
    wan_gateway: str
    wan_netmask: str

    # LAN
    lan_subnet: str
    lan_gateway: str
    dns_primary: str
    dns_secondary: str

    # USG
    usg_ip: str
    usg_user: str
    usg_pass: str
    usg_mac: str

    # Controller
    controller_host: str
    controller_https_port: int
    controller_inform_port: int
    controller_user: str
    controller_pass: str
    controller_docker_name: str

    # NAS
    nas_ip: str
    nas_user: str
    nas_pass: str

    # Servers
    server_primary_user: str
    server_secondary_user: str
    server_pass: str

    # Admin
    admin_ssh_pubkey: str

    # Samba
    samba_workgroup: str
    samba_netbios: str
    samba_hosts_allow: str

    @classmethod
    def load(cls) -> Settings:
        load_dotenv(ENV_PATH)
        m = _MissingEnv()
        instance = cls(
            wan_ip=m.required("WAN_IP"),
            wan_ip_alias=m.optional("WAN_IP_ALIAS"),
            wan_gateway=m.required("WAN_GATEWAY"),
            wan_netmask=m.optional("WAN_NETMASK", "255.255.255.0"),
            lan_subnet=m.optional("LAN_SUBNET", "192.168.1.0/24"),
            lan_gateway=m.optional("LAN_GATEWAY", "192.168.1.1"),
            dns_primary=m.optional("DNS_PRIMARY", "1.1.1.1"),
            dns_secondary=m.optional("DNS_SECONDARY", "8.8.8.8"),
            usg_ip=m.optional("USG_IP", "192.168.1.1"),
            usg_user=m.required("USG_USER"),
            usg_pass=m.required("USG_PASS"),
            usg_mac=m.optional("USG_MAC"),
            controller_host=m.optional("CONTROLLER_HOST", "192.168.1.129"),
            controller_https_port=int(m.optional("CONTROLLER_HTTPS_PORT", "8443")),
            controller_inform_port=int(m.optional("CONTROLLER_INFORM_PORT", "8080")),
            controller_user=m.required("CONTROLLER_USER"),
            controller_pass=m.required("CONTROLLER_PASS"),
            controller_docker_name=m.optional("CONTROLLER_DOCKER_NAME", "unifi"),
            nas_ip=m.optional("NAS_IP", "192.168.1.129"),
            nas_user=m.required("NAS_USER"),
            nas_pass=m.required("NAS_PASS"),
            server_primary_user=m.optional("SERVER_PRIMARY_USER", "admin"),
            server_secondary_user=m.optional("SERVER_SECONDARY_USER", "ops"),
            server_pass=m.required("SERVER_PASS"),
            admin_ssh_pubkey=m.required("ADMIN_SSH_PUBKEY"),
            samba_workgroup=m.optional("SAMBA_WORKGROUP", "WORKGROUP"),
            samba_netbios=m.optional("SAMBA_NETBIOS", "NAS"),
            samba_hosts_allow=m.optional("SAMBA_HOSTS_ALLOW", "192.168.1.0/24"),
        )
        if m.names:
            raise RuntimeError(
                f"{len(m.names)} required env var(s) missing or unset: "
                f"{', '.join(m.names)}. Copy .env.example to .env and fill them in."
            )
        return instance


@dataclass(frozen=True)
class ServerEntry:
    name: str
    internal_ip: str
    external_port: int
    mac: str
    user_profile: str  # "primary" | "secondary"
    ip_mode: str       # "dhcp_reservation" | "static_netplan" | "static_nmcli"
    extra: dict[str, Any] = field(default_factory=dict)

    def ssh_user(self, settings: Settings) -> str:
        if self.user_profile == "secondary":
            return settings.server_secondary_user
        return settings.server_primary_user


def load_inventory() -> dict[str, Any]:
    """Return raw inventory mapping. Prefers hosts.yml, falls back to the example."""
    if yaml is None:
        raise RuntimeError("pyyaml is required; run `pip install pyyaml` or `make install`.")
    path = INVENTORY_PATH if INVENTORY_PATH.exists() else INVENTORY_EXAMPLE_PATH
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_servers() -> list[ServerEntry]:
    """Parse the `servers:` list out of inventory into typed entries."""
    inv = load_inventory()
    out: list[ServerEntry] = []
    for raw in inv.get("servers", []):
        out.append(
            ServerEntry(
                name=raw["name"],
                internal_ip=raw["internal_ip"],
                external_port=int(raw["external_port"]),
                mac=raw.get("mac", ""),
                user_profile=raw.get("user_profile", "primary"),
                ip_mode=raw.get("ip_mode", "dhcp_reservation"),
                extra={k: v for k, v in raw.items() if k not in {
                    "name", "internal_ip", "external_port", "mac",
                    "user_profile", "ip_mode",
                }},
            )
        )
    return out
