#!/usr/bin/env bash
# SSH into USG-3P and dump full configuration
# USG runs EdgeOS/Vyatta - use 'show' commands

HOST="192.168.1.1"
USER="ops"
PASS="exampleswitchpass"

# Check if sshpass is available
if ! command -v sshpass > /dev/null 2>&1; then
    echo "Installing sshpass..."
    sudo apt-get update -qq 2>/dev/null
    sudo apt-get install -y -qq sshpass 2>/dev/null
fi

if ! command -v sshpass > /dev/null 2>&1; then
    echo "sshpass not available. Trying expect..."
    # Fallback: use expect-like approach with bash
    echo "Cannot automate SSH without sshpass. Try manually:"
    echo "  ssh ops@192.168.1.1"
    echo "  Password: exampleswitchpass"
    echo ""
    echo "Then run these commands:"
    echo "  show interfaces"
    echo "  show configuration"
    echo "  show nat rules"
    echo "  show dhcp leases"
    exit 1
fi

echo "======================================"
echo "  USG-3P Configuration Dump"
echo "  $(date)"
echo "======================================"

run_cmd() {
    local CMD="$1"
    echo ""
    echo "=== $CMD ==="
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 "$USER@$HOST" "$CMD" 2>/dev/null
}

# Core interface info
run_cmd "show interfaces"

# Full configuration (most important!)
run_cmd "show configuration"

# NAT rules (port forwarding)
run_cmd "show nat rules"
run_cmd "show nat translations"

# DHCP leases (identify servers!)
run_cmd "show dhcp leases"

# Firewall rules
run_cmd "show firewall"

# System info
run_cmd "show system uptime"
run_cmd "show version"

# Routing table
run_cmd "show ip route"

# ARP table (MAC addresses!)
run_cmd "show arp"

echo ""
echo "======================================"
echo "  Done!"
echo "======================================"
