#!/usr/bin/env bash

echo "=== Ping sweep 203.0.113.21-35 ==="
for i in 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35; do
    IP="203.0.113.$i"
    if ping -c 1 -W 1 "$IP" > /dev/null 2>&1; then
        echo "$IP UP"
    else
        echo "$IP DOWN"
    fi
done

echo ""
echo "=== Ping sweep 192.168.1.1 and .100-.120 ==="
for i in 1 100 101 102 103 104 105 106 107 108 109 110 111 112 113 114 115 116 117 118 119 120 200 250 254; do
    IP="192.168.1.$i"
    if ping -c 1 -W 1 "$IP" > /dev/null 2>&1; then
        echo "$IP UP"
    else
        echo "$IP DOWN"
    fi
done

echo ""
echo "=== Test SSH ports on 203.0.113.10 ==="
for PORT in 22 80 443 8080 8443 12020 12030 12040 12050 12060 12070 12080 12090 12100 12110 12120 12130 12140 12150 12160 12170 12990; do
    timeout 2 bash -c "echo > /dev/tcp/203.0.113.10/$PORT" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "203.0.113.10:$PORT OPEN"
    else
        echo "203.0.113.10:$PORT CLOSED"
    fi
done

echo ""
echo "=== Test SSH port 22 on internal servers ==="
for i in 101 102 103 104 105 106 107 108 109 110 111 112 113 114 115; do
    IP="192.168.1.$i"
    timeout 2 bash -c "echo > /dev/tcp/$IP/22" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "$IP:22 SSH OPEN"
    else
        echo "$IP:22 SSH CLOSED"
    fi
done

echo ""
echo "=== Traceroute to 203.0.113.10 ==="
traceroute -n -m 10 203.0.113.10 2>/dev/null || tracepath -n 203.0.113.10 2>/dev/null || echo "traceroute not available"

echo ""
echo "=== DNS test ==="
nslookup google.com 2>/dev/null || host google.com 2>/dev/null || echo "DNS tools not available"

echo ""
echo "=== Done ==="
