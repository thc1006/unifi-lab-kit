#!/usr/bin/env python3
"""SSH into USG-3P and GPU servers - v2 with rate limiting fix."""
import sys
import time
import paramiko

HOST = "192.168.1.1"


def run_cmd(client, cmd, timeout=10):
    try:
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        return (out + ("\n[STDERR]: " + err if err.strip() else "")).strip()
    except Exception as e:
        return f"[ERROR]: {e}"


def try_usg():
    """Try connecting to USG with various credentials."""
    print("=" * 60)
    print("  USG-3P Configuration Dump")
    print("=" * 60)

    # Credentials to try (in order of likelihood post-reset)
    creds = [
        ("ubnt", "ubnt"),           # Factory default
        ("admin", ""),              # Some firmware versions
        ("admin", "admin"),         # Alternative default
        ("ops", "exampleswitchpass"),  # Pre-reset password from CSV
        ("root", "ubnt"),           # Root default
    ]

    for user, pwd in creds:
        print(f"\nTrying {user}/{pwd or '(empty)'}...")
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(HOST, port=22, username=user, password=pwd,
                     timeout=10, banner_timeout=30, auth_timeout=10,
                     allow_agent=False, look_for_keys=False)
            print(f"SUCCESS! Connected as {user}")

            commands = [
                "show interfaces",
                "show configuration commands | head -100",
                "show nat rules",
                "show dhcp leases",
                "show ip route",
                "show arp",
                "show version",
            ]
            for cmd in commands:
                print(f"\n>>> {cmd}")
                print(run_cmd(c, cmd))

            c.close()
            return True
        except paramiko.AuthenticationException:
            print(f"  Auth failed")
            time.sleep(2)  # Avoid rate limiting
        except Exception as e:
            print(f"  Error: {e}")
            time.sleep(3)

    print("\nAll USG credentials failed!")
    return False


def identify_servers():
    """Identify GPU servers one at a time with delays."""
    print("\n\n" + "=" * 60)
    print("  GPU Server Identification (with rate-limit protection)")
    print("=" * 60)

    # Map server number to expected password from CSV
    # server_num -> password
    pw_map = {
        1: "legacypass01",
        2: "legacypass02",
        3: "legacypass03",
        4: "legacypass04",
        5: "legacypass05",
        6: "legacypass06",
        7: "legacypass16",  # was labeled "7-14"
        8: "legacypass07",
        9: "legacypass08",
        10: "legacypass09",
        11: "legacypass10",
        12: "legacypass11",
        13: "legacypass12",
        14: "legacypass16",  # same as 7?
        15: "legacypass13",
    }
    all_pws = list(dict.fromkeys(pw_map.values()))  # unique, preserve order
    all_pws += ["legacypass14", "legacypass15", "examplenaspass"]

    # Skip .6 (already identified as server6)
    targets = [14, 21, 29, 46, 49, 57, 100, 102]

    for ip_suffix in targets:
        ip = f"192.168.1.{ip_suffix}"
        print(f"\n--- {ip} ---")
        found = False

        for pw in all_pws:
            try:
                c = paramiko.SSHClient()
                c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                c.connect(ip, port=22, username="admin", password=pw,
                         timeout=8, banner_timeout=15, auth_timeout=8,
                         allow_agent=False, look_for_keys=False)

                hostname = run_cmd(c, "hostname", timeout=5)
                gpu = run_cmd(c, "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo 'no-gpu'", timeout=10)
                net = run_cmd(c, "ip -4 addr show scope global | grep inet", timeout=5)
                cat_host = run_cmd(c, "cat /etc/hostname", timeout=5)

                print(f"  Password: {pw}")
                print(f"  Hostname: {hostname}")
                print(f"  /etc/hostname: {cat_host}")
                print(f"  GPU: {gpu}")
                print(f"  Network: {net}")
                c.close()
                found = True
                break
            except paramiko.AuthenticationException:
                continue  # Try next password, no delay for auth failure
            except Exception as e:
                err_str = str(e)
                if "banner" in err_str.lower() or "10054" in err_str:
                    # Rate limited or connection reset - wait longer
                    print(f"  Rate limited, waiting 5s...")
                    time.sleep(5)
                else:
                    print(f"  Error: {e}")
                break  # Don't try more passwords on connection error

        if not found:
            print(f"  Could not identify")

        # Delay between servers to avoid rate limiting
        time.sleep(2)


if __name__ == "__main__":
    try_usg()
    identify_servers()
    print("\n=== DONE ===")
