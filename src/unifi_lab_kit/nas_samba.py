"""Install native Samba on the NAS, bind to LAN interface only, expose three shares.

Replaces any containerised SMB setup. See docs/adr/0002-native-samba-over-docker.md.

    $ python -m unifi_lab_kit.nas_samba
"""
from __future__ import annotations

import shlex
import string
import sys
import time

from ._ssh import exec_capture, ssh_connect
from .config import REPO_ROOT, Settings


def render_smb_conf(settings: Settings) -> str:
    template_path = REPO_ROOT / "configs" / "smb.conf.template"
    tmpl = template_path.read_text(encoding="utf-8")
    return string.Template(tmpl).substitute(
        SAMBA_WORKGROUP=settings.samba_workgroup,
        SAMBA_NETBIOS=settings.samba_netbios,
        NAS_IP=settings.nas_ip,
        SAMBA_HOSTS_ALLOW=settings.samba_hosts_allow,
        SERVER_PRIMARY_USER=settings.server_primary_user,
    )


def _sudo(nas_pass: str, cmd: str) -> str:
    """Wrap a command in `echo PASS | sudo -S -p '' …`, safely quoted."""
    return f"echo {shlex.quote(nas_pass)} | sudo -S -p '' {cmd}"


def main(argv: list[str] | None = None) -> int:
    settings = Settings.load()
    smb_conf = render_smb_conf(settings)

    nas_pass_q = shlex.quote(settings.nas_pass)
    server_pass_q = shlex.quote(settings.server_pass)
    user_q = shlex.quote(settings.server_primary_user)

    print(f"Installing Samba on NAS {settings.nas_ip}…")
    with ssh_connect(settings.nas_ip, settings.nas_user, settings.nas_pass) as nas:
        # Install if missing (idempotent).
        exec_capture(
            nas,
            _sudo(settings.nas_pass, "apt-get update -qq") + " 2>&1 | tail -1",
            timeout=60,
        )
        exec_capture(
            nas,
            _sudo(settings.nas_pass, "apt-get install -y -qq samba") + " 2>&1 | tail -3",
            timeout=180,
        )
        exec_capture(nas, _sudo(settings.nas_pass, "systemctl stop smbd nmbd") + " 2>/dev/null", timeout=15)

        version = exec_capture(nas, "smbd --version 2>/dev/null", timeout=5)
        print(f"  Version: {version}")

        # Write smb.conf
        sftp = nas.open_sftp()
        with sftp.open("/tmp/ulk_smb.conf", "w") as f:
            f.write(smb_conf)
        sftp.close()
        time.sleep(0.3)
        exec_capture(nas, _sudo(settings.nas_pass, "cp /tmp/ulk_smb.conf /etc/samba/smb.conf"), timeout=5)
        testparm = exec_capture(nas, "testparm -s 2>/dev/null | head -5", timeout=5)
        print(f"  testparm: {testparm}")

        # Samba user must exist as system user first
        exec_capture(
            nas,
            _sudo(
                settings.nas_pass,
                f"useradd -M -s /usr/sbin/nologin {user_q}",
            ) + " 2>/dev/null; true",
            timeout=10,
        )

        # Set the Samba password.
        #
        # We must NOT do:
        #   (echo NEW; echo NEW) | echo NAS_PASS | sudo -S smbpasswd ...
        # because `echo NAS_PASS` in the middle of the pipeline discards
        # its stdin and only writes NAS_PASS to the next stage, so
        # smbpasswd reads NAS_PASS as the new password (wrong) or blocks.
        #
        # Correct: pipe NAS_PASS, then NEW, then NEW on three separate
        # lines to one `sudo -S smbpasswd -a -s`. sudo consumes the first
        # line (its own password), then exec's smbpasswd, which reads the
        # next two lines from the same stdin under -s (stdin mode).
        set_pass = (
            f"printf '%s\\n%s\\n%s\\n' {nas_pass_q} {server_pass_q} {server_pass_q} "
            f"| sudo -S -p '' smbpasswd -a -s {user_q} 2>&1"
        )
        out = exec_capture(nas, set_pass, timeout=10)
        print(f"  smbpasswd: {out[:200]}")

        exec_capture(nas, _sudo(settings.nas_pass, "systemctl enable --now smbd"), timeout=15)
        time.sleep(2)
        active = exec_capture(nas, "systemctl is-active smbd", timeout=5)
        print(f"  smbd active: {active}")
        listening = exec_capture(
            nas,
            _sudo(settings.nas_pass, "ss -tlnp") + " | grep :445 || true",
            timeout=5,
        )
        print(f"  Listening 445: {listening or 'not detected'}")

    print("\nDone. Shares are LAN-only per hosts allow directive.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
