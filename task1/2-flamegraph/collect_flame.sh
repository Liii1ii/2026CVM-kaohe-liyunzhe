#!/bin/bash
#
# collect_flame.sh — 火焰图数据采集与生成脚本（任务1.2）
#
# 功能：
#   1. 采集 matrixprod（计算密集型）的 perf record 调用栈
#   2. 采集 randset（访存密集型）的 perf record 调用栈
#   3. 生成对应的 SVG 火焰图到 flamegraphs/ 目录
#   4. 保存 .data 文件到 perf_data/ 目录，供后续深入分析
#
# 使用方法：
#   bash collect_flame.sh
#
# 输出：
#   flamegraphs/matrixprod_flame.svg
#   flamegraphs/randset_flame.svg
#   perf_data/matrixprod.data
#   perf_data/randset.data
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 创建目录
mkdir -p flamegraphs perf_data

# 检查 FlameGraph 工具是否存在
if [ ! -d "$SCRIPT_DIR/FlameGraph" ] || [ ! -f "$SCRIPT_DIR/FlameGraph/flamegraph.pl" ]; then
    echo "❌ 错误: FlameGraph 工具未找到"
    echo "请先执行: git clone https://github.com/brendangregg/FlameGraph.git"
    exit 1
fi

echo "============================================"
echo "  火焰图数据采集与生成"
echo "  工作目录: $SCRIPT_DIR"
echo "============================================"

# -------- 采集 matrixprod 调用栈 --------
echo ""
echo "[1/4] 采集 matrixprod 调用栈 (30s) ..."
perf record -F 99 -g -o perf_data/matrixprod.data -- \
    stress-ng --cpu 1 --cpu-method matrixprod -t 30s

# -------- 采集 randset 调用栈 --------
echo ""
echo "[2/4] 采集 randset 调用栈 (30s) ..."
perf record -F 99 -g -o perf_data/randset.data -- \
    stress-ng --vm 1 --vm-bytes 512M --vm-method rand-set -t 30s

# -------- 生成 matrixprod 火焰图 --------
echo ""
echo "[3/4] 生成 matrixprod 火焰图 ..."
perf script -i perf_data/matrixprod.data | \
    ./FlameGraph/stackcollapse-perf.pl | \
    ./FlameGraph/flamegraph.pl \
        --title "Matrix Multiplication CPU Flame" \
        --colors hot \
        > flamegraphs/matrixprod_flame.svg

# -------- 生成 randset 火焰图 --------
echo ""
echo "[4/4] 生成 randset 火焰图 ..."
perf script -i perf_data/randset.data | \
    ./FlameGraph/stackcollapse-perf.pl | \
    ./FlameGraph/flamegraph.pl \
        --title "Random Memory Access CPU Flame" \
        --colors hot \
        > flamegraphs/randset_flame.svg

echo ""
echo "============================================"
echo "  ✅ 火焰图生成完成"
echo ""
echo "  火焰图文件 (提交到 GitHub):"
ls -la flamegraphs/*.svg
echo ""
echo "  perf 原始数据 (已忽略，不提交):"
ls -la perf_data/*.data
echo "============================================"