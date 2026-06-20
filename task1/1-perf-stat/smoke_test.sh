#!/bin/bash
#
# smoke_test.sh — 运行 5 个微基准负载，每个 3 次，用 perf stat 采集性能计数器
# 使用方法: bash smoke_test.sh
# 输出: 15 个 .txt 文件在当前目录下
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/results_raw"
mkdir -p "$OUTPUT_DIR"

# ============================================================
# 5 个微基准负载定义（使用 C 语言内联编译，确保无外部依赖）
# ============================================================

WORKLOADS=(
    "int64"
    "matrixprod"
    "read64"
    "randset"
    "queens"
)

# 每个负载运行 3 次
RUNS=3

# perf stat 采集的事件列表
PERF_EVENTS="cycles,instructions,cache-references,cache-misses,L1-dcache-load-misses,LLC-load-misses,branch-instructions,branch-misses,dTLB-load-misses"

# ============================================================
# 编译各负载的 C 源码
# ============================================================

compile_int64() {
    cat > /tmp/int64_bench.c << 'EOF'
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>

#define ITER 500000000ULL

int main() {
    volatile int64_t a = 1, b = 2, c;
    for (uint64_t i = 0; i < ITER; i++) {
        c = a + b;
        c = a * b;
        c = a / (b ? b : 1);
        c = a % (b ? b : 1);
        a = (a + 1) & 0x7FFFFFFF;
        b = (b + 1) & 0x7FFFFFFF;
    }
    printf("int64 done, c=%ld\n", (long)c);
    return 0;
}
EOF
    gcc -O2 -o /tmp/int64_bench /tmp/int64_bench.c
}

compile_matrixprod() {
    cat > /tmp/matrixprod_bench.c << 'EOF'
#include <stdio.h>
#include <stdlib.h>

#define N 512

static double A[N][N], B[N][N], C[N][N];

int main() {
    for (int i = 0; i < N; i++)
        for (int j = 0; j < N; j++) {
            A[i][j] = (double)(i + j) / 1000.0;
            B[i][j] = (double)(i - j) / 1000.0;
            C[i][j] = 0.0;
        }
    for (int i = 0; i < N; i++)
        for (int k = 0; k < N; k++)
            for (int j = 0; j < N; j++)
                C[i][j] += A[i][k] * B[k][j];
    printf("matrixprod done, C[0][0]=%f\n", C[0][0]);
    return 0;
}
EOF
    gcc -O2 -o /tmp/matrixprod_bench /tmp/matrixprod_bench.c
}

compile_read64() {
    cat > /tmp/read64_bench.c << 'EOF'
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

#define SIZE (64ULL * 1024 * 1024)   /* 64M 个 int64 */

int main() {
    int64_t *arr = (int64_t *)malloc(SIZE * sizeof(int64_t));
    if (!arr) { perror("malloc"); return 1; }
    for (uint64_t i = 0; i < SIZE; i++) arr[i] = (int64_t)i;
    volatile int64_t sum = 0;
    for (uint64_t i = 0; i < SIZE; i++) {
        sum += arr[i];
    }
    printf("read64 done, sum=%ld\n", (long)sum);
    free(arr);
    return 0;
}
EOF
    gcc -O2 -o /tmp/read64_bench /tmp/read64_bench.c
}

compile_randset() {
    cat > /tmp/randset_bench.c << 'EOF'
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

#define SIZE (16ULL * 1024 * 1024)   /* 16M 个元素 */

int main() {
    int64_t *arr = (int64_t *)malloc(SIZE * sizeof(int64_t));
    if (!arr) { perror("malloc"); return 1; }
    srand(42);
    for (uint64_t i = 0; i < SIZE; i++) arr[i] = rand();
    volatile int64_t sum = 0;
    for (uint64_t i = 0; i < SIZE; i++) {
        int64_t idx = rand() % SIZE;
        sum += arr[idx];
    }
    printf("randset done, sum=%ld\n", (long)sum);
    free(arr);
    return 0;
}
EOF
    gcc -O2 -o /tmp/randset_bench /tmp/randset_bench.c
}

compile_queens() {
    cat > /tmp/queens_bench.c << 'EOF'
#include <stdio.h>
#include <stdlib.h>

#define N 14

static int count = 0;
static int col[N], diag1[2*N], diag2[2*N];

void search(int y) {
    if (y == N) { count++; return; }
    for (int x = 0; x < N; x++) {
        if (col[x] || diag1[x+y] || diag2[x-y+N-1]) continue;
        col[x] = diag1[x+y] = diag2[x-y+N-1] = 1;
        search(y+1);
        col[x] = diag1[x+y] = diag2[x-y+N-1] = 0;
    }
}

int main() {
    search(0);
    printf("queens(N=%d) solutions=%d\n", N, count);
    return 0;
}
EOF
    gcc -O2 -o /tmp/queens_bench /tmp/queens_bench.c
}

# ============================================================
# 编译所有负载
# ============================================================
echo "============================================"
echo "  编译微基准负载..."
echo "============================================"
compile_int64    && echo "  -> int64 编译完成"
compile_matrixprod && echo "  -> matrixprod 编译完成"
compile_read64   && echo "  -> read64 编译完成"
compile_randset  && echo "  -> randset 编译完成"
compile_queens   && echo "  -> queens 编译完成"
echo ""

# ============================================================
# 运行 perf stat 采集
# ============================================================
echo "============================================"
echo "  开始 perf stat 数据采集"
echo "  (5 个负载 × 3 次运行 = 15 个文件)"
echo "============================================"

for workload in "${WORKLOADS[@]}"; do
    for run in $(seq 1 $RUNS); do
        OUTFILE="$OUTPUT_DIR/${workload}_run${run}.txt"
        echo ""
        echo ">>> 运行: $workload 第 $run 次"
        perf stat -e "$PERF_EVENTS" /tmp/${workload}_bench 2>&1 | tee "$OUTFILE"
        echo "    输出: $OUTFILE"
    done
done

echo ""
echo "============================================"
echo "  数据采集完成"
echo "  输出目录: $OUTPUT_DIR"
echo "  文件列表:"
ls -la "$OUTPUT_DIR"/*.txt
echo "============================================"