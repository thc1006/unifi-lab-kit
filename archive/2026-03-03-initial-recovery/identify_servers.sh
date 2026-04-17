#!/usr/bin/env bash

echo "=== GPU Server Fingerprinting via SSH Banner + nvidia-smi ==="
echo "Attempting to identify servers by SSH into each and checking GPU..."
echo ""

# All IPs with SSH open (discovered from scan)
SSH_HOSTS="6 14 21 29 39 46 49 57 100 102"

# Try to grab SSH host key fingerprint (unique per machine, no auth needed)
echo "=== SSH Host Key Fingerprints (no auth required) ==="
for i in $SSH_HOSTS; do
    IP="192.168.1.$i"
    echo -n "$IP: "
    timeout 3 ssh-keyscan -t ed25519 "$IP" 2>/dev/null | awk '{print $3}' || echo "timeout"
done
echo ""

# Try to get SSH banner (already got some, but let's get all)
echo "=== SSH Banners ==="
for i in $SSH_HOSTS; do
    IP="192.168.1.$i"
    echo -n "$IP: "
    timeout 3 bash -c "cat < /dev/tcp/$IP/22" 2>/dev/null &
    PID=$!
    sleep 1
    kill $PID 2>/dev/null
    wait $PID 2>/dev/null
done
echo ""

# Check if sshpass is available for automated login
if command -v sshpass > /dev/null 2>&1; then
    echo "sshpass available, attempting automated identification..."

    # Try common password patterns from CSV
    PASSWORDS="legacypass01 legacypass02 legacypass03 legacypass04 legacypass05 legacypass06 legacypass16 legacypass07 legacypass08 legacypass09 legacypass10 legacypass11 legacypass12 legacypass13 legacypass14 legacypass15 examplenaspass"

    for i in $SSH_HOSTS; do
        IP="192.168.1.$i"
        echo "--- Trying $IP ---"
        for PASS in $PASSWORDS; do
            RESULT=$(timeout 5 sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 "god@$IP" "hostname && nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo 'no-gpu'" 2>/dev/null)
            if [ $? -eq 0 ] && [ -n "$RESULT" ]; then
                echo "$IP: password=$PASS hostname+gpu=$RESULT"
                break
            fi
        done
    done
else
    echo "sshpass not installed. Installing..."
    sudo apt-get update -qq && sudo apt-get install -y -qq sshpass 2>/dev/null

    if command -v sshpass > /dev/null 2>&1; then
        echo "sshpass installed, retrying..."

        PASSWORDS="legacypass01 legacypass02 legacypass03 legacypass04 legacypass05 legacypass06 legacypass16 legacypass07 legacypass08 legacypass09 legacypass10 legacypass11 legacypass12 legacypass13 legacypass14 legacypass15 examplenaspass"

        for i in $SSH_HOSTS; do
            IP="192.168.1.$i"
            echo "--- Trying $IP ---"
            for PASS in $PASSWORDS; do
                RESULT=$(timeout 5 sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 "god@$IP" "hostname && nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo 'no-gpu'" 2>/dev/null)
                if [ $? -eq 0 ] && [ -n "$RESULT" ]; then
                    echo "$IP: password=$PASS hostname+gpu=$RESULT"
                    break
                fi
            done
        done
    else
        echo "Failed to install sshpass. Manual identification needed."
        echo ""
        echo "Run this on each server manually:"
        echo "  ssh admin@192.168.1.X"
        echo "  hostname && nvidia-smi --query-gpu=name,memory.total --format=csv,noheader"
    fi
fi

echo ""
echo "=== DONE ==="
