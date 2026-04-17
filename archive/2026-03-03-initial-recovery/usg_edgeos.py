#!/usr/bin/env python3
"""Try EdgeOS Web UI login and SSH with legacy algorithms."""
import urllib3
import requests
import paramiko
import socket

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HOST = "192.168.1.1"

# === Part 1: EdgeOS Web UI API ===
print("=" * 60)
print("Part 1: EdgeOS Web UI Login Attempts")
print("=" * 60)

# Passwords to try on the EdgeOS web UI
creds = [
    ("ubnt", "ubnt"),
    ("admin", ""),
    ("root", "ubnt"),
    ("ops", "exampleswitchpass"),
    ("ops", "examplewifipass"),
    ("ops", "examplepass"),
    ("ops", "exampleunifipass"),
]

session = requests.Session()
session.verify = False

for user, pwd in creds:
    label = f"{user}/{pwd or '(empty)'}"
    try:
        # EdgeOS uses POST to / with username/password form data
        r = session.post(
            f"https://{HOST}/",
            data={"username": user, "password": pwd},
            timeout=10,
            allow_redirects=False
        )
        print(f"  {label}: HTTP {r.status_code}, Location: {r.headers.get('Location', 'none')}")
        
        # If we get a redirect to /index.html or a 303, login succeeded
        if r.status_code in (302, 303) and 'index' in r.headers.get('Location', ''):
            print(f"  >>> LOGIN SUCCESS: {label} <<<")
            
            # Try to get system info
            try:
                info = session.get(f"https://{HOST}/api/edge/data.json?data=sys_info", timeout=10)
                print(f"  System info: {info.text[:500]}")
            except Exception as e:
                print(f"  System info error: {e}")
            break
        
        # Also try the EdgeOS API endpoint directly
        r2 = session.post(
            f"https://{HOST}/api/edge/auth.json",
            json={"username": user, "password": pwd},
            timeout=10
        )
        if r2.status_code == 200 and '"success"' in r2.text.lower():
            print(f"  >>> API LOGIN SUCCESS: {label} <<<")
            break
            
    except requests.exceptions.ConnectionError as e:
        print(f"  {label}: Connection error - {e}")
        break
    except Exception as e:
        print(f"  {label}: {type(e).__name__}: {e}")

print()

# === Part 2: SSH with legacy algorithms ===
print("=" * 60)
print("Part 2: SSH with Legacy Algorithms")
print("=" * 60)

ssh_creds = [
    ("ubnt", "ubnt"),
    ("ops", "exampleswitchpass"),
    ("ops", "examplewifipass"),
]

for user, pwd in ssh_creds:
    label = f"{user}/{pwd}"
    print(f"\n  Trying SSH: {label}")
    try:
        sock = socket.create_connection((HOST, 22), timeout=10)
        t = paramiko.Transport(sock)
        t.banner_timeout = 30
        
        # Get server banner
        t.start_client()
        
        # Try authentication
        t.auth_password(user, pwd)
        
        if t.is_authenticated():
            print(f"  >>> SSH SUCCESS: {label} <<<")
            c = paramiko.SSHClient()
            c._transport = t
            
            # Set inform URL
            print("\n  Setting inform URL...")
            _, stdout, stderr = c.exec_command(
                "mca-cli-op set-param mgmt.is_default false && "
                "set-inform http://192.168.1.60:8080/inform",
                timeout=15
            )
            out = stdout.read().decode()
            err = stderr.read().decode()
            print(f"  Output: {out}")
            if err:
                print(f"  Stderr: {err}")
            
            # Show current info
            _, stdout, _ = c.exec_command("info", timeout=10)
            print(f"  Info: {stdout.read().decode()}")
            
            c.close()
            break
        else:
            print(f"  Auth failed")
            t.close()
    except paramiko.AuthenticationException:
        print(f"  Auth rejected")
    except Exception as e:
        print(f"  Error: {type(e).__name__}: {e}")

print("\n=== DONE ===")
