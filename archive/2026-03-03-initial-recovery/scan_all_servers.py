#!/usr/bin/env python3
"""Scan all servers on both port 22 and legacy ports."""
import socket

servers = [
    ("server1",  ".101", "192.168.1.101", 12010),
    ("server2",  ".102", "192.168.1.102", 12020),
    ("server3",  ".103", "192.168.1.103", 12030),
    ("server4",  ".104", "192.168.1.104", 12040),
    ("server5",  ".105", "192.168.1.105", 12050),
    ("server6",  ".106", "192.168.1.106", 12060),
    ("server7",  ".107", "192.168.1.107", 12070),
    ("server8",  ".108", "192.168.1.108", 12080),
    ("server9",  ".109", "192.168.1.109", 12090),
    ("server10", ".110", "192.168.1.110", 12100),
    ("server11", ".111", "192.168.1.111", 12110),
    ("server12", ".112", "192.168.1.112", 12120),
    ("server13", ".113", "192.168.1.113", 12130),
    ("server14", ".114", "192.168.1.114", 12140),
    ("server15", ".115", "192.168.1.115", 12150),
    ("server20", ".120", "192.168.1.120", 12200),
    ("server21", ".121", "192.168.1.121", 12210),
    ("server22", ".122", "192.168.1.122", 12220),
    ("Pro6000",  ".123", "192.168.1.123", 12230),
    ("NAS",      ".129", "192.168.1.129", None),
]

print(f"{'Server':<12} {'IP':<17} {'Port 22':<25} {'Legacy Port':<25}")
print("-" * 80)

for name, short, ip, legacy_port in servers:
    # Check port 22
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.5)
    r22 = s.connect_ex((ip, 22))
    if r22 == 0:
        try:
            banner22 = s.recv(256).decode().strip()[:40]
        except:
            banner22 = "connected"
        p22 = f"OPEN  {banner22}"
    else:
        p22 = "CLOSED"
    s.close()

    # Check legacy port
    if legacy_port:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.5)
        rL = s.connect_ex((ip, legacy_port))
        if rL == 0:
            try:
                bannerL = s.recv(256).decode().strip()[:40]
            except:
                bannerL = "connected"
            pL = f":{legacy_port} OPEN  {bannerL}"
        else:
            pL = f":{legacy_port} CLOSED"
        s.close()
    else:
        pL = "-"

    print(f"{name:<12} {ip:<17} {p22:<25} {pL}")
