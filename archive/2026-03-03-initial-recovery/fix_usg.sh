#!/usr/bin/env bash

echo "=== 1. Try SSH to USG with default credentials ==="
echo "Trying ubnt/ubnt (factory default)..."
timeout 5 ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 -o BatchMode=yes -o PubkeyAuthentication=no ubnt@192.168.1.1 "echo AUTH_SUCCESS" 2>&1
echo "exit: $?"

echo ""
echo "Trying admin/admin..."
timeout 5 ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 -o BatchMode=yes -o PubkeyAuthentication=no admin@192.168.1.1 "echo AUTH_SUCCESS" 2>&1
echo "exit: $?"

echo ""
echo "Trying mllab with old password..."
timeout 5 ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 -o BatchMode=yes -o PubkeyAuthentication=no ops@192.168.1.1 "echo AUTH_SUCCESS" 2>&1
echo "exit: $?"

echo ""
echo "Trying root/ubnt..."
timeout 5 ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 -o BatchMode=yes -o PubkeyAuthentication=no root@192.168.1.1 "echo AUTH_SUCCESS" 2>&1
echo "exit: $?"

echo ""
echo "=== 2. USG SSH Banner ==="
timeout 3 bash -c "cat < /dev/tcp/192.168.1.1/22" 2>/dev/null &
PID=$!
sleep 2
kill $PID 2>/dev/null
wait $PID 2>/dev/null

echo ""
echo "=== 3. Scan for UniFi Controller (port 8443) on LAN ==="
echo "Scanning all alive hosts for port 8443..."
for i in 1 6 9 14 21 29 39 43 45 46 49 55 56 57 58 76 100 102; do
    timeout 2 bash -c "echo > /dev/tcp/192.168.1.$i/8443" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "192.168.1.$i:8443 OPEN  <-- UniFi Controller HERE!"
    fi
done

echo ""
echo "Scanning for port 8080 (inform)..."
for i in 1 6 9 14 21 29 39 43 45 46 49 55 56 57 58 76 100 102; do
    timeout 2 bash -c "echo > /dev/tcp/192.168.1.$i/8080" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "192.168.1.$i:8080 OPEN  <-- Controller inform port"
    fi
done

echo ""
echo "=== 4. Check USG inform URL (port 8080 on USG) ==="
timeout 2 bash -c "echo > /dev/tcp/192.168.1.1/8080" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "USG:8080 OPEN (USG proxying inform?)"
else
    echo "USG:8080 closed"
fi

echo ""
echo "=== DONE ==="
