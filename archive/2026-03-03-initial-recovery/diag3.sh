#!/usr/bin/env bash
set -e

echo "=== Full LAN sweep 192.168.1.1-254 ==="
for i in $(seq 1 254); do
    (ping -c 1 -W 1 "192.168.1.$i" > /dev/null 2>&1 && echo "192.168.1.$i UP") &
done
wait
echo ""

echo "=== Port scan 192.168.1.100 ==="
for PORT in 22 80 443 5000 8080 8443 8880 9090 3389; do
    timeout 2 bash -c "echo > /dev/tcp/192.168.1.100/$PORT" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "192.168.1.100:$PORT OPEN"
    else
        echo "192.168.1.100:$PORT CLOSED"
    fi
done
echo ""

echo "=== Port scan 192.168.1.102 ==="
for PORT in 22 80 443 3389 5000 8080 8443 8888 9090; do
    timeout 2 bash -c "echo > /dev/tcp/192.168.1.102/$PORT" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "192.168.1.102:$PORT OPEN"
    else
        echo "192.168.1.102:$PORT CLOSED"
    fi
done
echo ""

echo "=== USG WAN interface check via SSH (will fail without password) ==="
timeout 5 ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 -o BatchMode=yes ops@192.168.1.1 "show interfaces" 2>&1 || echo "SSH needs interactive password"
echo ""

echo "=== Check what Windows host IP is ==="
cat /proc/net/arp 2>/dev/null || echo "No ARP table in proc"
ip neigh show 2>/dev/null
echo ""

echo "=== Test connectivity from internal to .34 port forwards ==="
echo "Testing if NAT hairpin works..."
timeout 2 bash -c "echo > /dev/tcp/203.0.113.10/22" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "203.0.113.10:22 reachable from LAN (USG SSH or hairpin)"
fi
echo ""

echo "=== DONE ==="
