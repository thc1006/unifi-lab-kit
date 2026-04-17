"""Install native Samba on the NAS, bind to LAN interface only, expose three shares.

Replaces any containerised SMB setup. See docs/adr/0002-native-samba-over-docker.md.

    $ python -m mllab_net.nas_samba
"""
from __future__ import annotations

import string
import sys
import time
from pathlib import Path

from .config import REPO_ROOT, Settings
from ._ssh import exec_capture, ssh_connect


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


def main(argv: list[str] | None = None) -> int:
    settings = Settings.load()
    smb_conf = render_smb_conf(settings)

    print(f"Installing Samba on NAS {settings.nas_ip}…")
    with ssh_connect(settings.nas_ip, settings.nas_user, settings.nas_pass) as nas:
        # Install if missing (idempotent).
        exec_capture(
            nas,
            f"echo '{settings.nas_pass}' | sudo -S apt-get update -qq 2>&1 | tail -1",
            timeout=60,
        )
        exec_capture(
            nas,
            f"echo '{settings.nas_pass}' | sudo -S apt-get install -y -qq samba 2>&1 | tail -3",
            timeout=180,
        )
        exec_capture(nas, f"echo '{settings.nas_pass}' | sudo -S systemctl stop smbd nmbd 2>/dev/null", timeout=15)

        version = exec_capture(nas, "smbd --version 2>/dev/null", timeout=5)
        print(f"  Version: {version}")

        # Write smb.conf
        sftp = nas.open_sftp()
        with sftp.open("/tmp/mllab_smb.conf", "w") as f:
            f.write(smb_conf)
        sftp.close()
        time.sleep(0.3)
        exec_capture(nas, f"echo '{settings.nas_pass}' | sudo -S cp /tmp/mllab_smb.conf /etc/samba/smb.conf", timeout=5)
        testparm = exec_capture(nas, "testparm -s 2>/dev/null | head -5", timeout=5)
        print(f"  testparm: {testparm}")

        # Samba user must exist as system user first
        exec_capture(
            nas,
            f"echo '{settings.nas_pass}' | sudo -S useradd -M -s /usr/sbin/nologin "
            f"{settings.server_primary_user} 2>/dev/null; true",
            timeout=10,
        )
        set_pass = (
            f"(echo '{settings.server_pass}'; echo '{settings.server_pass}') | "
            f"echo '{settings.nas_pass}' | sudo -S smbpasswd -a {settings.server_primary_user} 2>&1"
        )
        out = exec_capture(nas, set_pass, timeout=10)
        print(f"  smbpasswd: {out[:200]}")

        exec_capture(nas, f"echo '{settings.nas_pass}' | sudo -S systemctl enable --now smbd", timeout=15)
        time.sleep(2)
        active = exec_capture(nas, "systemctl is-active smbd", timeout=5)
        print(f"  smbd active: {active}")
        listening = exec_capture(nas, f"echo '{settings.nas_pass}' | sudo -S ss -tlnp | grep :445 || true", timeout=5)
        print(f"  Listening 445: {listening or 'not detected'}")

    print("\nDone. Shares are LAN-only per hosts allow directive.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
