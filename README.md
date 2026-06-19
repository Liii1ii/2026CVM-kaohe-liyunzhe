# 🏗️ CVM 竞品微架构性能测评 — 项目开发文档

## 📖 项目简介

本项目是 **2026 CVM 竞品微架构性能测评校企合作 Mini 项目** 的完整工程实现。项目旨在通过 Linux `perf` 工具链、火焰图分析与 AI 辅助编程，对 CPU 微架构性能指标进行深度采集与瓶颈定位，并构建容器化的持续 CPU Profiling 工具。

项目采用 **Monorepo（单体仓库）** 模式进行管理，严格对齐考核要求的目录结构，保证代码、数据、文档的高度可追溯性。

---

## 👥 任务模块与责任划分

本项目按考核题目拆分为三个核心研发模块。请按模块认领自己的阵地，严格遵循“先搭骨架、再填功能”的开发策略。

### 📊 模块一：微架构指标采集与分析模块 (Perf Stat Module)

- **核心使命**：系统的“体检中心”。对 CPU 执行 5 类典型负载（整数/浮点/连续访存/随机访存/分支密集型）的性能压测，输出微架构关键指标（IPC、Cache Miss Rate、分支预测失败率等）。
- **核心技术栈**：Linux `perf stat`、`stress-ng`、Bash 脚本、数据分析（Excel/ Python）。
- **专属代码阵地**：`task1/1-perf-stat/`
- **MVP 目标**：完成 5 类负载 × 3 次重复的自动化采集脚本，输出可对比的原始数据文件，生成包含衍生指标（IPC/Miss Rate）的对比表格与分析报告。

---

### 🔥 模块二：火焰图生成与热点分析模块 (FlameGraph Module)

- **核心使命**：系统的“CT 扫描仪”。通过调用栈采样，将 CPU 时间花在哪里的问题可视化为火焰图，精准定位热点函数。
- **核心技术栈**：`perf record`、`perf script`、Brendan Gregg 的 FlameGraph 工具链、Perl。
- **专属代码阵地**：`task1/2-flamegraph/`
- **MVP 目标**：对至少 2 种负载生成 SVG 火焰图，分析计算密集型与访存密集型负载的火焰图形态差异，识别内核态函数对性能的影响。

---

### 🧪 模块三：Cache Line 微基准测试模块 (Cache Benchmark Module)

- **核心使命**：系统的“微观探测仪”。通过 C 语言编写的微基准程序，验证 CPU Cache Line 大小对数组遍历性能的影响，定位 64 字节边界拐点。
- **核心技术栈**：C 语言（`posix_memalign`、`volatile`、`__builtin_prefetch`）、`gcc`、`perf stat` + `perf record`。
- **专属代码阵地**：`task1/3-cache-line-test/`
- **MVP 目标**：编写可编译运行的 C 程序，输出 stride=1~256 的性能曲线图，标注 Cache Line 拐点，并借助 AI 工具完成代码编写与问题排查。

---

### 🐳 模块四：持续 CPU Profiling 工具模块 (选做加分)

- **核心使命**：系统的“黑匣子”。提供 7×24 小时后台 CPU 采样能力，支持按时间回查并一键生成火焰图，解决“凌晨故障无法复盘”的痛点。
- **核心技术栈**：Golang / Python、Docker、`perf record --switch-output`、FlameGraph、Vue/React（前端可选）。
- **专属代码阵地**：`task2/`
- **MVP 目标**：完成容器化部署，实现按时间窗口轮转保存采样数据、历史数据自动清理、按时间段回查并生成火焰图的核心功能。

---

## 📂 项目目录树与开发导航

```text
2026CVM-kaohe-<你的名字拼音>/
│
├── README.md                        # 📄 仓库总说明：个人信息、题目完成情况概览
├── .gitignore                       # 🚫 Git 忽略规则（防大文件/临时文件）
├── resume/                          # 📄 个人简历
│   └── resume.pdf
│
├── task1/                           # ====== 必做题 ======
│   │
│   ├── 1-perf-stat/                 # 📊 [模块一] 多场景微架构指标采集
│   │   ├── README.md                # 运行说明：环境准备、perf stat 采集命令、如何复现
│   │   ├── results/                 # 存放 perf stat 原始输出（5个负载 × 3次重复 = 15个 .txt）
│   │   ├── environment/             # 存放环境快照信息（CPU/内核/NUMA/频率策略）
│   │   └── report.pdf               # 五场景对比表格 + 差异分析报告
│   │
│   ├── 2-flamegraph/                # 🔥 [模块二] 火焰图生成与热点分析
│   │   ├── README.md                # 运行说明：perf record + FlameGraph 生成步骤
│   │   ├── flamegraphs/             # 存放生成的 .svg 火焰图（≥2张 + 差异图）
│   │   └── report.pdf               # 火焰图对比分析报告
│   │
│   └── 3-cache-line-test/           # 🧪 [模块三] AI 辅助编写 Cache Line 微基准
│       ├── README.md                # 运行说明：编译命令、运行方式、perf 采集命令
│       ├── src/                     # C 语言源代码
│       │   └── cache_line_test.c
│       ├── results/                 # 各步长的 perf 输出 + 性能数据（CSV）
│       ├── flamegraphs/             # stride=1 vs stride=64 的火焰图
│       ├── report.pdf               # 曲线图 + 拐点分析 + AI 使用记录
│       └── ai-chat-log/             # AI 工具对话记录（截图或导出文件）
│
└── task2/                           # ====== 选做加分题 ======
    ├── README.md                    # 📄 项目简介、架构设计、快速启动、使用示例
    ├── src/                         # 💻 完整项目源代码
    │   ├── Dockerfile               # 容器化构建文件
    │   ├── .dockerignore
    │   ├── backend/                 # 后端服务（Golang/Python/Node.js）
    │   ├── frontend/                # 前端界面（Vue/React/纯HTML，可选）
    │   └── collector/               # 采集脚本（perf 轮转 + 数据管理）
    ├── profiler.tar                 # 🐳 Docker 镜像导出文件（docker save）
    ├── test/                        # 🧪 测试验证
    │   ├── test_scenario.sh         # 构造 CPU 飙升的测试脚本
    │   └── screenshots/             # 测试过程截图（回查操作 + 火焰图结果）
    └── ai-chat-log/                 # AI 编程完整对话记录
```

---

## ⚔️ Git 协作与提交流程

> **注**：本项目为单人开发，但依然遵循企业级 Git 规范，以培养良好的工程习惯。

1. **绝对禁止直接 `push` 到 `main` 分支。** `main` 分支必须保持随时可部署状态。
2. **分支命名规范**：
   - 功能开发：`feat/<模块名>-<功能描述>`（如 `feat/perf-stat-collector`）
   - Bug 修复：`fix/<模块名>-<问题描述>`（如 `fix/flamegraph-permission-denied`）
   - 文档更新：`docs/<模块名>-<内容描述>`（如 `docs/perf-stat-report`）
   - 数据更新：`data/<模块名>-<负载名>`（如 `data/perf-stat-int64-raw`）
3. **提交规范 (Conventional Commits)**：
   - `feat: 完成 1-perf-stat 自动化采集脚本`
   - `fix: 修复 matrixprod 负载在旧版 stress-ng 中不支持的问题`
   - `data: 添加五类负载的 perf stat 原始输出文件`
   - `docs: 完成火焰图对比分析报告初稿`
   - `chore: 更新 .gitignore，忽略 *.data 和 *.tar 文件`
4. **提交频率**：每完成一个子任务（如跑完 5 个负载、生成一张火焰图）即进行一次 commit，保证提交历史可追溯。

---

## 🚫 架构与工程红线（不可逾越）

### 1. 数据可复现性原则
- **环境固化**：每次采集前必须记录完整的测试环境信息（CPU 型号、内核版本、频率策略、NUMA 拓扑），并保存到 `environment/` 目录下。
- **频率锁定**：采集前必须执行 `cpupower frequency-set -g performance` 锁定 CPU 频率，或在报告中明确说明“虚拟化环境无法调节频率”并采取多次采样取中位数的补偿措施。
- **多次采样**：每个负载至少运行 3 次，取中位数作为最终结果，消除系统后台进程抖动。

### 2. 数据永久保存原则
- **本地持久化**：所有代码和最终成果（原始数据、火焰图、PDF 报告）必须保存在本地电脑（非虚拟机），虚拟机仅作为临时运行环境。
- **Git 版本控制**：所有文本文件（`.sh`、`.c`、`.txt`、`.md`、`.pdf`）必须提交到 Git 仓库，二进制大文件（`.data`、`.tar`）通过 `.gitignore` 忽略并通过 GitHub Release 单独分发。

### 3. 虚拟机隔离与防丢失原则
- **环境快照**：虚拟机环境配置完成后，必须拍摄快照（VMware/VirtualBox）或创建自定义镜像（云服务器），防止系统崩溃后重装。
- **数据即时回传**：每次在虚拟机跑完测试后，立即通过 `scp` / `rsync` 将 `results/` 和 `environment/` 目录同步回本地电脑。
- **WSL2 优先策略**：Windows 用户优先使用 WSL2（文件直接挂载在 `/mnt/` 下），天然解决数据丢失问题。

### 4. 工具链兼容性原则
- **版本降级处理**：若 `stress-ng` 不支持 `--cpu-method matrixprod`，使用 `stress-ng --cpu-method list` 查看可用方法，选择功能最接近的替代（如 `matrix` 或 `fft`），并在报告中明确说明。
- **WSL2 环境特殊处理**：若 `cpupower` 不可用（WSL2 不支持），放弃频率锁定，但需在报告中注明“WSL2 环境无法调节物理频率，采用 5 次采样取中位数消抖”。

### 5. 报告与代码的契约精神
- **数据与报告分离**：原始数据（`.txt`）只做“搬运”和“计算”，不做任何手工篡改。所有分析结论必须基于原始数据计算出的衍生指标。
- **截图可追溯**：PDF 报告中涉及的火焰图、`perf stat` 输出，必须来自 `flamegraphs/` 和 `results/` 目录下的文件，不得使用网图或非本机生成的数据。

---

## 🛠️ 环境准备快速指引

### 本地开发环境（Windows/Mac）
- **VSCode** + **Remote-SSH** 插件（远程连接虚拟机）或 **WSL2** 直接开发
- **Git** + **GitHub Desktop**（可选）

### 虚拟化运行环境（Linux x86_64）
- **推荐**：Ubuntu 22.04 LTS（WSL2 / VMware / VirtualBox / 云服务器）
- **必须安装的工具**：
  ```bash
  sudo apt update
  sudo apt install -y linux-tools-common linux-tools-$(uname -r) stress-ng git perl curl build-essential
  sudo sysctl -w kernel.perf_event_paranoid=-1
  ```
- **FlameGraph 工具链**：
  ```bash
  git clone https://github.com/brendangregg/FlameGraph.git ~/tools/FlameGraph
  ```

---

> **📌 开发阶段说明**：目前项目处于 **Phase 0（地基搭建阶段）**，已完成目录骨架、`.gitignore`、README 占位文件、环境快照脚本占位等基础结构。后续将按模块依次填充功能代码与数据。