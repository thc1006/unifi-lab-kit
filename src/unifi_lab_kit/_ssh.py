"""Tiny paramiko convenience wrappers shared by the other modules."""
from __future__ import annotations

import socket
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import paramiko


@contextmanager
def ssh_connect(host: str, user: str, password: str, *, timeout: int = 8) -> Iterator[paramiko.SSHClient]:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(host, username=user, password=password, timeout=timeout, allow_agent=False, look_for_keys=False)
    try:
        yield c
    finally:
        c.close()


def exec_capture(client: paramiko.SSHClient, cmd: str, *, timeout: int = 15) -> str:
    _, out, _ = client.exec_command(cmd, timeout=timeout)
    return out.read().decode("utf-8", errors="replace").strip()


def tcp_probe(host: str, port: int, *, timeout: float = 3.0) -> tuple[bool, str]:
    """Return (open, banner) for a given TCP endpoint."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        r = s.connect_ex((host, port))
        if r != 0:
            return False, ""
        try:
            banner = s.recv(256).decode("utf-8", errors="replace").strip()[:80]
        except Exception:
            banner = ""
        return True, banner
    finally:
        s.close()


def interactive_shell_commands(
    client: paramiko.SSHClient,
    commands: list[tuple[str, float]],
    *,
    width: int = 200,
    height: int = 50,
) -> list[str]:
    """Send a list of (cmd, wait_seconds) pairs down an interactive shell.

    Used for EdgeOS `configure; set …; commit; save` flows where each step
    must settle before the next.
    """
    shell = client.invoke_shell(width=width, height=height)
    time.sleep(2)
    shell.recv(4096)

    outputs: list[str] = []
    for cmd, wait in commands:
        shell.send((cmd + "\n").encode("utf-8"))
        time.sleep(wait)
        buf = ""
        while shell.recv_ready():
            buf += shell.recv(8192).decode("utf-8", errors="replace")
        outputs.append(buf)
    shell.close()
    return outputs


def run_on_nas_docker_controller(
    nas_client: paramiko.SSHClient,
    container: str,
    curl_args: str,
    *,
    timeout: int = 15,
) -> str:
    """Run `docker exec <container> curl …` on the NAS. Returns stdout."""
    return exec_capture(
        nas_client,
        f"docker exec {container} curl -sk {curl_args} 2>&1",
        timeout=timeout,
    )


def login_controller(
    nas_client: paramiko.SSHClient,
    container: str,
    user: str,
    password: str,
    https_port: int,
) -> None:
    """Log in to the UniFi Controller API and persist the session cookie at /tmp/uc inside the container."""
    body = '{"username":"' + user + '","password":"' + password + '"}'
    exec_capture(
        nas_client,
        f"docker exec {container} curl -sk -X POST "
        f"https://localhost:{https_port}/api/login "
        f'-H "Content-Type: application/json" '
        f"-d '{body}' "
        f"-c /tmp/uc 2>&1",
        timeout=15,
    )


def put_file_into_container(
    nas_client: paramiko.SSHClient,
    container: str,
    container_path: str,
    content: str,
) -> None:
    """Write `content` to a tmp file on the NAS, then `docker cp` into the container."""
    import uuid
    host_tmp = f"/tmp/mllab_{uuid.uuid4().hex}.tmp"
    sftp = nas_client.open_sftp()
    with sftp.open(host_tmp, "w") as f:
        f.write(content)
    sftp.close()
    time.sleep(0.3)
    exec_capture(nas_client, f"docker cp {host_tmp} {container}:{container_path} && rm -f {host_tmp}")


def _swallow(_: Any) -> None:
    """Utility to silence unused-return lints."""
    return None
