"""Deploy the admin SSH public key (and ensure NOPASSWD sudo) on every server in inventory.

    $ python -m mllab_net.ssh_deploy
"""
from __future__ import annotations

import sys

from ._ssh import exec_capture, ssh_connect
from .config import Settings, load_servers


def deploy_to_one(host: str, user: str, password: str, pubkey: str, *, setup_nopasswd: bool) -> bool:
    try:
        with ssh_connect(host, user, password) as c:
            install_key = (
                f"mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
                f"touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && "
                f"grep -qF '{pubkey}' ~/.ssh/authorized_keys 2>/dev/null || "
                f"echo '{pubkey}' >> ~/.ssh/authorized_keys && echo OK"
            )
            out = exec_capture(c, install_key, timeout=10)
            if "OK" not in out:
                print(f"  key install failed: {out!r}")
                return False

            # Confirm key lands
            verify = exec_capture(c, "grep -F 'ssh-ed25519' ~/.ssh/authorized_keys | wc -l", timeout=5)
            print(f"  key confirmed ({verify.strip()} key(s) total).")

            if setup_nopasswd:
                line = f"{user} ALL=(ALL) NOPASSWD:ALL"
                nopasswd_cmd = (
                    f"echo '{password}' | sudo -S bash -c \""
                    f"grep -q '^{user} ALL=(ALL) NOPASSWD:ALL' /etc/sudoers.d/90-{user} 2>/dev/null "
                    f"|| echo '{line}' > /etc/sudoers.d/90-{user}; "
                    f"chmod 440 /etc/sudoers.d/90-{user}\" 2>&1 | tail -2"
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
