"""Identify unknown / newly-attached hosts on the LAN by probing SSH with known credentials.

Runs via the NAS (since the NAS has sshpass and network adjacency to all LAN
hosts). For every target IP it tries every (user, password) pair recorded in
.env until one succeeds, then dumps hostname / CPU / GPU / RAM / MAC for
documentation purposes.

    $ python -m mllab_net.scan 192.168.1.50 192.168.1.51 ...
    $ python -m mllab_net.scan --range 192.168.1.100-199
"""
from __future__ import annotations

import argparse
import sys

from ._ssh import exec_capture, ssh_connect
from .config import Settings


def expand_range(spec: str) -> list[str]:
    """Accepts '192.168.1.100-199'. Returns explicit list of /32 addresses."""
    head, _, rng = spec.rpartition(".")
    start_s, _, end_s = rng.partition("-")
    if not end_s:
        return [spec]
    return [f"{head}.{i}" for i in range(int(start_s), int(end_s) + 1)]


def probe_one(nas_client, ip: str, users: list[str], passwords: list[str]) -> dict | None:
    for user in users:
        for pw in passwords:
            pw_esc = pw.replace("'", "'\\''")
            login = (
                f"sshpass -p '{pw_esc}' ssh -o StrictHostKeyChecking=no "
                f"-o ConnectTimeout=3 -o PreferredAuthentications=password "
                f"-o NumberOfPasswordPrompts=1 "
                f"{user}@{ip} hostname 2>&1"
            )
            out = exec_capture(nas_client, login, timeout=12)
            looks_like_error = any(m in out.lower() for m in (
                "denied", "permission", "error", "timeout", "closed", "refused",
                "no route", "reset", "port 22", "usage:",
            ))
            if out and not looks_like_error and len(out) < 80:
                # Got in; collect a richer profile.
                info_cmd = (
                    f"sshpass -p '{pw_esc}' ssh -o StrictHostKeyChecking=no "
                    f"-o ConnectTimeout=5 -o PreferredAuthentications=password "
                    f"{user}@{ip} \""
                    "hostname; "
                    "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo NO_GPU; "
                    "lscpu 2>/dev/null | grep 'Model name' | sed 's/.*: *//'; "
                    "free -h 2>/dev/null | grep Mem | awk '{print \\$2}'; "
                    "ip link show 2>/dev/null | awk '/link\\/ether/{print \\$2; exit}'"
                    "\" 2>&1"
                )
                info = exec_capture(nas_client, info_cmd, timeout=20)
                lines = [ln.strip() for ln in info.splitlines() if ln.strip()]
                return {
                    "ip": ip,
                    "user": user,
                    "hostname": lines[0] if lines else "",
                    "gpu": lines[1] if len(lines) > 1 else "",
                    "cpu": lines[2] if len(lines) > 2 else "",
                    "mem": lines[3] if len(lines) > 3 else "",
                    "mac": lines[4] if len(lines) > 4 else "",
                }
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="*", help="Individual IPs to scan.")
    parser.add_argument("--range", dest="iprange", default=None,
                        help="IP range, e.g. 192.168.1.100-199")
    args = parser.parse_args(argv)

    settings = Settings.load()
    ips = list(args.targets)
    if args.iprange:
        ips.extend(expand_range(args.iprange))
    if not ips:
        print("No targets; pass IPs or --range.")
        return 2

    users = [settings.server_primary_user, settings.server_secondary_user, "root", "ubuntu"]
    passwords = [settings.server_pass]  # extend here if you keep a known-legacy list

    print(f"Probing {len(ips)} host(s) via NAS {settings.nas_ip}…")
    matches: list[dict] = []
    with ssh_connect(settings.nas_ip, settings.nas_user, settings.nas_pass) as nas:
        # Need sshpass present
        have = exec_capture(nas, "command -v sshpass || echo missing", timeout=5)
        if "missing" in have:
            print("NAS is missing sshpass. Install it (apt-get install sshpass) before scanning.")
            return 2

        for ip in ips:
            hit = probe_one(nas, ip, users, passwords)
            if hit:
                print(f"  MATCH {hit['ip']:<15}  {hit['hostname']:<15} "
                      f"user={hit['user']} gpu={hit['gpu']} cpu={hit['cpu']}")
                matches.append(hit)
            else:
                print(f"  miss  {ip}")

    print(f"\nIdentified {len(matches)}/{len(ips)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
