#!/usr/bin/env python3
"""Try all known passwords on server21."""
import paramiko
import time

IP = "192.168.1.121"
users = ["ops", "admin", "root", "admin", "ubuntu"]
passwords = [
    "examplepass",
    "legacypass01",
    "legacypass02",
    "legacypass03",
    "legacypass04",
    "legacypass05",
    "legacypass06",
    "legacypass16",
    "legacypass07",
    "legacypass08",
    "legacypass09",
    "legacypass10",
    "legacypass11",
    "legacypass12",
    "legacypass13",
    "legacypass14",
    "legacypass15",
    "examplenaspass",
    "exampleswitchpass",
    "exampleunifipass",
    "mllab912_router",
    "mllabasus",
]

print(f"Trying {len(users)} users x {len(passwords)} passwords on {IP}...")
print()

found = False
for user in users:
    if found:
        break
    print(f"  User: {user}")
    for pw in passwords:
        time.sleep(1)  # avoid rate limit
        try:
            j = paramiko.SSHClient()
            j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            j.connect(IP, username=user, password=pw, timeout=8, banner_timeout=8, auth_timeout=8)
            _, out, _ = j.exec_command("hostname", timeout=3)
            hostname = out.read().decode().strip()
            print(f"    SUCCESS!  user={user}  pw={pw}  hostname={hostname}")
            j.close()
            found = True
            break
        except paramiko.AuthenticationException:
            print(f"    {pw[:20]:20s}  auth failed")
        except Exception as e:
            err = str(e)[:50]
            print(f"    {pw[:20]:20s}  error: {err}")
            time.sleep(3)  # extra wait on connection errors

if not found:
    print("\nAll combinations failed.")
