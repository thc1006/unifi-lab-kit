#!/usr/bin/env bash
# Quick TCP reachability sweep — no credentials, no nmap required.
# Reads targets from .env (WAN_IP, LAN_SUBNET_PREFIX). Falls back to defaults.

set -u

if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
fi

WAN_IP="${WAN_IP:-<WAN_IP>}"
LAN_SUBNET_PREFIX="${LAN_SUBNET_PREFIX:-192.168.1}"

probe() {
    local target="$1" port="$2" label="$3"
    if timeout 2 bash -c "echo > /dev/tcp/$target/$port" >/dev/null 2>&1; then
        echo "$target:$port  OPEN    $label"
    else
        echo "$target:$port  CLOSED  $label"
    fi
}

echo "=== Internal SSH 22 on servers ==="
for i in $(seq 101 125); do
    probe "${LAN_SUBNET_PREFIX}.$i" 22 ""
done

if [ "$WAN_IP" != "<WAN_IP>" ]; then
    echo
    echo "=== WAN port-forwards on $WAN_IP ==="
    for port in 22 12060 12080 12090 12110 12130 12150 12200 12210 12220 12230 12990; do
        probe "$WAN_IP" "$port" ""
    done
fi

echo
echo "=== DNS ==="
nslookup google.com 2>/dev/null || dig google.com +short 2>/dev/null || echo "no DNS tool"
