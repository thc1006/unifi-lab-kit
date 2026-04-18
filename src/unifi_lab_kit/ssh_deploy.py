"""Deploy the admin SSH public key (and ensure NOPASSWD sudo) on every server in inventory.

    $ python -m unifi_lab_kit.ssh_deploy
"""
from __future__ import annotations

import re
import shlex
import sys

from ._ssh import exec_capture, ssh_connect
from .config import Settings, load_servers

_SAFE_USERNAME = re.compile(r"^[a-z_][a-z0-9_-]*$")


def deploy_to_one(host: str, user: str, password: str, pubkey: str, *, setup_nopasswd: bool) -> bool:
    if setup_nopasswd and not _SAFE_USERNAME.match(user):
        # Defensive: user comes from .env/inventory and lands in a filename
        # and a grep pattern. Restrict to POSIX portable characters so we
        # don't have to think about escaping.
        print(f"  refused: username {user!r} is not a safe POSIX login name.")
        return False

    pubkey_q = shlex.quote(pubkey)
    try:
        with ssh_connect(host, user, password) as c:
            install_key = (
                f"mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
                f"touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && "
                f"grep -qF {pubkey_q} ~/.ssh/authorized_keys 2>/dev/null || "
                f"echo {pubkey_q} >> ~/.ssh/authorized_keys && echo OK"
            )
            out = exec_capture(c, install_key, timeout=10)
            if "OK" not in out:
                print(f"  key install failed: {out!r}")
                return False

            # Confirm key lands
            verify = exec_capture(c, "grep -cF ssh-ed25519 ~/.ssh/authorized_keys", timeout=5)
            print(f"  key confirmed ({verify.strip()} key(s) total).")

            if setup_nopasswd:
                sudoers_path = f"/etc/sudoers.d/90-{user}"
                line = f"{user} ALL=(ALL) NOPASSWD:ALL"
                inner = (
                    f"grep -qF {shlex.quote(line)} {sudoers_path} 2>/dev/null "
                    f"|| {{ printf '%s\\n' {shlex.quote(line)} > {sudoers_path} "
                    f"&& chmod 440 {sudoers_path}; }}"
                )
                nopasswd_cmd = (
                    f"echo {shlex.quote(password)} | sudo -S -p '' "
                    f"bash -c {shlex.quote(inner)} 2>&1 | tail -2"
                )
                _ = exec_capture(c, nopasswd_cmd, timeout=10)
                check = exec_capture(c, "sudo -n whoami 2>&1", timeout=5)
                if check.strip() != "root":
                    print(f"  NOPASSWD check: FAILED ({check!r})")
                    return False
                print("  NOPASSWD: OK")
            return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main(argv: list[str] | None = None) -> int:
    settings = Settings.load()
    servers = load_servers()

    if not settings.admin_ssh_pubkey.startswith("ssh-"):
        print("ADMIN_SSH_PUBKEY in .env does not look like an ssh-* line; aborting.")
        return 2

    print(f"Deploying pubkey to {len(servers)} server(s)…")
    failures = 0
    for srv in servers:
        user = srv.ssh_user(settings)
        print(f"--- {srv.name} ({srv.internal_ip}, user={user}) ---")
        ok = deploy_to_one(
            srv.internal_ip,
            user,
            settings.server_pass,
            settings.admin_ssh_pubkey,
            setup_nopasswd=True,
        )
        if not ok:
            failures += 1

    print(f"\nDone: {len(servers) - failures}/{len(servers)} succeeded.")
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
