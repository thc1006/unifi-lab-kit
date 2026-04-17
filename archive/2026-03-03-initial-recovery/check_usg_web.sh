#!/usr/bin/env bash

echo "=== USG LAN-side port check (192.168.1.1) ==="
for PORT in 22 80 443 8080 8443 8880; do
    timeout 2 bash -c "echo > /dev/tcp/192.168.1.1/$PORT" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "192.168.1.1:$PORT OPEN"
    else
        echo "192.168.1.1:$PORT closed"
    fi
done

echo ""
echo "=== Try HTTP GET on USG LAN ==="
echo "--- http://192.168.1.1 ---"
timeout 5 bash -c "exec 3<>/dev/tcp/192.168.1.1/80; echo -e 'GET / HTTP/1.0\r\nHost: 192.168.1.1\r\n\r\n' >&3; cat <&3" 2>/dev/null | head -20

echo ""
echo "--- https check (port 443) ---"
timeout 5 bash -c "exec 3<>/dev/tcp/192.168.1.1/443; echo -e 'GET / HTTP/1.0\r\nHost: 192.168.1.1\r\n\r\n' >&3; cat <&3" 2>/dev/null | head -20

echo ""
echo "=== Wider search: any device with port 8443 (full range) ==="
for i in $(seq 1 254); do
    timeout 1 bash -c "echo > /dev/tcp/192.168.1.$i/8443" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "192.168.1.$i:8443 OPEN <-- CONTROLLER!"
    fi
done

echo ""
echo "=== DONE ==="
