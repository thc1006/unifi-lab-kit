#!/usr/bin/env python3
"""Full scan: ping sweep + SSH on port 22 AND legacy ports for all IPs."""
import socket
import subprocess
import sys

# Ping sweep entire subnet first
print("Ping sweep 192.168.1.1-254...")
alive_ips = []
for i in range(1, 255):
    ip = f"192.168.1.{i}"
    r = subprocess.run(
        ["ping", "-n", "1", "-w", "400", ip],
        capture_output=True,
    )
    if "TTL=" in r.stdout.decode(errors="replace"):
        alive_ips.append(i)
        sys.stdout.write(f"  .{i}")
        sys.stdout.flush()

print(f"\n\nAlive: {len(alive_ips)} devices")
print(f"IPs: {', '.join(f'.{i}' for i in alive_ips)}")

# For each alive IP, check SSH on port 22 + legacy port
print("\n" + "=" * 70)
print(f"{'IP':<18} {'Port 22':<12} {'Legacy':<20} {'Other ports'}")
print("=" * 70)

known = {
    1: "USG", 106: "server6", 108: "server8", 109: "server9",
    115: "server15", 120: "server20", 121: "server21", 122: "server22",
    123: "Pro6000", 129: "NAS",
}

for i in alive_ips:
    ip = f"192.168.1.{i}"
    label = known.get(i, "")

    # Port 22
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.5)
    p22 = "OPEN" if s.connect_ex((ip, 22)) == 0 else "-"
    s.close()

    # Legacy port (12000 + suffix*10)
    legacy_port = None
    legacy_status = "-"
    # Try multiple legacy port patterns
    candidates = []
    if i <= 20:
        candidates.append(12000 + i * 10)
    if 100 <= i <= 130:
        candidates.append(12000 + (i - 100) * 10)
    # Also try the exact mapping from server-0.csv
    for lp in candidates:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        if s.connect_ex((ip, lp)) == 0:
            legacy_port = lp
            legacy_status = f":{lp} OPEN"
        s.close()

    # For unknown devices, also scan common SSH ports
    other = ""
    if not label and p22 == "-":
        for port in [2222, 8022, 12010, 12020, 12030, 12040, 12050,
                     12060, 12070, 12080, 12090, 12100, 12110, 12120,
                     12130, 12140, 12150, 12160, 12170, 12200, 12210,
                     12220, 12230]:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.8)
            if s.connect_ex((ip, port)) == 0:
                other += f":{port} "
            s.close()

    tag = f"  ({label})" if label else ""
    if p22 != "-" or legacy_status != "-" or other:
        print(f"  .{i:<3} {ip:<15} {p22:<12} {legacy_status:<20} {other}{tag}")
    elif not label:
        print(f"  .{i:<3} {ip:<15} no SSH{' '*26}{tag}")
