#!/bin/bash
# ============================================================
# 伺服器端網路診斷腳本 - 在每台 GPU Server 上執行
# 使用方式: bash diagnose_server.sh
# 需要 root 或 sudo 權限來查看完整資訊
# ============================================================

echo "=========================================="
echo "  伺服器網路診斷報告"
echo "  主機名: $(hostname)"
echo "  時間: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# --- 1. 主機名與 OS ---
echo "=== 1. 系統資訊 ==="
echo "Hostname: $(hostname)"
uname -a
echo ""

# --- 2. 所有網路介面 ---
echo "=== 2. 網路介面 ==="
ip addr show 2>/dev/null || ifconfig 2>/dev/null
echo ""

# --- 3. 路由表 ---
echo "=== 3. 路由表 ==="
ip route show 2>/dev/null || route -n 2>/dev/null
echo ""

# --- 4. DNS 設定 ---
echo "=== 4. DNS 設定 ==="
cat /etc/resolv.conf 2>/dev/null
echo ""

# --- 5. 網路設定檔 (netplan / interfaces) ---
echo "=== 5. 網路設定檔 ==="
if [ -d /etc/netplan ]; then
    echo "--- Netplan configs ---"
    for f in /etc/netplan/*.yaml /etc/netplan/*.yml; do
        if [ -f "$f" ]; then
            echo "File: $f"
            cat "$f"
            echo "---"
        fi
    done
elif [ -f /etc/network/interfaces ]; then
    echo "--- /etc/network/interfaces ---"
    cat /etc/network/interfaces
fi
echo ""

# --- 6. NetworkManager 狀態 ---
echo "=== 6. NetworkManager 狀態 ==="
if command -v nmcli &>/dev/null; then
    nmcli device status
    echo ""
    nmcli connection show
else
    echo "NetworkManager not installed"
fi
echo ""

# --- 7. 連通性測試 ---
echo "=== 7. 連通性測試 ==="

echo "  Ping Gateway (192.168.1.1):"
ping -c 2 -W 2 192.168.1.1 2>/dev/null
echo ""

echo "  Ping 外網 (8.8.8.8):"
ping -c 2 -W 2 8.8.8.8 2>/dev/null
echo ""

echo "  DNS 解析 (google.com):"
ping -c 2 -W 2 google.com 2>/dev/null
echo ""

# --- 8. SSH 服務狀態 ---
echo "=== 8. SSH 服務狀態 ==="
systemctl status sshd 2>/dev/null || systemctl status ssh 2>/dev/null || service ssh status 2>/dev/null
echo ""

echo "SSH listening ports:"
ss -tlnp | grep -E ':22\b' 2>/dev/null || netstat -tlnp | grep -E ':22\b' 2>/dev/null
echo ""

# --- 9. 防火牆規則 ---
echo "=== 9. 防火牆規則 ==="
if command -v ufw &>/dev/null; then
    echo "--- UFW Status ---"
    sudo ufw status verbose 2>/dev/null || ufw status verbose 2>/dev/null
fi
echo ""
if command -v iptables &>/dev/null; then
    echo "--- iptables (INPUT chain) ---"
    sudo iptables -L INPUT -n --line-numbers 2>/dev/null || iptables -L INPUT -n 2>/dev/null
fi
echo ""

# --- 10. GPU 狀態 (附帶確認身份) ---
echo "=== 10. GPU 資訊 ==="
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo "nvidia-smi not available"
echo ""

echo "=========================================="
echo "  診斷完成！請將結果回傳"
echo "=========================================="
