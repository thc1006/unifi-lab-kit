#!/usr/bin/env python3
"""Try SSH to known servers with various methods."""
import paramiko
import socket

SERVERS = [
    ("192.168.1.102", "admin", "legacypass02", "server2"),
    ("192.168.1.6", "admin", "legacypass06", "server6"),
    ("192.168.1.9", "admin", "legacypass08", "server9"),
    ("192.168.1.29", "admin", "examplenaspass", "NAS"),
]

# Also try mllab user with switch password
EXTRA = [
    ("192.168.1.102", "ops", "exampleswitchpass", "server2-mllab"),
    ("192.168.1.6", "ops", "exampleswitchpass", "server6-mllab"),
]


def try_ssh(ip, user, passwd, label):
    print(f"  Trying {user}@{ip} ({label})...", end=" ", flush=True)
    try:
        sock = socket.create_connection((ip, 22), timeout=5)
        t = paramiko.Transport(sock)
        t.banner_timeout = 15
        t.start_client()

        # Check available auth methods
        try:
            t.auth_none(user)
        except paramiko.ssh_exception.BadAuthenticationType as e:
            print(f"auth methods: {e.allowed_types}", end=" ")
        except Exception:
            pass

        try:
            t.auth_password(user, passwd)
            if t.is_authenticated():
                print("SUCCESS!")
                # Run commands
                c = paramiko.SSHClient()
                c._transport = t
                for cmd in [
                    "hostname",
                    "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo NO_GPU",
                    "lscpu 2>/dev/null | grep 'Model name' || echo NO_LSCPU",
                    "free -h 2>/dev/null | grep Mem || echo NO_FREE",
                    "ip addr show 2>/dev/null | grep 'inet ' | grep -v 127.0.0.1",
                    "cat /etc/hosts 2>/dev/null | grep -v '^#' | grep -v '^$' | head -20",
                    "ls ~/.ssh/ 2>/dev/null",
                    "cat ~/.ssh/known_hosts 2>/dev/null | awk '{print $1}' | sort -u | head -30",
                    "cat ~/.bash_history 2>/dev/null | grep -i ssh | sort -u | tail -20",
                ]:
                    _, stdout, stderr = c.exec_command(cmd, timeout=10)
                    out = stdout.read().decode("utf-8", errors="replace").strip()
                    if out:
                        print(f"    [{cmd.split()[0]}]: {out[:200]}")
                c.close()
                return True
            else:
                print("auth failed (not authenticated)")
        except paramiko.AuthenticationException:
            print("auth rejected")
        except Exception as e:
            print(f"error: {e}")

        t.close()
    except socket.timeout:
        print("timeout")
    except ConnectionRefusedError:
        print("refused")
    except Exception as e:
        print(f"error: {e}")
    return False


print("=" * 60)
print("Testing SSH to known servers")
print("=" * 60)

for ip, user, passwd, label in SERVERS + EXTRA:
    try_ssh(ip, user, passwd, label)
    print()

# Also check what auth methods are available on the 4 unknown SSH IPs
print("=" * 60)
print("Checking auth methods on unidentified SSH-open IPs")
print("=" * 60)

UNKNOWN_IPS = ["192.168.1.46", "192.168.1.49", "192.168.1.57", "192.168.1.100"]
for ip in UNKNOWN_IPS:
    print(f"  {ip}:", end=" ", flush=True)
    try:
        sock = socket.create_connection((ip, 22), timeout=5)
        t = paramiko.Transport(sock)
        t.banner_timeout = 10
        t.start_client()
        banner = t.remote_version
        print(f"banner={banner}", end=" ")
        try:
            t.auth_none("admin")
        except paramiko.ssh_exception.BadAuthenticationType as e:
            print(f"auth_methods={e.allowed_types}")
        except Exception as e:
            print(f"auth_none_error={e}")
        t.close()
    except Exception as e:
        print(f"error: {e}")

print("\n=== DONE ===")
