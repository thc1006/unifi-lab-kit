"""Sync the UniFi Controller port-forward rules to match the USG truth.

Also exposes:
  - `adopt_usg`: tells the Controller to adopt a pending USG by MAC
  - `reconnect`: set-inform on the USG so it checks back in

The Controller is treated as a reflection of the USG — never the other way
round (see docs/adr/0001-edgeos-cli-over-controller.md).

    $ python -m unifi_lab_kit.controller          # full sync
    $ python -m unifi_lab_kit.controller --adopt  # also send adopt command
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from ._ssh import (
    exec_capture,
    interactive_shell_commands,
    login_controller,
    put_file_into_container,
    ssh_connect,
)
from .config import Settings, load_servers


def _api(
    nas_client,
    container: str,
    https_port: int,
    method: str,
    path: str,
    body: dict | None = None,
) -> str:
    curl = f"-b /tmp/uc -X {method} 'https://localhost:{https_port}/api/s/default/{path}'"
    if body is not None:
        payload_path = "/tmp/mllab_payload.json"
        put_file_into_container(nas_client, container, payload_path, json.dumps(body))
        curl += f' -H "Content-Type: application/json" -d "$(cat {payload_path})"'
    return exec_capture(
        nas_client,
        f"docker exec {container} curl -sk {curl} 2>&1",
        timeout=20,
    )


def _api_get_data(nas_client, container: str, https_port: int, path: str) -> list[dict]:
    raw = _api(nas_client, container, https_port, "GET", path)
    try:
        return json.loads(raw).get("data", [])
    except json.JSONDecodeError:
        return []


def sync_portforwards(nas_client, settings: Settings, servers: list) -> tuple[int, int]:
    """Delete all existing port-forward rules, re-create from inventory. Returns (deleted, created)."""
    existing = _api_get_data(nas_client, settings.controller_docker_name,
                             settings.controller_https_port, "rest/portforward")
    for r in existing:
        _api(nas_client, settings.controller_docker_name, settings.controller_https_port,
             "DELETE", f"rest/portforward/{r['_id']}")

    created = 0
    for srv in servers:
        body = {
            "name": f"{srv.name}-ssh",
            "enabled": True,
            "dst_port": str(srv.external_port),
            "fwd": srv.internal_ip,
            "fwd_port": "22",
            "proto": "tcp",
            "src": "any",
            "log": False,
        }
        resp = _api(nas_client, settings.controller_docker_name,
                    settings.controller_https_port, "POST", "rest/portforward", body=body)
        if '"ok"' in resp:
            created += 1
    return len(existing), created


def ensure_wan_static(nas_client, settings: Settings) -> None:
    nets = _api_get_data(nas_client, settings.controller_docker_name,
                         settings.controller_https_port, "rest/networkconf")
    for n in nets:
        if n.get("purpose") == "wan" and "WAN1" in n.get("name", ""):
            if n.get("wan_type") != "static":
                body = {
                    "wan_type": "static",
                    "wan_ip": settings.wan_ip,
                    "wan_netmask": settings.wan_netmask,
                    "wan_gateway": settings.wan_gateway,
                    "wan_dns1": settings.dns_primary,
                    "wan_dns2": settings.dns_secondary,
                }
                _api(nas_client, settings.controller_docker_name,
                     settings.controller_https_port, "PUT", f"rest/networkconf/{n['_id']}", body=body)
                print("  WAN networkconf updated to static.")
            else:
                print("  WAN networkconf already static.")
            return


def adopt_usg(nas_client, settings: Settings) -> None:
    if not settings.usg_mac or settings.usg_mac == "aa:bb:cc:dd:ee:ff":
        print("  USG_MAC not set in .env; skipping adopt.")
        return
    body = {"cmd": "adopt", "mac": settings.usg_mac}
    _api(nas_client, settings.controller_docker_name, settings.controller_https_port,
         "POST", "cmd/devmgr", body=body)
    print(f"  Adopt command sent for MAC {settings.usg_mac}.")


def set_inform_on_usg(settings: Settings) -> None:
    inform_url = f"http://{settings.controller_host}:{settings.controller_inform_port}/inform"
    with ssh_connect(settings.usg_ip, settings.usg_user, settings.usg_pass) as c:
        interactive_shell_commands(c, [(f"mca-cli-op set-inform {inform_url}", 10.0)])
    print(f"  set-inform sent: {inform_url}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adopt", action="store_true", help="Also send adopt command for the USG.")
    parser.add_argument("--reconnect", action="store_true", help="set-inform on USG after sync.")
    parser.add_argument("--reset", action="store_true", help="Delete all Controller rules, leave empty.")
    args = parser.parse_args(argv)

    settings = Settings.load()
    servers = load_servers()

    print(f"Controller via NAS : {settings.nas_ip}  container={settings.controller_docker_name}")
    print(f"Controller API     : https://localhost:{settings.controller_https_port}")

    with ssh_connect(settings.nas_ip, settings.nas_user, settings.nas_pass) as nas:
        login_controller(
            nas,
            settings.controller_docker_name,
            settings.controller_user,
            settings.controller_pass,
            settings.controller_https_port,
        )

        if args.reset:
            existing = _api_get_data(nas, settings.controller_docker_name,
                                     settings.controller_https_port, "rest/portforward")
            for r in existing:
                _api(nas, settings.controller_docker_name, settings.controller_https_port,
                     "DELETE", f"rest/portforward/{r['_id']}")
            print(f"Reset: deleted {len(existing)} rule(s).")
            return 0

        deleted, created = sync_portforwards(nas, settings, servers)
        print(f"Port-forwards: deleted {deleted}, created {created}.")

        ensure_wan_static(nas, settings)

        if args.adopt:
            adopt_usg(nas, settings)

    if args.reconnect:
        set_inform_on_usg(settings)
        print("Waiting 15 s for Controller to observe the USG…")
        time.sleep(15)

    return 0 if created == len(servers) else 2


if __name__ == "__main__":
    sys.exit(main())
