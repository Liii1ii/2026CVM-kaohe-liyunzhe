#!/usr/bin/env python3
"""
analyze_perf.py — 微架构差异分析报告生成器

功能：
  从 process_perf.py 输出的衍生指标数据出发，自动执行环境检测、数据有效性声明、
  异常发现、三维度归因分析，最终生成企业级 Markdown + 纯文本双格式报告。

数据来源：
  脚本中硬编码的 DATA 字典来自 process_perf.py 的输出结果。
  如需更新数据，直接修改 DATA 字典中的数值即可。

环境检测：
  依赖 capture_env.sh 在 ./environment/ 目录下生成的系统信息文件。

使用方法：
  python analyze_perf.py

输出：
  - analysis_report.md  （Markdown 格式，可直接阅读）
  - analysis_report.txt （纯文本格式，便于复制到 Word）
  - 终端打印报告摘要（前 3 章 + 异常列表）
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Windows 终端编码兼容：确保 emoji 等 Unicode 字符正常输出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ============================================================
# 一、数据定义（来源：process_perf.py 输出的衍生指标）
# ============================================================
# 修改方法：直接替换下方的数值，格式为:
#   "workload_name": {"IPC": 值, "L1_Miss": 值, "LLC_Miss": 值, "Branch_Miss": 值, "TLB_Miss": 值}
# 其中 N/A 表示该指标不可用（用字符串 "N/A" 表示）

DATA = {
    "int64": {
        "IPC": 0.8000,
        "L1_Miss": 0.0100,      # 1.0%
        "LLC_Miss": "N/A",
        "Branch_Miss": 0.0100,  # 1.0%
        "TLB_Miss": 0.002,      # 0.2%
    },
    "matrixprod": {
        "IPC": 0.4000,
        "L1_Miss": 0.0250,      # 2.5%
        "LLC_Miss": 0.0050,     # 0.5%
        "Branch_Miss": 0.0050,  # 0.5%
        "TLB_Miss": 0.001,      # 0.1%
    },
    "read64": {
        "IPC": 0.3750,
        "L1_Miss": 0.0100,      # 1.0%
        "LLC_Miss": 0.0020,     # 0.2%
        "Branch_Miss": 0.0040,  # 0.4%
        "TLB_Miss": 0.000,      # <0.1%
    },
    "randset": {
        "IPC": 0.3333,
        "L1_Miss": 0.0500,      # 5.0%
        "LLC_Miss": 0.0100,     # 1.0%
        "Branch_Miss": 0.0500,  # 5.0%
        "TLB_Miss": 0.001,      # 0.1%
    },
    "queens": {
        "IPC": 1.2000,
        "L1_Miss": 0.0099,      # ~1.0%
        "LLC_Miss": 0.0010,     # 0.1%
        "Branch_Miss": 0.0500,  # 5.0%
        "TLB_Miss": 0.002,      # 0.2%
    },
}

# 负载顺序（保持输出一致性）
WORKLOAD_ORDER = ["int64", "matrixprod", "read64", "randset", "queens"]

# 指标显示名称
METRIC_NAMES = {
    "IPC": "IPC",
    "L1_Miss": "L1 DCache Miss Rate",
    "LLC_Miss": "LLC Miss Rate",
    "Branch_Miss": "Branch Miss Rate",
    "TLB_Miss": "TLB Miss Rate",
}

# 负载分类
WORKLOAD_CATEGORIES = {
    "计算密集型": ["int64", "matrixprod"],
    "访存密集型": ["read64", "randset"],
    "分支密集型": ["queens"],
}


# ============================================================
# 二、环境检测
# ============================================================

def get_script_dir():
    """获取脚本所在目录。"""
    return Path(__file__).resolve().parent


def check_freq_locked(env_dir):
    """
    检查 CPU 频率是否锁定。
    规则：如果 environment/freq_warning.txt 存在 → 频率未锁定
    """
    freq_file = env_dir / "freq_warning.txt"
    return not freq_file.exists()


def read_numa_info(env_dir):
    """
    读取 NUMA 信息。
    规则：如果包含 "not available" → NUMA 不可用
    """
    numa_file = env_dir / "numa_info.txt"
    if not numa_file.exists():
        return "文件不存在"
    content = numa_file.read_text(encoding="utf-8", errors="replace")
    return content


def check_cpu_flags(env_dir):
    """
    检查 CPU 指令集支持情况。
    规则：
      - avx2 不在 flags 中 → 不支持 AVX2
      - avx512 不在 flags 中 → 不支持 AVX-512
    返回: (has_avx2, has_avx512)
    """
    cpu_file = env_dir / "cpu_info.txt"
    if not cpu_file.exists():
        return False, False
    content = cpu_file.read_text(encoding="utf-8", errors="replace")
    has_avx2 = "avx2" in content
    has_avx512 = "avx512" in content
    return has_avx2, has_avx512


def read_virt_type(env_dir):
    """
    读取虚拟化类型。
    返回虚拟化类型字符串，如 "vmware", "kvm", "physical" 或 "unknown"。
    """
    virt_file = env_dir / "virt_type.txt"
    if not virt_file.exists():
        return "unknown"
    content = virt_file.read_text(encoding="utf-8", errors="replace").strip()
    # 跳过注释行和时间戳行
    for line in content.split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            return line.lower()
    return "unknown"


def read_cpu_count(env_dir):
    """
    从 cpu_info.txt 中读取可用核心数。
    规则：从 lscpu 输出中提取 "CPU(s):" 行。
    """
    cpu_file = env_dir / "cpu_info.txt"
    if not cpu_file.exists():
        return "N/A"
    content = cpu_file.read_text(encoding="utf-8", errors="replace")
    import re
    match = re.search(r"CPU\(s\):\s+(\d+)", content)
    if match:
        return match.group(1)
    return "N/A"


def detect_environment():
    """
    执行所有环境检测，返回环境检测结果字典。
    """
    script_dir = get_script_dir()
    env_dir = script_dir / "environment"

    env = {
        "freq_locked": check_freq_locked(env_dir),
        "numa_content": read_numa_info(env_dir),
        "has_avx2": False,
        "has_avx512": False,
        "virt_type": "unknown",
        "cpu_count": "N/A",
    }
    env["has_avx2"], env["has_avx512"] = check_cpu_flags(env_dir)
    env["virt_type"] = read_virt_type(env_dir)
    env["cpu_count"] = read_cpu_count(env_dir)

    return env


# ============================================================
# 三、辅助格式化函数
# ============================================================

def fmt_pct(value):
    """将数值格式化为百分比字符串。"""
    if value == "N/A":
        return "N/A"
    if isinstance(value, (int, float)):
        if value == 0.0:
            return "<0.1%"
        return f"{value * 100:.1f}%"
    return str(value)


def fmt_val(value):
    """格式化数值：N/A 或 4 位小数。"""
    if value == "N/A":
        return "N/A"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def is_na(value):
    """判断值是否为 N/A。"""
    return value == "N/A"


# ============================================================
# 四、数据有效性声明
# ============================================================

def check_data_validity():
    """
    逐项检查每个负载的每个指标，标注可靠性等级。
    返回: {
        workload: {
            metric: {"value": ..., "reliability": "可靠"|"谨慎"|"不可用", "reason": ...}
        }
    }
    """
    validity = {}

    for wl in WORKLOAD_ORDER:
        validity[wl] = {}
        for metric_key, metric_name in METRIC_NAMES.items():
            val = DATA[wl].get(metric_key, "N/A")
            entry = {"value": val, "reliability": "可靠", "reason": ""}

            if is_na(val):
                entry["reliability"] = "不可用"
                entry["reason"] = "该事件在虚拟化环境中不可用"
            else:
                # 根据指标类型判断可靠性
                if metric_key == "IPC":
                    if val < 0.3:
                        entry["reliability"] = "谨慎"
                        entry["reason"] = "IPC 极低，可能存在严重的流水线停顿或虚拟化开销"
                    elif val < 0.8:
                        # IPC 偏低但在合理范围内，仍然可靠
                        entry["reliability"] = "可靠"
                    elif val > 2.0:
                        entry["reliability"] = "谨慎"
                        entry["reason"] = "IPC 异常偏高，可能存在数据采集误差"
                elif metric_key == "L1_Miss":
                    if val > 0.10:
                        entry["reliability"] = "谨慎"
                        entry["reason"] = "L1 Miss 率 >10%，数据局部性异常差"
                elif metric_key == "Branch_Miss":
                    if val > 0.10:
                        entry["reliability"] = "谨慎"
                        entry["reason"] = "分支预测失败率 >10%，需确认测试环境"
                elif metric_key == "TLB_Miss":
                    if val > 0.05:
                        entry["reliability"] = "谨慎"
                        entry["reason"] = "TLB Miss 率 >5%，页表遍历开销异常高"

            validity[wl][metric_key] = entry

    return validity


def check_all_na_metrics():
    """
    检查是否有指标在所有负载中都为 N/A。
    返回: 所有负载中均为 N/A 的指标名列表。
    """
    all_na = []
    for metric_key in METRIC_NAMES:
        all_na_flag = True
        for wl in WORKLOAD_ORDER:
            if DATA[wl].get(metric_key, "N/A") != "N/A":
                all_na_flag = False
                break
        if all_na_flag:
            all_na.append(metric_key)
    return all_na


# ============================================================
# 五、关键异常发现
# ============================================================

# 严重程度定义
SEVERITY = {
    "P0": ("🔴 严重", "数据不可用或结果与理论严重背离"),
    "P1": ("🟡 警告", "数据存在异常但可解释"),
    "P2": ("🟢 提示", "数据正常，但存在值得关注的细节"),
}


def detect_anomalies():
    """
    自动检测所有异常，返回异常列表。
    每条异常: {"severity": "P0"|"P1"|"P2", "message": str, "trigger": str}
    """
    anomalies = []

    # ---- 1. IPC 异常检测 ----
    for wl in WORKLOAD_ORDER:
        ipc = DATA[wl].get("IPC", "N/A")
        if is_na(ipc):
            continue

        # IPC < 0.3 → P0
        if ipc < 0.3:
            anomalies.append({
                "severity": "P0",
                "message": f"[{wl}] IPC 极低（{ipc:.4f}），可能存在严重的流水线停顿或"
                           f"虚拟化开销，建议检查 CPU 配置。",
                "trigger": "IPC < 0.3",
            })
        # IPC 在 0.3~0.6 → P1
        elif ipc < 0.6:
            anomalies.append({
                "severity": "P1",
                "message": f"[{wl}] IPC 偏低（{ipc:.4f}），可能存在访存延迟或执行单元争用。",
                "trigger": "IPC 在 0.3~0.6 之间",
            })

        # IPC > 1.5 且 matrixprod → P2
        if ipc > 1.5 and wl == "matrixprod":
            anomalies.append({
                "severity": "P2",
                "message": f"[{wl}] IPC 较高（{ipc:.4f}），表明 SIMD 指令集有效利用。",
                "trigger": "IPC > 1.5 且负载为 matrixprod",
            })

        # int64 且 IPC < 0.5 → P1
        if wl == "int64" and ipc < 0.5:
            anomalies.append({
                "severity": "P1",
                "message": f"[{wl}] 整数运算 IPC 偏低（{ipc:.4f}），"
                           f"虚拟化环境可能存在指令模拟开销。",
                "trigger": "int64 负载 IPC < 0.5",
            })

    # ---- 2. Miss Rate 异常检测 ----
    for wl in WORKLOAD_ORDER:
        # L1 Miss > 10% → P0
        l1 = DATA[wl].get("L1_Miss", "N/A")
        if not is_na(l1):
            if l1 > 0.10:
                anomalies.append({
                    "severity": "P0",
                    "message": f"[{wl}] L1 DCache Miss 率 {fmt_pct(l1)}，数据局部性极差，"
                               f"性能可能严重受限于访存延迟。",
                    "trigger": "L1 Miss > 10%",
                })
            elif l1 > 0.05:
                anomalies.append({
                    "severity": "P1",
                    "message": f"[{wl}] L1 Miss 率 {fmt_pct(l1)} 偏高，存在一定的 Cache 压力。",
                    "trigger": "L1 Miss > 5% 且 < 10%",
                })

        # TLB Miss > 1% → P1
        tlb = DATA[wl].get("TLB_Miss", "N/A")
        if not is_na(tlb) and tlb > 0.01:
            anomalies.append({
                "severity": "P1",
                "message": f"[{wl}] TLB Miss 率 {fmt_pct(tlb)}，页表遍历开销显著，"
                           f"可能影响性能。",
                "trigger": "TLB Miss > 1%",
            })

    # ---- 3. 反常识检测 ----
    # queens 的 Branch Miss Rate < 3% → P1
    queens_bm = DATA["queens"].get("Branch_Miss", "N/A")
    if not is_na(queens_bm) and queens_bm < 0.03:
        anomalies.append({
            "severity": "P1",
            "message": f"queens 分支预测失败率异常低（{fmt_pct(queens_bm)}），"
                       f'与\u201c分支密集型\u201d标签不符，建议检查编译器优化（可能使用 CMOV）。',
            "trigger": "queens 分支密集型负载 Branch Miss < 3%",
        })

    # read64 的 L1 Miss 高于 randset → P0
    read64_l1 = DATA["read64"].get("L1_Miss", "N/A")
    randset_l1 = DATA["randset"].get("L1_Miss", "N/A")
    if not is_na(read64_l1) and not is_na(randset_l1) and read64_l1 > randset_l1:
        anomalies.append({
            "severity": "P0",
            "message": f"连续读模式（read64）的 L1 Miss（{fmt_pct(read64_l1)}）"
                       f"高于随机访问（randset）的 L1 Miss（{fmt_pct(randset_l1)}），"
                       f"违反直觉，建议检查测试数据。",
            "trigger": "read64 的 L1 Miss 高于 randset",
        })

    # matrixprod 的 IPC 低于 int64 → P1
    mp_ipc = DATA["matrixprod"].get("IPC", "N/A")
    i64_ipc = DATA["int64"].get("IPC", "N/A")
    if not is_na(mp_ipc) and not is_na(i64_ipc) and mp_ipc < i64_ipc:
        anomalies.append({
            "severity": "P1",
            "message": f"浮点矩阵乘法 IPC（{mp_ipc:.4f}）低于整数运算 IPC（{i64_ipc:.4f}），"
                       f"可能 SIMD 指令未生效。",
            "trigger": "matrixprod 的 IPC 低于 int64",
        })

    # ---- 4. N/A 检测 ----
    na_count = 0
    for wl in WORKLOAD_ORDER:
        for metric_key in METRIC_NAMES:
            if is_na(DATA[wl].get(metric_key, "N/A")):
                na_count += 1
    if na_count > 0:
        anomalies.append({
            "severity": "P2",
            "message": f"部分事件在虚拟化环境中不可用（共 {na_count} 处 N/A），已在报告中标记。",
            "trigger": "存在 N/A 数据",
        })

    return anomalies


# ============================================================
# 六、各负载三维度分析
# ============================================================

def analyze_frontend(wl, branch_miss):
    """
    前端取指/解码维度分析。
    数据依据：Branch Miss Rate
    """
    if is_na(branch_miss):
        return "Branch Miss Rate 数据不可用，无法评估前端取指效率。"

    if wl == "queens" and branch_miss < 0.03:
        # 特殊情况：queens 异常低值
        base = (
            f"分支预测失败率仅为 {fmt_pct(branch_miss)}，"
            f"分支模式简单或编译器优化有效（可能使用 CMOV），前端取指效率高。"
        )
        extra = (
            "但 queens 的异常低值表明编译器可能将分支优化为 CMOV，"
            "实际分支预测能力需通过 -O0 重新编译验证。"
        )
        return base + " " + extra

    if branch_miss < 0.02:
        return (
            f"分支预测失败率 {fmt_pct(branch_miss)}，"
            f"分支模式简单或编译器优化有效（可能使用 CMOV），前端取指效率高。"
        )
    elif branch_miss < 0.05:
        return (
            f"分支预测失败率 {fmt_pct(branch_miss)}，"
            f"存在一定量的条件分支，分支预测器工作正常，前端无明显瓶颈。"
        )
    else:
        return (
            f"分支预测失败率 {fmt_pct(branch_miss)}，"
            f"存在大量不可预测分支，流水线冲刷频繁，前端取指存在瓶颈。"
        )


def analyze_backend(wl, ipc):
    """
    后端执行单元维度分析。
    数据依据：IPC
    """
    if is_na(ipc):
        return "IPC 数据不可用，无法评估后端执行效率。"

    if wl == "matrixprod" and ipc < 0.5:
        base = (
            f"IPC 为 {ipc:.4f}，流水线效率偏低，推测为访存延迟（Load-to-Use）"
            f"或依赖冲突导致后端 Stall。"
        )
        extra = (
            "浮点矩阵乘法 IPC 偏低，虚拟化环境下 SIMD 指令集（AVX2/AVX-512）"
            "可能未被有效透传至虚拟机，建议在物理机复测验证。"
        )
        return base + " " + extra

    if ipc > 1.5:
        return f"IPC 为 {ipc:.4f}，超标量/SIMD 流水线利用充分，后端执行效率高。"
    elif ipc >= 0.8:
        return (
            f"IPC 为 {ipc:.4f}，流水线利用正常，存在轻度停顿，但未形成明显瓶颈。"
        )
    else:
        return (
            f"IPC 为 {ipc:.4f}，流水线效率偏低，推测为访存延迟（Load-to-Use）"
            f"或依赖冲突导致后端 Stall。"
        )


def analyze_memory(wl, l1_miss, llc_miss, tlb_miss):
    """
    访存子系统维度分析。
    数据依据：L1 Miss Rate、LLC Miss Rate、TLB Miss Rate
    """
    parts = []

    # L1 Miss 分析
    if not is_na(l1_miss):
        if l1_miss < 0.02:
            parts.append(
                f"L1 DCache Miss Rate 为 {fmt_pct(l1_miss)}，"
                f"数据局部性极好，工作集完全在 L1 缓存内。"
            )
        elif l1_miss < 0.05:
            parts.append(
                f"L1 DCache Miss Rate 为 {fmt_pct(l1_miss)}，"
                f"数据局部性良好，存在少量 L1 未命中，但影响有限。"
            )
        else:
            parts.append(
                f"L1 DCache Miss Rate 为 {fmt_pct(l1_miss)}，"
                f"数据局部性较差，频繁访问 L2/LLC，访存延迟可能成为主要瓶颈。"
            )

    # TLB Miss 分析
    if not is_na(tlb_miss):
        if tlb_miss > 0.01:
            parts.append(
                f"TLB Miss Rate 为 {fmt_pct(tlb_miss)}，"
                f"页表遍历开销显著，建议检查内存访问模式或使用大页（HugeTLB）。"
            )

    return " ".join(parts) if parts else "访存子系统数据不可用，无法评估。"


def analyze_continuous_vs_random():
    """
    连续读 vs 随机访问对比分析（read64 vs randset）。
    """
    read64_llc = DATA["read64"].get("LLC_Miss", "N/A")
    randset_llc = DATA["randset"].get("LLC_Miss", "N/A")

    if is_na(read64_llc) or is_na(randset_llc):
        return "LLC Miss 数据不可用，无法进行连续读与随机访问的对比分析。"

    if randset_llc == 0:
        return "randset 的 LLC Miss 为 0，无法进行对比。"

    ratio = read64_llc / randset_llc
    if ratio < 0.5:
        return (
            f"连续读模式（read64）的 LLC Miss Rate（{fmt_pct(read64_llc)}）"
            f"显著低于随机访问模式（randset，{fmt_pct(randset_llc)}），"
            f"表明硬件预取器有效工作，连续读模式下预取命中率高，符合预期。"
        )
    else:
        return (
            f"连续读模式（read64）的 LLC Miss Rate（{fmt_pct(read64_llc)}）"
            f"与随机访问模式（randset，{fmt_pct(randset_llc)}）接近，"
            f"硬件预取器可能未生效，或测试数据规模未超出 LLC 容量。"
        )


def generate_workload_analysis():
    """生成每个负载的详细分析。"""
    analyses = {}
    for wl in WORKLOAD_ORDER:
        d = DATA[wl]
        analyses[wl] = {
            "frontend": analyze_frontend(wl, d.get("Branch_Miss", "N/A")),
            "backend": analyze_backend(wl, d.get("IPC", "N/A")),
            "memory": analyze_memory(
                wl,
                d.get("L1_Miss", "N/A"),
                d.get("LLC_Miss", "N/A"),
                d.get("TLB_Miss", "N/A"),
            ),
        }
    return analyses


# ============================================================
# 七、报告生成
# ============================================================

def generate_report():
    """
    生成完整的分析报告。
    返回: (markdown_content, txt_content)
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    env = detect_environment()
    validity = check_data_validity()
    all_na_metrics = check_all_na_metrics()
    anomalies = detect_anomalies()
    workload_analyses = generate_workload_analysis()

    # ===== 构建 Markdown 报告 =====
    md = []

    # 标题
    md.append("# 微架构差异分析报告")
    md.append("")
    md.append("---")
    md.append("")

    # ================================================================
    # 第 1 章：报告元信息
    # ================================================================
    md.append("## 一、报告元信息")
    md.append("")
    md.append(f"- **生成时间**：{now}")
    md.append(f"- **数据来源**：`process_perf.py` 输出的衍生指标数据（硬编码于 `analyze_perf.py` 的 DATA 字典中）")
    md.append(f"- **脚本版本**：analyze_perf.py v1.0")
    md.append(f"- **分析负载**：{', '.join(WORKLOAD_ORDER)}")
    md.append("")

    # 环境摘要
    md.append("### 环境摘要")
    md.append("")
    md.append("| 项目 | 值 |")
    md.append("|:---|:---|")
    md.append(f"| 虚拟化类型 | {env['virt_type']} |")
    md.append(f"| 频率锁定状态 | {'✅ 已锁定' if env['freq_locked'] else '⚠️ 未锁定'} |")
    md.append(f"| AVX2 支持 | {'✅ 支持' if env['has_avx2'] else '❌ 不支持'} |")
    md.append(f"| AVX-512 支持 | {'✅ 支持' if env['has_avx512'] else '❌ 不支持'} |")
    md.append(f"| 可用核心数 | {env['cpu_count']} |")
    md.append("")

    # 原始数据展示
    md.append("### 原始衍生指标数据")
    md.append("")
    # 表头
    headers = ["负载", "IPC", "L1 DCache Miss Rate", "LLC Miss Rate",
               "Branch Miss Rate", "TLB Miss Rate"]
    md.append("| " + " | ".join(headers) + " |")
    md.append("|" + "|".join([":---:"] * len(headers)) + "|")
    for wl in WORKLOAD_ORDER:
        d = DATA[wl]
        row = [
            wl,
            fmt_val(d.get("IPC", "N/A")),
            fmt_pct(d.get("L1_Miss", "N/A")),
            fmt_pct(d.get("LLC_Miss", "N/A")),
            fmt_pct(d.get("Branch_Miss", "N/A")),
            fmt_pct(d.get("TLB_Miss", "N/A")),
        ]
        md.append("| " + " | ".join(row) + " |")
    md.append("")

    # ================================================================
    # 第 2 章：执行摘要
    # ================================================================
    md.append("## 二、执行摘要")
    md.append("")

    # 根据数据生成执行摘要
    summary_parts = []
    # 统计 IPC 最高和最低的负载
    valid_ipc = {wl: DATA[wl]["IPC"] for wl in WORKLOAD_ORDER
                 if not is_na(DATA[wl]["IPC"])}
    if valid_ipc:
        best_ipc_wl = max(valid_ipc, key=valid_ipc.get)
        worst_ipc_wl = min(valid_ipc, key=valid_ipc.get)
        summary_parts.append(
            f"本次测试覆盖 5 种典型负载，IPC 范围从 {valid_ipc[worst_ipc_wl]:.4f}（{worst_ipc_wl}）"
            f"到 {valid_ipc[best_ipc_wl]:.4f}（{best_ipc_wl}）。"
        )

    # 检查 LLC 是否全 N/A
    if "LLC_Miss" in all_na_metrics:
        summary_parts.append(
            "LLC-load-misses 事件在所有负载中均不可用，表明虚拟化环境屏蔽了 LLC 事件，"
            "报告中所有涉及 LLC Miss Rate 的分析均已跳过。"
        )

    # 异常数量
    p0_count = sum(1 for a in anomalies if a["severity"] == "P0")
    p1_count = sum(1 for a in anomalies if a["severity"] == "P1")
    if p0_count > 0:
        summary_parts.append(f"检测到 {p0_count} 项严重异常（P0），需重点关注。")
    if p1_count > 0:
        summary_parts.append(f"检测到 {p1_count} 项警告（P1），建议结合环境上下文解读。")

    # 整体评价
    summary_parts.append(
        f"整体来看，该 vCPU 在 {env['virt_type']} 虚拟化环境下运行，"
        f"{'频率已锁定，数据具有横向可比性' if env['freq_locked'] else '频率未锁定，IPC 数据可能存在波动'}。"
    )

    for i, part in enumerate(summary_parts, 1):
        md.append(f"{i}. {part}")
    md.append("")

    # ================================================================
    # 第 3 章：环境约束说明
    # ================================================================
    md.append("## 三、环境约束说明")
    md.append("")

    # 频率锁定状态
    if env["freq_locked"]:
        md.append("✅ **频率已锁定**：CPU 调速器已锁定为 performance 模式，IPC 数据具有横向可比性。")
    else:
        md.append("⚠️ **频率未锁定**：CPU 调速器未锁定为 performance 模式，IPC 数据可能存在 ±5%~8% 的波动，横向对比需谨慎解读。")
    md.append("")

    # NUMA 信息
    if "not available" in env["numa_content"].lower():
        md.append("- NUMA 拓扑信息不可用（虚拟化环境常见），不影响单核性能测试。")
        md.append("")

    # AVX2 / AVX-512
    if not env["has_avx2"]:
        md.append("⚠️ **CPU 不支持 AVX2 指令集**，matrixprod 负载无法利用 SIMD 加速。")
        md.append("")
    if not env["has_avx512"]:
        md.append("- CPU 不支持 AVX-512 指令集。")
        md.append("")

    # 虚拟化类型
    virt_display = env["virt_type"]
    if virt_display == "vmware":
        virt_display = "VMware"
    elif virt_display == "kvm":
        virt_display = "KVM"
    elif virt_display == "physical":
        virt_display = "物理机"
    md.append(f"- **虚拟化类型**：{virt_display}")
    md.append("")

    # 环境摘要表格
    md.append("### 环境配置摘要")
    md.append("")
    md.append("| 配置项 | 状态 |")
    md.append("|:---|:---|")
    md.append(f"| 虚拟化类型 | {virt_display} |")
    md.append(f"| 频率锁定 | {'✅ 已锁定' if env['freq_locked'] else '⚠️ 未锁定'} |")
    md.append(f"| AVX2 指令集 | {'✅ 支持' if env['has_avx2'] else '❌ 不支持'} |")
    md.append(f"| AVX-512 指令集 | {'✅ 支持' if env['has_avx512'] else '❌ 不支持'} |")
    md.append(f"| 可用 CPU 核心数 | {env['cpu_count']} |")
    md.append(f"| NUMA 信息 | {'可用' if 'not available' not in env['numa_content'].lower() else '不可用（虚拟化环境）'} |")
    md.append("")

    # ================================================================
    # 第 4 章：数据有效性声明
    # ================================================================
    md.append("## 四、数据有效性声明")
    md.append("")

    # 如果 LLC 全 N/A，加粗标注
    if "LLC_Miss" in all_na_metrics:
        md.append("> **⚠️ 重要：LLC-load-misses 在所有负载中均显示为 N/A，表明虚拟化环境屏蔽了 LLC 事件。报告中所有涉及 LLC Miss Rate 的分析均已跳过。**")
        md.append("")

    # 逐项标注
    md.append("### 逐指标可靠性评估")
    md.append("")
    rel_headers = ["负载", "指标", "数值", "可靠性", "说明"]
    md.append("| " + " | ".join(rel_headers) + " |")
    md.append("|" + "|".join([":---:"] * len(rel_headers)) + "|")

    for wl in WORKLOAD_ORDER:
        for metric_key, metric_name in METRIC_NAMES.items():
            entry = validity[wl][metric_key]
            val = entry["value"]
            rel = entry["reliability"]
            reason = entry["reason"] if entry["reason"] else "—"
            display_val = fmt_pct(val) if metric_key != "IPC" else fmt_val(val)
            md.append(f"| {wl} | {metric_name} | {display_val} | {rel} | {reason} |")
    md.append("")

    # queens 特殊处理
    queens_bm = DATA["queens"].get("Branch_Miss", "N/A")
    if not is_na(queens_bm) and queens_bm < 0.03:
        md.append(f"> **⚠️ 异常发现：queens 作为分支密集型负载，分支预测失败率仅为 {fmt_pct(queens_bm)}，显著低于预期。经分析，可能原因是编译器在 -O2 优化级别下将条件分支（如 if 语句）转换为了条件传送指令（CMOV），该指令不会触发分支预测器，因此分支预测失败率无法反映真实的算法分支特征。**")
        md.append("")

    # ================================================================
    # 第 5 章：关键异常发现
    # ================================================================
    md.append("## 五、关键异常发现")
    md.append("")

    md.append("### 严重程度定义")
    md.append("")
    md.append("| 等级 | 标识 | 含义 |")
    md.append("|:---:|:---:|:---|")
    md.append("| P0 | 🔴 严重 | 数据不可用或结果与理论严重背离，需要明确说明 |")
    md.append("| P1 | 🟡 警告 | 数据存在异常但可解释，需要在报告中重点说明 |")
    md.append("| P2 | 🟢 提示 | 数据正常，但存在值得关注的细节 |")
    md.append("")

    if not anomalies:
        md.append("✅ 未检测到异常，所有数据在正常范围内。")
    else:
        md.append("### 异常列表")
        md.append("")
        for a in anomalies:
            sev_label, sev_desc = SEVERITY.get(a["severity"], (a["severity"], ""))
            md.append(f"- **{sev_label}** [{a['severity']}] {a['message']}")
            md.append(f"  - 触发条件：`{a['trigger']}`")
        md.append("")

    # ================================================================
    # 第 6 章：各负载详细分析
    # ================================================================
    md.append("## 六、各负载详细分析")
    md.append("")

    for wl in WORKLOAD_ORDER:
        d = DATA[wl]
        analysis = workload_analyses[wl]

        md.append(f"### {wl}")
        md.append("")

        # 数值速览
        md.append("**数值速览**：")
        md.append("")
        md.append("| 指标 | 数值 |")
        md.append("|:---|:---:|")
        md.append(f"| IPC | {fmt_val(d.get('IPC', 'N/A'))} |")
        md.append(f"| L1 DCache Miss Rate | {fmt_pct(d.get('L1_Miss', 'N/A'))} |")
        md.append(f"| LLC Miss Rate | {fmt_pct(d.get('LLC_Miss', 'N/A'))} |")
        md.append(f"| Branch Miss Rate | {fmt_pct(d.get('Branch_Miss', 'N/A'))} |")
        md.append(f"| TLB Miss Rate | {fmt_pct(d.get('TLB_Miss', 'N/A'))} |")
        md.append("")

        # 三维归因
        md.append("**三维归因分析**：")
        md.append("")
        md.append(f"- **前端取指/解码**：{analysis['frontend']}")
        md.append(f"- **后端执行单元**：{analysis['backend']}")
        md.append(f"- **访存子系统**：{analysis['memory']}")
        md.append("")

        # 综合结论
        md.append(f"**综合结论**：")
        md.append("")
        # 基于负载类型和数据给出结论
        if wl in WORKLOAD_CATEGORIES["计算密集型"]:
            md.append(f"{wl} 属于计算密集型负载。")
        elif wl in WORKLOAD_CATEGORIES["访存密集型"]:
            md.append(f"{wl} 属于访存密集型负载。")
        elif wl in WORKLOAD_CATEGORIES["分支密集型"]:
            md.append(f"{wl} 属于分支密集型负载。")
        md.append("")

    # 连续读 vs 随机访问对比
    md.append("### 连续读 vs 随机访问对比")
    md.append("")
    md.append(analyze_continuous_vs_random())
    md.append("")

    # ================================================================
    # 第 7 章：综合结论与建议
    # ================================================================
    md.append("## 七、综合结论与建议")
    md.append("")

    # 分类汇总
    md.append("### 1. 分类汇总")
    md.append("")
    for category, wls in WORKLOAD_CATEGORIES.items():
        wl_str = "、".join(wls)
        md.append(f"- **{category}**：{wl_str}")
    md.append("")

    # 场景适用性评估
    md.append("### 2. 场景适用性评估")
    md.append("")

    # 根据数据判断
    best_ipc_wl = max(valid_ipc, key=valid_ipc.get)
    worst_ipc_wl = min(valid_ipc, key=valid_ipc.get)

    if valid_ipc[best_ipc_wl] >= 1.0:
        md.append(f"- 该 vCPU 在 **{best_ipc_wl}** 场景下 IPC 达到 {valid_ipc[best_ipc_wl]:.4f}，表现优异，"
                  f"适合整数计算密集型业务。")
    if valid_ipc[worst_ipc_wl] < 0.5:
        md.append(f"- 在 **{worst_ipc_wl}** 场景下 IPC 仅为 {valid_ipc[worst_ipc_wl]:.4f}，"
                  f"存在明显瓶颈，建议在物理机复测排除虚拟化干扰。")

    # 根据 randset 和 read64 判断访存场景
    randset_ipc = DATA["randset"].get("IPC", "N/A")
    if not is_na(randset_ipc) and randset_ipc < 0.5:
        md.append(f"- 该 vCPU 在随机访问场景下表现受限（randset IPC={randset_ipc:.4f}），"
                  f"不建议部署对内存延迟敏感的业务。")
    md.append("")

    # 后续建议
    md.append("### 3. 后续建议")
    md.append("")

    suggestion_num = 1
    if "LLC_Miss" in all_na_metrics:
        md.append(f"{suggestion_num}. 虚拟化环境屏蔽了 LLC 事件，建议在物理机复测获取完整数据，以便进行更准确的 Cache 层级分析。")
        suggestion_num += 1

    queens_bm = DATA["queens"].get("Branch_Miss", "N/A")
    if not is_na(queens_bm) and queens_bm < 0.03:
        md.append(f"{suggestion_num}. queens 分支预测失败率异常低（{fmt_pct(queens_bm)}），建议用 `-O0` 编译后重新测试，验证 CMOV 优化对分支预测指标的影响。")
        suggestion_num += 1

    mp_ipc = DATA["matrixprod"].get("IPC", "N/A")
    if not is_na(mp_ipc) and mp_ipc < 0.5:
        md.append(f"{suggestion_num}. matrixprod IPC 偏低（{mp_ipc:.4f}），建议检查虚拟机 CPU 配置是否透传了 AVX2 指令集，并确认 `/proc/cpuinfo` 中 flags 包含 `avx2`。")
        suggestion_num += 1

    if not env["freq_locked"]:
        md.append(f"{suggestion_num}. 建议在锁定 CPU 频率（performance 模式）后重新测试，排除 Turbo Boost 和频率缩放对 IPC 的干扰，获得更准确的横向对比数据。")
        suggestion_num += 1

    md.append("")

    # ================================================================
    # 附录：可视化建议
    # ================================================================
    md.append("## 附录：Excel 条件格式热力图建议")
    md.append("")
    md.append("在 Excel 中打开数据表格后，可使用以下条件格式规则快速生成热力图：")
    md.append("")
    md.append("### IPC 着色规则（越高越绿）")
    md.append("")
    md.append("| 条件 | 颜色 | 含义 |")
    md.append("|:---|:---|:---|")
    md.append("| IPC ≥ 1.5 | 🟢 绿色 | 流水线利用充分 |")
    md.append("| 0.8 ≤ IPC < 1.5 | 🟡 黄色 | 正常范围 |")
    md.append("| IPC < 0.8 | 🔴 红色 | 流水线效率偏低 |")
    md.append("")
    md.append("### Miss Rate 着色规则（越低越绿）")
    md.append("")
    md.append("| 条件 | 颜色 | 含义 |")
    md.append("|:---|:---|:---|")
    md.append("| Miss Rate < 2% | 🟢 绿色 | 缓存命中率高 |")
    md.append("| 2% ≤ Miss Rate < 5% | 🟡 黄色 | 正常范围 |")
    md.append("| Miss Rate ≥ 5% | 🔴 红色 | 缓存压力大，需关注 |")
    md.append("")
    md.append("### Excel 操作步骤")
    md.append("")
    md.append("1. 选中数据区域")
    md.append("2. 点击「开始」→「条件格式」→「新建规则」")
    md.append("3. 选择「使用公式确定要设置格式的单元格」")
    md.append("4. 输入对应公式（如 `=A1>=1.5`），设置填充色")
    md.append("5. 重复上述步骤完成所有阈值规则")
    md.append("")

    # 报告结尾
    md.append("---")
    md.append("")
    md.append(f"*报告由 `analyze_perf.py` 自动生成于 {now}*")
    md.append("")

    # ===== 构建纯文本报告 =====
    txt = build_txt_report(md)

    return "\n".join(md), txt


def build_txt_report(md_lines):
    """
    将 Markdown 报告转换为纯文本格式。
    移除 Markdown 标记，保留核心内容。
    """
    txt_lines = []
    for line in md_lines:
        # 跳过分隔线
        if line.strip() == "---":
            txt_lines.append("=" * 60)
            continue
        # 转换标题
        if line.startswith("## "):
            txt_lines.append("")
            txt_lines.append(line[3:].upper())
            txt_lines.append("-" * len(line[3:]))
            continue
        if line.startswith("### "):
            txt_lines.append("")
            txt_lines.append(line[4:])
            txt_lines.append("~" * len(line[4:]))
            continue
        if line.startswith("# "):
            txt_lines.append("")
            txt_lines.append(line[2:].upper())
            txt_lines.append("=" * len(line[2:]))
            continue
        # 转换表格分隔行
        if line.startswith("|:") or line.startswith("| :"):
            txt_lines.append("-" * 60)
            continue
        # 转换表格行 → 制表符分隔
        if line.startswith("|"):
            cells = [c.strip() for c in line.split("|")[1:-1]]
            txt_lines.append("\t".join(cells))
            continue
        # 转换引用
        if line.startswith("> "):
            txt_lines.append("  >>> " + line[2:])
            continue
        # 转换列表项
        if line.startswith("- **"):
            # 加粗列表项
            clean = line.replace("**", "")
            txt_lines.append("  * " + clean[2:])
            continue
        if line.startswith("- "):
            txt_lines.append("  * " + line[2:])
            continue
        if line.startswith("  - "):
            txt_lines.append("    + " + line[4:])
            continue
        # 编号列表
        if line and line[0].isdigit() and ". " in line[:5]:
            txt_lines.append(line)
            continue
        # 普通文本
        txt_lines.append(line)

    return "\n".join(txt_lines)


# ============================================================
# 八、终端摘要输出
# ============================================================

def print_terminal_summary(anomalies, all_na_metrics):
    """在终端打印报告摘要（前 3 章 + 异常列表）。"""
    env = detect_environment()

    print("=" * 70)
    print("  微架构差异分析报告 — 终端摘要")
    print("=" * 70)
    print()

    # 第 1 章摘要
    print("【一、报告元信息】")
    print(f"  生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  虚拟化类型：{env['virt_type']}")
    print(f"  频率锁定：{'✅ 已锁定' if env['freq_locked'] else '⚠️ 未锁定'}")
    print(f"  AVX2：{'✅ 支持' if env['has_avx2'] else '❌ 不支持'}")
    print(f"  AVX-512：{'✅ 支持' if env['has_avx512'] else '❌ 不支持'}")
    print(f"  可用核心数：{env['cpu_count']}")
    print()

    # 数据表格
    headers = ["负载", "IPC", "L1 Miss", "LLC Miss", "Br Miss", "TLB Miss"]
    print("  " + " | ".join(f"{h:^10}" for h in headers))
    print("  " + "-" * 68)
    for wl in WORKLOAD_ORDER:
        d = DATA[wl]
        row = [
            wl,
            fmt_val(d.get("IPC", "N/A")),
            fmt_pct(d.get("L1_Miss", "N/A")),
            fmt_pct(d.get("LLC_Miss", "N/A")),
            fmt_pct(d.get("Branch_Miss", "N/A")),
            fmt_pct(d.get("TLB_Miss", "N/A")),
        ]
        print("  " + " | ".join(f"{r:^10}" for r in row))
    print()

    # 第 2 章摘要
    print("【二、执行摘要】")
    if "LLC_Miss" in all_na_metrics:
        print("  ⚠️ LLC 事件在所有负载中均不可用（虚拟化环境屏蔽）。")
    p0_count = sum(1 for a in anomalies if a["severity"] == "P0")
    p1_count = sum(1 for a in anomalies if a["severity"] == "P1")
    print(f"  检测到 {p0_count} 项严重异常（P0），{p1_count} 项警告（P1）。")
    print()

    # 第 3 章摘要
    print("【三、环境约束说明】")
    if env["freq_locked"]:
        print("  ✅ 频率已锁定")
    else:
        print("  ⚠️ 频率未锁定，IPC 数据可能存在 ±5%~8% 波动")
    if not env["has_avx2"]:
        print("  ⚠️ CPU 不支持 AVX2")
    if not env["has_avx512"]:
        print("  - CPU 不支持 AVX-512")
    print(f"  虚拟化类型：{env['virt_type']}")
    print()

    # 异常列表
    print("【异常发现】")
    if not anomalies:
        print("  ✅ 未检测到异常。")
    else:
        for a in anomalies:
            sev_label, _ = SEVERITY.get(a["severity"], (a["severity"], ""))
            print(f"  {sev_label} [{a['severity']}] {a['message']}")
    print()

    print("=" * 70)
    print("  完整报告请查看 analysis_report.md 和 analysis_report.txt")
    print("=" * 70)


# ============================================================
# 九、主入口
# ============================================================

def main():
    """主函数：生成报告并输出到文件。"""
    script_dir = get_script_dir()

    # 生成报告
    print("正在生成微架构差异分析报告...")
    md_content, txt_content = generate_report()

    # 写入 Markdown 文件
    md_path = script_dir / "analysis_report.md"
    md_path.write_text(md_content, encoding="utf-8")
    print(f"✅ Markdown 报告已生成：{md_path}")

    # 写入纯文本文件
    txt_path = script_dir / "analysis_report.txt"
    txt_path.write_text(txt_content, encoding="utf-8")
    print(f"✅ 纯文本报告已生成：{txt_path}")

    print()

    # 终端打印摘要
    all_na_metrics = check_all_na_metrics()
    anomalies = detect_anomalies()
    print_terminal_summary(anomalies, all_na_metrics)


if __name__ == "__main__":
    main()