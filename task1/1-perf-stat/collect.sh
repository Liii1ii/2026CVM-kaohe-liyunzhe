#!/bin/bash
#
# collect.sh — 一键采集脚本
# 功能：
#   1. 调用 capture_env.sh 采集环境基线数据
#   2. 调用 smoke_test.sh 运行 5 个微基准负载 × 3 次，采集 perf stat 数据
#   3. 验证采集结果完整性
#
# 使用方法:
#   bash collect.sh
#
# 输出:
#   environment/   — 7 个环境基线文件
#   results_raw/   — 15 个 perf stat 原始数据文件
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "============================================"
echo "  CVM 性能测评 — 一键采集"
echo "  采集时间: $TIMESTAMP"
echo "  工作目录: $SCRIPT_DIR"
echo "============================================"
echo ""

# ============================================================
# 阶段一：环境基线采集
# ============================================================
echo "============================================"
echo "  阶段一：环境基线采集"
echo "============================================"
bash "$SCRIPT_DIR/capture_env.sh"
echo ""

# ============================================================
# 阶段二：负载 perf stat 采集
# ============================================================
echo "============================================"
echo "  阶段二：负载 perf stat 采集"
echo "============================================"
bash "$SCRIPT_DIR/smoke_test.sh"
echo ""

# ============================================================
# 阶段三：结果验证
# ============================================================
echo "============================================"
echo "  阶段三：结果验证"
echo "============================================"

# 验证 environment/ 目录
ENV_DIR="$SCRIPT_DIR/environment"
EXPECTED_ENV_FILES=(
    "cpu_info.txt"
    "kernel_info.txt"
    "virt_type.txt"
    "memory_info.txt"
    "numa_info.txt"
    "cpupower_info.txt"
    "timestamp.txt"
)

echo ""
echo "--- 环境基线数据验证 ---"
env_ok=true
for f in "${EXPECTED_ENV_FILES[@]}"; do
    if [ -f "$ENV_DIR/$f" ]; then
        echo "  [OK] $f"
    else
        echo "  [MISSING] $f"
        env_ok=false
    fi
done

# 验证 results_raw/ 目录
RAW_DIR="$SCRIPT_DIR/results_raw"
WORKLOADS=("int64" "matrixprod" "read64" "randset" "queens")
RUNS=3

echo ""
echo "--- perf stat 原始数据验证 ---"
raw_ok=true
for workload in "${WORKLOADS[@]}"; do
    for run in $(seq 1 $RUNS); do
        file="$RAW_DIR/${workload}_run${run}.txt"
        if [ -f "$file" ]; then
            # 检查文件是否包含 perf stat 输出
            if grep -q "Performance counter stats" "$file" 2>/dev/null; then
                echo "  [OK] ${workload}_run${run}.txt"
            else
                echo "  [WARN] ${workload}_run${run}.txt 存在但内容可能不完整"
                raw_ok=false
            fi
        else
            echo "  [MISSING] ${workload}_run${run}.txt"
            raw_ok=false
        fi
    done
done

echo ""
echo "============================================"
echo "  采集完成"
echo "============================================"

if $env_ok; then
    echo "  环境基线数据: 全部 7 个文件已生成"
else
    echo "  环境基线数据: 存在缺失，请检查"
fi

if $raw_ok; then
    echo "  perf stat 数据: 全部 15 个文件已生成"
else
    echo "  perf stat 数据: 存在缺失，请检查"
fi

echo ""
echo "  环境基线文件:"
ls -la "$ENV_DIR"/*.txt 2>/dev/null || echo "  (无文件)"
echo ""
echo "  perf 原始数据文件:"
ls -la "$RAW_DIR"/*.txt 2>/dev/null || echo "  (无文件)"
echo "============================================"