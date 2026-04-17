"""Reset the UniFi Controller admin password directly via its MongoDB.

Use when you've locked yourself out of the Controller UI but still have
SSH to the NAS where it runs. The Controller user/password you want to
restore is read from .env (CONTROLLER_USER / CONTROLLER_PASS).

    $ python -m mllab_net.controller_pwreset
"""
from __future__ import annotations

import sys
import time

from .config import Settings
from ._ssh import exec_capture, put_file_into_container, ssh_connect


def main(argv: list[str] | None = None) -> int:
    settings = Settings.load()

    print(f"Connecting to NAS {settings.nas_ip}…")
    with ssh_connect(settings.nas_ip, settings.nas_user, settings.nas_pass) as nas:
        # Generate a SHA-512 crypt hash of the desired password on the NAS host
        target_pass = settings.controller_pass.replace('"', r'\"')
        hash_cmd = (
            "python3 -c 'import crypt; "
            f'print(crypt.crypt("{target_pass}", crypt.mksalt(crypt.METHOD_SHA512)))'
            "'"
        )
        new_hash = exec_capture(nas, hash_cmd, timeout=10)
        if not new_hash.startswith("$6$"):
            print(f"Hash generation failed: {new_hash!r}")
            return 2
        print(f"Generated hash: {new_hash[:30]}…")

        js = (
            f'db.admin.updateOne({{"name": "{settings.controller_user}"}}, '
            f'{{$set: {{"x_shadow": "{new_hash}"}}}});\n'
            f'print("Updated");\n'
        )
        put_file_into_container(nas, settings.controller_docker_name, "/tmp/update_pw.js", js)

        out = exec_capture(
            nas,
            f"docker exec {settings.controller_docker_name} mongo --port 27117 ace /tmp/update_pw.js 2>&1",
            timeout=20,
        )
        print(f"Mongo response: {out[:200]}")

        # Verify login
        time.sleep(1)
        body = (
            '{"username":"' + settings.controller_user
            + '","password":"' + settings.controller_pass + '"}'
        )
        verify = exec_capture(
            nas,
            f"docker exec {settings.controller_docker_name} curl -sk -X POST "
            f"https://localhost:{settings.controller_https_port}/api/login "
            f'-H "Content-Type: application/json" -d \'{body}\' 2>&1',
            timeout=15,
        )
        ok = '"ok"' in verify
        print(f"Login verify: {'OK' if ok else 'FAILED'}")
        if ok:
            print(
                f"You can now sign in at "
                f"https://{settings.controller_host}:{settings.controller_https_port}"
                f" as {settings.controller_user}."
            )
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
