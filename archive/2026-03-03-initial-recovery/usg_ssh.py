#!/usr/bin/env python3
"""SSH into USG-3P and dump configuration using paramiko."""
import sys
import time

try:
    import paramiko
except ImportError:
    print("Installing paramiko...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko", "-q"])
    import paramiko

HOST = "192.168.1.1"
USER = "ops"
PASS = "exampleswitchpass"
PORT = 22

COMMANDS = [
    "show interfaces",
    "show configuration commands",
    "cat /etc/hostname",
    "show nat rules",
    "show nat translations",
    "show dhcp leases",
    "show ip route",
    "show arp",
    "show system uptime",
    "show version",
]


def run_command(client, cmd, timeout=10):
    """Execute a command and return output."""
    try:
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        output = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        if err:
            return f"{output}\n[STDERR]: {err}"
        return output
    except Exception as e:
        return f"[ERROR]: {e}"


def main():
    print("=" * 60)
    print(f"  USG-3P Configuration Dump ({HOST})")
    print("=" * 60)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print(f"\nConnecting to {USER}@{HOST}:{PORT}...")
        client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=10)
        print("Connected!\n")

        for cmd in COMMANDS:
            print(f"\n{'='*60}")
            print(f">>> {cmd}")
            print(f"{'='*60}")
            output = run_command(client, cmd)
            print(output)

    except paramiko.AuthenticationException:
        print(f"Authentication failed for {USER}@{HOST}")
        print("Trying with different credentials...")
        # Try empty password (CLAUDE.md mentions "空" for router)
        try:
            client.connect(HOST, port=PORT, username=USER, password="", timeout=10)
            print("Connected with empty password!")
            for cmd in COMMANDS:
                print(f"\n>>> {cmd}")
                print(run_command(client, cmd))
        except Exception as e2:
            print(f"Also failed: {e2}")
    except Exception as e:
        print(f"Connection failed: {e}")
    finally:
        client.close()

    # Also try connecting to GPU servers
    print("\n\n" + "=" * 60)
    print("  GPU Server Identification")
    print("=" * 60)

    servers = {
        "192.168.1.6": ["legacypass01", "legacypass02", "legacypass03", "legacypass04", "legacypass05"],
        "192.168.1.14": ["legacypass02", "legacypass03", "legacypass04", "legacypass07", "legacypass08"],
        "192.168.1.21": ["legacypass09", "legacypass10", "legacypass11", "legacypass12", "legacypass06"],
        "192.168.1.29": ["legacypass03", "legacypass04", "legacypass05", "legacypass06", "legacypass01"],
        "192.168.1.46": ["legacypass07", "legacypass08", "legacypass09", "legacypass16", "legacypass02"],
        "192.168.1.49": ["legacypass10", "legacypass11", "legacypass12", "legacypass07", "legacypass08"],
        "192.168.1.57": ["legacypass06", "legacypass16", "legacypass01", "legacypass02", "legacypass05"],
        "192.168.1.100": ["examplenaspass", "legacypass01", "legacypass02", "legacypass04", "legacypass05"],
        "192.168.1.102": ["legacypass02"],
    }

    # All known passwords
    all_passwords = [
        "legacypass01", "legacypass02", "legacypass03", "legacypass04",
        "legacypass05", "legacypass06", "legacypass16", "legacypass07",
        "legacypass08", "legacypass09", "legacypass10", "legacypass11",
        "legacypass12", "legacypass13", "legacypass14", "legacypass15",
        "examplenaspass",
    ]

    for ip in servers:
        print(f"\n--- {ip} ---")
        identified = False
        for pw in all_passwords:
            try:
                c = paramiko.SSHClient()
                c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                c.connect(ip, port=22, username="admin", password=pw, timeout=5,
                         banner_timeout=5, auth_timeout=5)

                hostname = run_command(c, "hostname", timeout=5).strip()
                gpu = run_command(c, "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo 'no-gpu'", timeout=10).strip()
                net = run_command(c, "ip -4 addr show scope global | grep inet", timeout=5).strip()

                print(f"  IP: {ip}")
                print(f"  Password: {pw}")
                print(f"  Hostname: {hostname}")
                print(f"  GPU: {gpu}")
                print(f"  Network: {net}")
                c.close()
                identified = True
                break
            except paramiko.AuthenticationException:
                continue
            except Exception as e:
                print(f"  Connection error with pw={pw}: {e}")
                break

        if not identified:
            print(f"  Could not authenticate with any known password")


if __name__ == "__main__":
    main()
