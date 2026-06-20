#!/usr/bin/env python3
"""
process_perf.py — 从 15 个 perf stat 输出 .txt 中提取关键数据，
取中位数作为最终值，计算 5 个衍生指标，输出对比表格。

使用方法:
    python process_perf.py [perf_output_dir]

默认从 ./perf_output 目录读取 .txt 文件。
"""

import os
import re
import sys
import statistics
from pathlib import Path


# ============================================================
# 配置
# ============================================================

WORKLOADS = ["int64", "matrixprod", "read64", "randset", "queens"]
RUNS = [1, 2, 3]

# 需要提取的 perf 事件及其在 perf stat 输出中的匹配模式
EVENTS = [
    "cycles",
    "instructions",
    "cache-references",
    "cache-misses",
    "L1-dcache-load-misses",
    "LLC-load-misses",
    "branch-instructions",
    "branch-misses",
    "dTLB-load-misses",
]

# 衍生指标定义: (指标名, 分子, 分母)
DERIVED_METRICS = [
    ("IPC",                    "instructions",         "cycles"),
    ("L1 DCache Miss Rate",    "L1-dcache-load-misses", "cache-references"),
    ("LLC Miss Rate",          "LLC-load-misses",       "cache-references"),
    ("Branch Miss Rate",       "branch-misses",         "branch-instructions"),
    ("TLB Miss Rate",          "dTLB-load-misses",      "cache-references"),
]

# 不可用标记
NOT_COUNTED_PATTERNS = [
    r"<not counted>",
    r"<not supported>",
]


# ============================================================
# 解析单个 perf stat 输出文件
# ============================================================

def parse_perf_stat(filepath: str) -> dict:
    """
    解析 perf stat 输出文件，返回 {event_name: value_or_NA} 字典。
    value 为整数，如果事件不可用则返回 "N/A"。
    """
    result = {}
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    for event in EVENTS:
        value = extract_event_value(content, event)
        result[event] = value

    return result


def extract_event_value(content: str, event: str):
    """
    从 perf stat 输出文本中提取单个事件的值。
    perf stat 输出格式示例:
         1,234,567,890      cycles
         123,456,789        instructions  #    0.12  insn per cycle
         <not counted>      cache-misses
         <not supported>    L1-dcache-load-misses
    """
    # 先检查是否不可用
    for pattern in NOT_COUNTED_PATTERNS:
        if re.search(pattern + r".*" + re.escape(event), content, re.IGNORECASE):
            return "N/A"

    # 尝试匹配 "数字 + 事件名" 格式
    # perf stat 输出中数字可能包含逗号分隔符，如 1,234,567
    # 模式: 可选的空白 + 数字(可能含逗号) + 空白 + 事件名
    pattern = r"([\d,]+)\s+" + re.escape(event) + r"\b"
    matches = re.findall(pattern, content)

    if not matches:
        # 尝试匹配带路径的事件名（如 L1-dcache-load-misses 可能显示为 L1-dcache-load-misses:u）
        pattern2 = r"([\d,]+)\s+" + re.escape(event) + r"(?::[ku])?\b"
        matches = re.findall(pattern2, content)

    if matches:
        # 取最后一个匹配（通常是总计行）
        raw = matches[-1].replace(",", "")
        try:
            return int(raw)
        except ValueError:
            return "N/A"

    return "N/A"


# ============================================================
# 中位数计算
# ============================================================

def compute_median(values: list):
    """
    对三个值取中位数。如果存在 "N/A"，则跳过不可用值。
    如果全是 "N/A"，返回 "N/A"。
    """
    numeric = [v for v in values if v != "N/A"]
    if not numeric:
        return "N/A"
    return int(statistics.median(numeric))


# ============================================================
# 衍生指标计算
# ============================================================

def compute_derived(median_data: dict) -> dict:
    """根据中位数数据计算 5 个衍生指标。"""
    derived = {}
    for metric_name, numerator_key, denominator_key in DERIVED_METRICS:
        num = median_data.get(numerator_key, "N/A")
        den = median_data.get(denominator_key, "N/A")
        if num == "N/A" or den == "N/A" or den == 0:
            derived[metric_name] = "N/A"
        else:
            derived[metric_name] = num / den
    return derived


# ============================================================
# 格式化输出
# ============================================================

def format_value(value):
    """格式化数值：N/A 或 保留 4 位小数或科学计数法。"""
    if value == "N/A":
        return "N/A"
    if isinstance(value, float):
        if value == 0.0:
            return "0.0000"
        # 对于非常小的值用科学计数法
        if value < 0.0001:
            return f"{value:.4e}"
        return f"{value:.4f}"
    return str(value)


def print_table(derived_data: dict):
    """打印衍生指标对比表格。"""
    headers = ["负载类型", "IPC", "L1 DCache Miss Rate", "LLC Miss Rate",
               "Branch Miss Rate", "TLB Miss Rate"]
    col_widths = [12, 10, 20, 14, 17, 15]

    def print_sep():
        parts = ["-" * w for w in col_widths]
        print("|-" + "-|-".join(parts) + "-|")

    # 表头
    header_parts = [h.center(w) for h, w in zip(headers, col_widths)]
    print("| " + " | ".join(header_parts) + " |")
    print_sep()

    # 数据行
    for workload in WORKLOADS:
        data = derived_data.get(workload, {})
        row = [workload]
        for metric_name, _, _ in DERIVED_METRICS:
            row.append(format_value(data.get(metric_name, "N/A")))
        row_parts = [str(r).center(w) for r, w in zip(row, col_widths)]
        print("| " + " | ".join(row_parts) + " |")


def print_raw_medians(median_data: dict):
    """打印原始事件中位数表格（调试用）。"""
    print("\n--- 原始事件中位数 ---")
    header = ["负载"] + EVENTS
    print("\t".join(header))
    for workload in WORKLOADS:
        data = median_data.get(workload, {})
        row = [workload] + [str(data.get(e, "N/A")) for e in EVENTS]
        print("\t".join(row))


# ============================================================
# 主流程
# ============================================================

def main():
    # 确定输入目录
    if len(sys.argv) > 1:
        input_dir = sys.argv[1]
    else:
        script_dir = Path(__file__).parent
        input_dir = script_dir / "results_raw"

    input_dir = Path(input_dir)
    if not input_dir.is_dir():
        print(f"错误: 目录不存在: {input_dir}")
        print("请先运行 smoke_test.sh 或 collect.sh 生成 perf stat 输出文件。")
        sys.exit(1)

    # 1. 解析所有文件
    print("=" * 60)
    print("  第一步: 解析 15 个 perf stat 输出文件")
    print("=" * 60)

    # raw_data[workload][run] = {event: value}
    raw_data = {}
    for workload in WORKLOADS:
        raw_data[workload] = {}
        for run in RUNS:
            filename = f"{workload}_run{run}.txt"
            filepath = input_dir / filename
            if not filepath.exists():
                print(f"  [警告] 文件不存在: {filepath}")
                raw_data[workload][run] = {e: "N/A" for e in EVENTS}
                continue
            parsed = parse_perf_stat(str(filepath))
            raw_data[workload][run] = parsed
            # 简要输出
            status = []
            for e in EVENTS:
                v = parsed.get(e, "N/A")
                status.append(f"{e}={v}")
            print(f"  [{workload}_run{run}] 解析完成: {', '.join(status[:3])}...")

    # 2. 取中位数
    print("\n" + "=" * 60)
    print("  第二步: 对每个负载的 3 次运行取中位数")
    print("=" * 60)

    median_data = {}
    for workload in WORKLOADS:
        median_data[workload] = {}
        for event in EVENTS:
            values = [raw_data[workload][run].get(event, "N/A") for run in RUNS]
            median_val = compute_median(values)
            median_data[workload][event] = median_val
            if median_val == "N/A":
                print(f"  [{workload}] {event}: N/A (该事件在当前虚拟化环境中不可用)")

    # 3. 计算衍生指标
    print("\n" + "=" * 60)
    print("  第三步: 计算 5 个衍生指标")
    print("=" * 60)

    derived_data = {}
    for workload in WORKLOADS:
        derived_data[workload] = compute_derived(median_data[workload])

    # 4. 输出对比表格
    print("\n" + "=" * 60)
    print("  第四步: 衍生指标对比表格")
    print("=" * 60)
    print()
    print_table(derived_data)

    # 5. 输出备注
    print("\n--- 备注 ---")
    na_events = set()
    for workload in WORKLOADS:
        for event in EVENTS:
            if median_data[workload].get(event) == "N/A":
                na_events.add(event)
    if na_events:
        for e in sorted(na_events):
            print(f"  - {e}: 该事件在当前虚拟化环境中不可用")
    else:
        print("  所有事件均正常采集。")

    print()
    print("=" * 60)
    print("  处理完成。")
    print("=" * 60)


if __name__ == "__main__":
    main()