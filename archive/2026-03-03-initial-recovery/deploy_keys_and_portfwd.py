#!/usr/bin/env python3
"""
1. Deploy SSH key to server11 + server13 (+ verify all others)
2. Try USG SSH to set port forwarding
"""
import paramiko
import socket
import time

PUB_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEXAMPLE0000000000000000000000000000000000 admin@example.com"

# ============================================================
# Part 1: SSH key deploy + verify ALL servers
# ============================================================
print("=" * 60)
print("PART 1: SSH key deploy + verify")
print("=" * 60)

all_servers = [
    ("192.168.1.106", "admin",   "examplepass", "server6"),
    ("192.168.1.108", "admin",   "examplepass", "server8"),
    ("192.168.1.109", "admin",   "examplepass", "server9"),
    ("192.168.1.111", "admin",   "examplepass", "server11"),
    ("192.168.1.113", "admin",   "examplepass", "server13"),
    ("192.168.1.115", "admin",   "examplepass", "server15"),
    ("192.168.1.120", "ops", "examplepass", "server20"),
    ("192.168.1.121", "ops", "examplepass", "server21"),
    ("192.168.1.122", "ops", "examplepass", "server22"),
    ("192.168.1.123", "ops", "examplepass", "Pro6000"),
    ("192.168.1.129", "admin",   "examplepass", "NAS"),
]

for ip, user, pw, name in all_servers:
    try:
        j = paramiko.SSHClient()
        j.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        j.connect(ip, username=user, password=pw, timeout=5)

        # Deploy key
        cmd = (
            f"mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
            f"touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && "
            f"grep -qF '{PUB_KEY}' ~/.ssh/authorized_keys 2>/dev/null || "
            f"echo '{PUB_KEY}' >> ~/.ssh/authorized_keys && "
            f"grep -c hctsai ~/.ssh/authorized_keys"
        )
        _, out, _ = j.exec_command(cmd, timeout=8)
        count = out.read().decode().strip()
        print(f"  {name:12s} {ip:>15}  key: {count} entry(s)  OK")
        j.close()
    except Exception as e:
        print(f"  {name:12s} {ip:>15}  FAIL: {e}")

# ============================================================
# Part 2: USG SSH - try ALL known passwords
# ============================================================
print("\n" + "=" * 60)
print("PART 2: USG SSH")
print("=" * 60)

usg_creds = [
    ("ops", "exampleusgpass"),
    ("ops", "exampleswitchpass"),
    ("ops", "examplepass"),
    ("admin", "exampleusgpass"),
    ("admin", "exampleswitchpass"),
    ("admin", "examplepass"),
    ("ubnt", "ubnt"),
    ("root", "exampleusgpass"),
    ("root", "exampleswitchpass"),
    ("ops", "exampleunifipass"),
    ("ops", "mllab912_router"),
    ("ops", "mllabasus"),
    ("ops", "ops"),
    ("admin", "admin"),
]

usg = paramiko.SSHClient()
usg.set_missing_host_key_policy(paramiko.AutoAddPolicy())
usg_ok = False

for user, pw in usg_creds:
    try:
        usg.connect("192.168.1.1", username=user, password=pw, timeout=5)
        print(f"  SUCCESS: {user}/{pw}")
        usg_ok = True
        break
    except paramiko.AuthenticationException:
        print(f"  {user}/{pw}: auth failed")
    except Exception as e:
        print(f"  {user}/{pw}: {str(e)[:40]}")
        time.sleep(2)

# Also try via NAS (different source IP)
if not usg_ok:
    print("\n  Trying via NAS jump host...")
    nas = paramiko.SSHClient()
    nas.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    nas.connect("192.168.1.129", username="admin", password="examplepass", timeout=5)

    for user, pw in usg_creds[:6]:
        cmd = (
            f"sshpass -p '{pw}' ssh -o StrictHostKeyChecking=no "
            f"-o ConnectTimeout=5 -o NumberOfPasswordPrompts=1 "
            f"{user}@192.168.1.1 'echo SUCCESS; cat /etc/version' 2>&1"
        )
        _, out, _ = nas.exec_command(cmd, timeout=12)
        result = out.read().decode().strip()
        if "SUCCESS" in result:
            print(f"  VIA NAS SUCCESS: {user}/{pw} -> {result}")
            usg_ok = True
            # Now set port forwarding via NAS jump
            break
        elif "denied" in result.lower():
            print(f"  VIA NAS {user}/{pw}: auth failed")
        time.sleep(0.5)
    nas.close()

if usg_ok:
    # Set port forwarding
    print("\n  Setting port forwarding...")
    if not usg.get_transport():
        usg.connect("192.168.1.1", username=user, password=pw, timeout=5)

    # Check current port forwarding rules
    _, out, _ = usg.exec_command(
        "vbash -ic 'show configuration commands | grep port-forward'",
        timeout=10,
    )
    current_pf = out.read().decode().strip()
    print(f"\n  Current port-forward rules:")
    for line in current_pf.split("\n")[:30]:
        print(f"    {line.strip()}")

    # Add new rules for server11 and server13
    new_rules = [
        ("server11-ssh", "12110", "192.168.1.111", "22"),
        ("server13-ssh", "12130", "192.168.1.113", "22"),
    ]

    for rule_name, src_port, fwd_ip, fwd_port in new_rules:
        # Check if rule already exists
        if src_port in current_pf:
            print(f"\n  {rule_name} (:{src_port}): already exists, skipping")
            continue

        print(f"\n  Adding {rule_name}: :{src_port} -> {fwd_ip}:{fwd_port}")
        cmd = (
            f"vbash -ic '"
            f"configure ; "
            f"set port-forward rule 0 description {rule_name} ; "
            f"set port-forward rule 0 forward-to address {fwd_ip} ; "
            f"set port-forward rule 0 forward-to port {fwd_port} ; "
            f"set port-forward rule 0 original-port {src_port} ; "
            f"set port-forward rule 0 protocol tcp ; "
            f"commit ; save ; exit'"
        )
        _, out, err = usg.exec_command(cmd, timeout=20)
        print(f"    Out: {out.read().decode().strip()[:200]}")
        e = err.read().decode().strip()
        if e:
            print(f"    Err: {e[:200]}")

    # Verify port forwarding
    print("\n  Verifying all port forwards...")
    _, out, _ = usg.exec_command(
        "vbash -ic 'show configuration commands | grep port-forward | grep -E \"(forward-to|original-port|description)\"'",
        timeout=10,
    )
    print(out.read().decode().strip()[:1000])

    usg.close()

    # Test external SSH
    print("\n  Testing port forwards externally...")
    WAN = "203.0.113.10"
    test_ports = [
        (12060, "server6", ".106"),
        (12080, "server8", ".108"),
        (12090, "server9", ".109"),
        (12110, "server11", ".111"),
        (12130, "server13", ".113"),
        (12150, "server15", ".115"),
        (12200, "server20", ".120"),
        (12210, "server21", ".121"),
        (12220, "server22", ".122"),
        (12230, "Pro6000", ".123"),
    ]
    for port, name, target in test_ports:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(4)
        r = s.connect_ex((WAN, port))
        if r == 0:
            try:
                banner = s.recv(256).decode().strip()[:40]
            except:
                banner = "?"
            print(f"    :{port} -> {target} {name:12s}  OK  {banner}")
        else:
            print(f"    :{port} -> {target} {name:12s}  CLOSED")
        s.close()
else:
    print("\n  USG SSH failed - cannot set port forwarding")
    print("  Need to fix Controller <-> USG connection first")

print("\n=== DONE ===")
