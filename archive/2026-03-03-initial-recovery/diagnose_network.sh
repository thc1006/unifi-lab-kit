#!/bin/bash
# ============================================================
# 實驗室網路診斷腳本 - 在接到 UniFi Switch 的筆電上執行
# 使用方式: bash diagnose_network.sh
# 需要: nmap (apt install nmap / brew install nmap)
# ============================================================

echo "=========================================="
echo "  ML Lab 網路診斷報告"
echo "  時間: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# --- 1. 本機網路介面資訊 ---
echo "=== 1. 本機網路介面 ==="
ip addr show 2>/dev/null || ipconfig 2>/dev/null
echo ""

# --- 2. 確認能到 USG LAN ---
echo "=== 2. Ping USG LAN (192.168.1.1) ==="
ping -c 3 192.168.1.1 2>/dev/null || ping -n 3 192.168.1.1 2>/dev/null
echo ""

# --- 3. 確認能到 USG WAN ---
echo "=== 3. Ping USG WAN (203.0.113.21) ==="
ping -c 3 203.0.113.21 2>/dev/null || ping -n 3 203.0.113.21 2>/dev/null
echo ""

# --- 4. 確認 .34 和 .33 是否有回應（IP alias 測試） ---
echo "=== 4. Ping WAN IP Alias (.34) ==="
ping -c 3 203.0.113.10 2>/dev/null || ping -n 3 203.0.113.10 2>/dev/null
echo ""

echo "=== 5. Ping WAN IP Alias (.33) ==="
ping -c 3 203.0.113.11 2>/dev/null || ping -n 3 203.0.113.11 2>/dev/null
echo ""

# --- 5. 掃描內網存活設備 ---
echo "=== 6. 內網存活設備掃描 (192.168.1.0/24) ==="
if command -v nmap &>/dev/null; then
    nmap -sn 192.168.1.0/24
elif command -v arp-scan &>/dev/null; then
    sudo arp-scan --localnet
else
    echo "[WARN] nmap 未安裝，改用 ping sweep..."
    for i in $(seq 1 254); do
        (ping -c 1 -W 1 192.168.1.$i &>/dev/null && echo "192.168.1.$i is UP") &
    done
    wait
fi
echo ""

# --- 6. 特別掃描已知伺服器 IP ---
echo "=== 7. 已知伺服器 IP 逐一檢測 ==="
SERVERS=(
    "192.168.1.101:server1"
    "192.168.1.102:server2"
    "192.168.1.103:server3"
    "192.168.1.104:server4"
    "192.168.1.105:server5"
    "192.168.1.106:server6"
    "192.168.1.107:server7"
    "192.168.1.108:server8"
    "192.168.1.109:server9"
    "192.168.1.110:server10"
    "192.168.1.111:server11"
    "192.168.1.112:server12"
    "192.168.1.113:server13"
    "192.168.1.114:server14"
    "192.168.1.115:server15"
)

for entry in "${SERVERS[@]}"; do
    IP="${entry%%:*}"
    NAME="${entry##*:}"
    if ping -c 1 -W 1 "$IP" &>/dev/null 2>&1; then
        echo "  ✅ $NAME ($IP) - REACHABLE"
        # 嘗試檢測 SSH
        if command -v nc &>/dev/null; then
            if nc -z -w2 "$IP" 22 2>/dev/null; then
                echo "     └─ SSH (port 22) OPEN"
            else
                echo "     └─ SSH (port 22) CLOSED/FILTERED"
            fi
        fi
    else
        echo "  ❌ $NAME ($IP) - UNREACHABLE"
    fi
done
echo ""

# --- 7. 檢查 NAS ---
echo "=== 8. NAS 檢測 ==="
echo "  嘗試常見 NAS IP..."
for IP in 192.168.1.100 192.168.1.200 192.168.1.250 192.168.1.99; do
    if ping -c 1 -W 1 "$IP" &>/dev/null 2>&1; then
        echo "  📦 $IP is UP (可能是 NAS)"
    fi
done
echo ""

# --- 8. 檢查 DHCP lease table（如果可以從 USG 拿到） ---
echo "=== 9. 本機 ARP 表 ==="
arp -a 2>/dev/null || ip neigh show 2>/dev/null
echo ""

# --- 9. 路由表 ---
echo "=== 10. 路由表 ==="
ip route show 2>/dev/null || route print 2>/dev/null || netstat -rn 2>/dev/null
echo ""

# --- 10. 測試 Port Forward (嘗試從內網連 .34 的 port) ---
echo "=== 11. Port Forward 測試 (從內網連 203.0.113.10) ==="
if command -v nc &>/dev/null; then
    for PORT in 12020 12030 12040 12050 12060 12080 12090 12100 12110 12120 12130; do
        if nc -z -w2 203.0.113.10 "$PORT" 2>/dev/null; then
            echo "  ✅ Port $PORT - OPEN"
        else
            echo "  ❌ Port $PORT - CLOSED/TIMEOUT"
        fi
    done
else
    echo "  [WARN] nc 未安裝，跳過 port 測試"
fi
echo ""

# --- 11. DNS 測試 ---
echo "=== 12. DNS 解析測試 ==="
nslookup google.com 2>/dev/null || dig google.com +short 2>/dev/null || echo "DNS test tools not available"
echo ""

echo "=========================================="
echo "  診斷完成！請將以上結果提供給我分析"
echo "=========================================="
