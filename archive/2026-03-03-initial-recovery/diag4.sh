#!/usr/bin/env bash

echo "=== Port scan 192.168.1.100 (all useful ports) ==="
for PORT in 22 80 443 5000 5001 8080 8443 8880 9090 3389 139 445 548 111 2049 9000; do
    timeout 2 bash -c "echo > /dev/tcp/192.168.1.100/$PORT" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo ".100:$PORT OPEN"
    else
        echo ".100:$PORT closed"
    fi
done

echo ""
echo "=== Port scan 192.168.1.102 ==="
for PORT in 22 80 443 3389 5000 8080 8443 8888 9090; do
    timeout 2 bash -c "echo > /dev/tcp/192.168.1.102/$PORT" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo ".102:$PORT OPEN"
    else
        echo ".102:$PORT closed"
    fi
done

echo ""
echo "=== Scan all DHCP devices for SSH (port 22) ==="
for i in 6 9 14 21 29 39 43 45 46 49 55 56 57 58 76; do
    timeout 2 bash -c "echo > /dev/tcp/192.168.1.$i/22" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "192.168.1.$i:22 SSH-OPEN (likely a server!)"
    else
        echo "192.168.1.$i:22 no-ssh"
    fi
done

echo ""
echo "=== Scan DHCP devices for common GPU server ports ==="
for i in 6 9 14 21 29 39 43 45 46 49 55 56 57 58 76; do
    HAS_PORT=""
    for PORT in 22 3389 8888 6006; do
        timeout 1 bash -c "echo > /dev/tcp/192.168.1.$i/$PORT" 2>/dev/null
        if [ $? -eq 0 ]; then
            HAS_PORT="$HAS_PORT $PORT"
        fi
    done
    if [ -n "$HAS_PORT" ]; then
        echo "192.168.1.$i OPEN:$HAS_PORT"
    else
        echo "192.168.1.$i no-known-ports"
    fi
done

echo ""
echo "=== SSH banner grab on .100 and .102 ==="
echo "--- .100 ---"
timeout 3 bash -c "cat < /dev/tcp/192.168.1.100/22" 2>/dev/null &
PID1=$!
sleep 2
kill $PID1 2>/dev/null
wait $PID1 2>/dev/null

echo ""
echo "--- .102 ---"
timeout 3 bash -c "cat < /dev/tcp/192.168.1.102/22" 2>/dev/null &
PID2=$!
sleep 2
kill $PID2 2>/dev/null
wait $PID2 2>/dev/null

echo ""
echo "=== DONE ==="
