#!/usr/bin/env bash
# ============================================================================
#  mllab-network — read-only network diagnostics.
#  Run from anywhere with LAN or WAN reachability. No credentials required.
#
#  Usage: bash scripts/diagnose.sh
#  Needs: ping, plus any of {nmap, arp-scan} for subnet scanning.
# ============================================================================

set -u

# Load .env if present so the script talks about *your* network. Falls back
# to safe defaults for a first read.
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
fi

WAN_IP="${WAN_IP:-<WAN_IP>}"
WAN_GATEWAY="${WAN_GATEWAY:-<WAN_GATEWAY>}"
WAN_IP_ALIAS="${WAN_IP_ALIAS:-}"
LAN_GATEWAY="${LAN_GATEWAY:-192.168.1.1}"
LAN_SUBNET_PREFIX="${LAN_SUBNET_PREFIX:-192.168.1}"

section() {
    echo
    echo "=========================================="
    echo "  $1"
    echo "=========================================="
}

section "1. Local network interfaces"
ip addr show 2>/dev/null || ipconfig 2>/dev/null || ifconfig 2>/dev/null

section "2. Ping LAN gateway ($LAN_GATEWAY)"
ping -c 3 "$LAN_GATEWAY" 2>/dev/null || ping -n 3 "$LAN_GATEWAY" 2>/dev/null

if [ "$WAN_GATEWAY" != "<WAN_GATEWAY>" ]; then
    section "3. Ping WAN gateway ($WAN_GATEWAY)"
    ping -c 3 "$WAN_GATEWAY" 2>/dev/null || ping -n 3 "$WAN_GATEWAY" 2>/dev/null
fi

if [ "$WAN_IP" != "<WAN_IP>" ]; then
    section "4. Ping WAN IP ($WAN_IP)"
    ping -c 3 "$WAN_IP" 2>/dev/null || ping -n 3 "$WAN_IP" 2>/dev/null
fi

if [ -n "$WAN_IP_ALIAS" ]; then
    section "5. Ping WAN alias ($WAN_IP_ALIAS)"
    ping -c 3 "$WAN_IP_ALIAS" 2>/dev/null || ping -n 3 "$WAN_IP_ALIAS" 2>/dev/null
fi

section "6. LAN sweep (${LAN_SUBNET_PREFIX}.0/24)"
if command -v nmap >/dev/null 2>&1; then
    nmap -sn "${LAN_SUBNET_PREFIX}.0/24"
elif command -v arp-scan >/dev/null 2>&1; then
    sudo arp-scan --localnet
else
    echo "nmap / arp-scan not installed; falling back to ping sweep (slow)…"
    for i in $(seq 1 254); do
        ( ping -c 1 -W 1 "${LAN_SUBNET_PREFIX}.$i" >/dev/null 2>&1 \
            && echo "${LAN_SUBNET_PREFIX}.$i is UP" ) &
    done
    wait
fi

section "7. Known server SSH reachability"
for i in $(seq 101 125); do
    ip="${LAN_SUBNET_PREFIX}.$i"
    if command -v nc >/dev/null 2>&1; then
        if nc -z -w2 "$ip" 22 2>/dev/null; then
            echo "  $ip:22  OPEN"
        fi
    else
        if timeout 2 bash -c "echo > /dev/tcp/$ip/22" 2>/dev/null; then
            echo "  $ip:22  OPEN"
        fi
    fi
done

section "8. ARP table"
arp -a 2>/dev/null || ip neigh show 2>/dev/null

section "9. Routing table"
ip route show 2>/dev/null || route print 2>/dev/null || netstat -rn 2>/dev/null

if [ "$WAN_IP" != "<WAN_IP>" ]; then
    section "10. Port-forward probe on $WAN_IP"
    for port in 12060 12080 12090 12110 12130 12150 12200 12210 12220 12230 12990; do
        if command -v nc >/dev/null 2>&1; then
            if nc -z -w2 "$WAN_IP" "$port" 2>/dev/null; then
                echo "  :$port  OPEN"
            else
                echo "  :$port  CLOSED/TIMEOUT"
            fi
        fi
    done
fi

section "11. DNS sanity"
nslookup google.com 2>/dev/null || dig google.com +short 2>/dev/null || \
    echo "no DNS tools installed"

echo
echo "=========================================="
echo "  Diagnostics complete"
echo "=========================================="
