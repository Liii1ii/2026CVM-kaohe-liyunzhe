#!/bin/bash
#
# capture_env.sh — 环境基线快照脚本
# 自动采集系统信息并尝试锁定 CPU 频率至 performance 模式
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_DIR="$SCRIPT_DIR/environment"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

mkdir -p "$ENV_DIR"

# 辅助函数：写入带时间戳的文件头
write_header() {
    local file="$1"
    echo "# Captured at: $TIMESTAMP" > "$file"
}

echo "============================================"
echo "  环境基线快照采集开始"
echo "  采集时间: $TIMESTAMP"
echo "  输出目录: $ENV_DIR"
echo "============================================"

# 1. cpu_info.txt
echo "[1/7] 采集 CPU 信息..."
OUTFILE="$ENV_DIR/cpu_info.txt"
write_header "$OUTFILE"
{
    echo ""
    echo "===== lscpu ====="
    lscpu 2>&1
    echo ""
    echo "===== /proc/cpuinfo (model name & flags) ====="
    grep -E "^(model name|flags)" /proc/cpuinfo 2>&1 || true
} >> "$OUTFILE"
echo "  -> cpu_info.txt 完成"

# 2. kernel_info.txt
echo "[2/7] 采集内核信息..."
OUTFILE="$ENV_DIR/kernel_info.txt"
write_header "$OUTFILE"
{
    echo ""
    uname -a
} >> "$OUTFILE"
echo "  -> kernel_info.txt 完成"

# 3. virt_type.txt
echo "[3/7] 检测虚拟化类型..."
OUTFILE="$ENV_DIR/virt_type.txt"
write_header "$OUTFILE"
{
    echo ""
    if command -v systemd-detect-virt &>/dev/null; then
        systemd-detect-virt
    else
        echo "unknown"
    fi
} >> "$OUTFILE"
echo "  -> virt_type.txt 完成"

# 4. memory_info.txt
echo "[4/7] 采集内存信息..."
OUTFILE="$ENV_DIR/memory_info.txt"
write_header "$OUTFILE"
{
    echo ""
    free -h
} >> "$OUTFILE"
echo "  -> memory_info.txt 完成"

# 5. numa_info.txt
echo "[5/7] 采集 NUMA 信息..."
OUTFILE="$ENV_DIR/numa_info.txt"
write_header "$OUTFILE"
{
    echo ""
    if command -v numactl &>/dev/null; then
        numactl --hardware 2>&1
    else
        echo "numactl not available"
    fi
} >> "$OUTFILE"
echo "  -> numa_info.txt 完成"

# 6. cpupower_info.txt
echo "[6/7] 采集 CPU 频率策略及锁频状态..."
OUTFILE="$ENV_DIR/cpupower_info.txt"
write_header "$OUTFILE"
{
    echo ""
    if command -v cpupower &>/dev/null; then
        cpupower frequency-info 2>&1
    else
        echo "cpupower command not found"
    fi
} >> "$OUTFILE"
echo "  -> cpupower_info.txt 完成"

# 7. timestamp.txt
echo "[7/7] 记录采集时间戳..."
OUTFILE="$ENV_DIR/timestamp.txt"
write_header "$OUTFILE"
{
    echo ""
    echo "采集时间 (本地): $TIMESTAMP"
    echo "采集时间 (UTC) : $(date -u '+%Y-%m-%d %H:%M:%S')"
    echo "Unix 时间戳    : $(date +%s)"
} >> "$OUTFILE"
echo "  -> timestamp.txt 完成"

# 尝试锁定 CPU 频率至 performance 模式
echo ""
echo "尝试锁定 CPU 频率至 performance 模式..."
if command -v cpupower &>/dev/null; then
    if sudo cpupower frequency-set -g performance 2>"$ENV_DIR/freq_warning.txt"; then
        echo "  -> 频率锁定成功 (performance)"
        rm -f "$ENV_DIR/freq_warning.txt"
    else
        echo "  -> 频率锁定失败，详细信息见 freq_warning.txt"
        sed -i "1i# Captured at: $TIMESTAMP" "$ENV_DIR/freq_warning.txt"
    fi
else
    echo "  -> cpupower 命令不存在，跳过频率锁定"
    {
        echo "# Captured at: $TIMESTAMP"
        echo ""
        echo "cpupower: command not found"
        echo "本次数据未锁定频率，存在 Turbo Boost 干扰可能"
    } > "$ENV_DIR/freq_warning.txt"
    echo "  -> freq_warning.txt 已生成"
fi

echo ""
echo "============================================"
echo "  环境基线快照采集完成"
echo "  输出文件列表:"
ls -la "$ENV_DIR"/*.txt 2>/dev/null || true
if [ -f "$ENV_DIR/freq_warning.txt" ]; then
    ls -la "$ENV_DIR/freq_warning.txt"
fi
echo "============================================"