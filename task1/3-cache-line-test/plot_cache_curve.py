"""
plot_cache_curve.py

读取 results/cache_line_results.csv，绘制“步长 vs 数组遍历性能”曲线图。
输出 cache_line_curve.png（DPI 300，透明背景）。
"""

import os
import sys
import csv
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

# ============================================================
# 跨平台字体设置
# ============================================================
_font_candidates = ["DejaVu Sans", "Arial"]
for _font in _font_candidates:
    try:
        matplotlib.font_manager.findfont(_font, fallback_to_default=False)
        plt.rcParams["font.family"] = _font
        break
    except Exception:
        continue

# ============================================================
# 路径配置（相对于脚本所在目录）
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(SCRIPT_DIR, "results", "cache_line_results.csv")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "cache_line_curve.png")

# ============================================================
# 读取 CSV 数据
# ============================================================
if not os.path.isfile(CSV_PATH):
    print(f"Error: CSV file not found at '{CSV_PATH}'", file=sys.stderr)
    sys.exit(1)

strides = []
avg_times = []
min_times = []
max_times = []

with open(CSV_PATH, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        strides.append(int(row["stride"]))
        avg_times.append(float(row["avg_time_ns"]))
        min_times.append(float(row["min_time_ns"]))
        max_times.append(float(row["max_time_ns"]))

strides = np.array(strides)
avg_times = np.array(avg_times)
min_times = np.array(min_times)
max_times = np.array(max_times)

# 误差棒：上误差 = max - avg，下误差 = avg - min
yerr_lower = avg_times - min_times
yerr_upper = max_times - avg_times

# ============================================================
# 绘图
# ============================================================
fig, ax = plt.subplots(figsize=(10, 6))

# 主折线 + 误差棒
ax.errorbar(
    strides,
    avg_times,
    yerr=[yerr_lower, yerr_upper],
    fmt="o-",
    color="steelblue",
    markersize=7,
    linewidth=1.8,
    capsize=4,
    label="Access Time",
    zorder=3,
)

# 数据点上方标注数值
for x, y in zip(strides, avg_times):
    if y >= 1e6:
        label = f"{y / 1e6:.1f}ms"
    else:
        label = f"{y / 1e3:.1f}μs"
    ax.annotate(
        label,
        (x, y),
        textcoords="offset points",
        xytext=(0, 10),
        fontsize=8,
        ha="center",
        color="steelblue",
    )

# Cache Line 边界红线（X=64）
ax.axvline(x=64, linestyle="--", color="red", linewidth=1.5, label="Cache Line Boundary", zorder=2)
ax.annotate(
    "Cache Line Boundary (64B)",
    xy=(64, avg_times[strides == 64][0]),
    xytext=(64 * 1.6, avg_times[strides == 64][0] * 1.8),
    arrowprops=dict(arrowstyle="->", color="red", lw=1.5),
    fontsize=10,
    color="red",
    ha="center",
    bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="red", alpha=0.8),
)

# 拐点标注（绿色星标）
turn_x = 64
turn_y = 3700844
ax.scatter([turn_x], [turn_y], marker="*", color="green", s=200, zorder=5)
ax.annotate(
    "Performance turning point",
    xy=(turn_x, turn_y),
    xytext=(turn_x * 0.35, turn_y * 0.6),
    arrowprops=dict(arrowstyle="->", color="green", lw=1.5),
    fontsize=10,
    color="green",
    ha="center",
    bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="green", alpha=0.8),
)

# 坐标轴设置
ax.set_xscale("log")
ax.set_xlabel("Stride (bytes)", fontsize=12)
ax.set_ylabel("Average Access Time (ns)", fontsize=12)
ax.set_title("Stride vs Array Traversal Performance", fontsize=14, fontweight="bold")

# X 轴刻度：固定为 1,2,4,8,16,32,64,128,256
ax.set_xticks(strides)
ax.set_xticklabels([str(int(s)) for s in strides])
ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
ax.get_xaxis().set_minor_formatter(matplotlib.ticker.NullFormatter())

# 网格
ax.grid(True, which="both", linestyle="--", alpha=0.7)

# 图例
ax.legend(loc="upper right", fontsize=10)

# 调整布局
plt.tight_layout()

# 保存
fig.savefig(OUTPUT_PATH, dpi=300, transparent=True)
print(f"Plot saved to: {OUTPUT_PATH}")