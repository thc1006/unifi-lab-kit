#!/usr/bin/env python3
"""Connect to USG-3P EdgeOS (OpenSSH 6.6.1p1) with legacy compatibility."""
import sys
import time
import paramiko
import socket

HOST = "192.168.1.1"
PORT = 22

# USG runs OpenSSH 6.6.1p1 - need legacy algorithm support
CREDS = [
    ("ubnt", "ubnt"),
    ("admin", ""),
    ("admin", "admin"),
    ("ops", "exampleswitchpass"),
    ("root", "ubnt"),
    ("root", ""),
]


def run_cmd(client, cmd, timeout=10):
    try:
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        return (out + ("\n[ERR]: " + err if err.strip() else "")).strip()
    except Exception as e:
        return f"[ERROR]: {e}"


def connect_usg():
    """Connect with legacy SSH compatibility."""
    for user, pwd in CREDS:
        label = f"{user}/{pwd or '(empty)'}"
        print(f"Trying {label}...", end=" ", flush=True)

        try:
            # Create transport manually for more control
            sock = socket.create_connection((HOST, PORT), timeout=10)
            transport = paramiko.Transport(sock)

            # Set banner timeout higher for slow USG
            transport.banner_timeout = 30

            # Start the transport
            transport.start_client()

            # Try password auth
            transport.auth_password(user, pwd)

            if transport.is_authenticated():
                print(f"SUCCESS!")
                client = paramiko.SSHClient()
                client._transport = transport
                return client, user, pwd
            else:
                print("Not authenticated")
                transport.close()

        except paramiko.AuthenticationException:
            print("Auth failed")
            try:
                transport.close()
            except:
                pass
            time.sleep(1)

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(2)

    return None, None, None


def dump_config(client):
    """Dump full USG configuration."""
    commands = [
        ("show version", "System version"),
        ("show interfaces", "Interface configuration"),
        ("show configuration commands | head -200", "Configuration (first 200 lines)"),
        ("show nat rules", "NAT / Port forwarding rules"),
        ("show nat translations", "Active NAT translations"),
        ("show dhcp leases", "DHCP lease table"),
        ("show ip route", "Routing table"),
        ("show arp", "ARP table (MAC addresses)"),
        ("show firewall summary", "Firewall summary"),
        ("cat /config/config.boot | head -200", "Config boot file (first 200 lines)"),
    ]

    for cmd, desc in commands:
        print(f"\n{'='*60}")
        print(f">>> {cmd}  ({desc})")
        print(f"{'='*60}")
        result = run_cmd(client, cmd)
        print(result if result else "(empty)")


def main():
    print("=" * 60)
    print(f"  USG-3P EdgeOS SSH (MAC: 74:AC:B9:4E:38:D7)")
    print(f"  Target: {HOST}:{PORT}")
    print(f"  SSH: OpenSSH_6.6.1p1 Debian (EdgeOS)")
    print("=" * 60)

    client, user, pwd = connect_usg()

    if client:
        print(f"\nAuthenticated as: {user}/{pwd}")
        dump_config(client)
        client.close()
    else:
        print("\nAll credentials failed!")
        print("\nThe USG was adopted by UniFi Controller.")
        print("The SSH password is set by the Controller under:")
        print("  Settings > System > Device Authentication")
        print("\nPlease check the Controller for the device SSH password.")


if __name__ == "__main__":
    main()
