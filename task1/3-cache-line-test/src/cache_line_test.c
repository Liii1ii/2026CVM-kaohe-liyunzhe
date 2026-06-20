/*
 * cache_line_test.c
 *
 * Author : Li Yunzhe
 * Date   : 2026-06-21
 *
 * 测试不同步长遍历大数组时的缓存行性能差异。
 * 通过动态调整循环次数，使各步长的总访问数据量一致，
 * 从而横向对比不同步长下的访存延迟。
 *
 * 用法:
 *   ./cache_line_test              测试所有步长，生成 results.csv
 *   ./cache_line_test <stride>     只测试指定步长
 *   ./cache_line_test --verbose    详细模式，输出每次测试的原始数据
 *   ./cache_line_test --help       显示帮助
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define ARRAY_SIZE    (32 * 1024 * 1024)  /* 32 MB = 33554432 bytes */
#define BASE_ITER     100000000           /* 基准迭代次数，按 stride 缩放 */
#define REPEATS       3                   /* 每个步长的计时次数 */
#define NUM_STRIDES   9

static volatile unsigned char *g_array;

/* 根据步长动态计算迭代次数：总访问数据量 ≈ BASE_ITER 字节 */
static long calc_iterations(int stride)
{
    long iters = BASE_ITER / stride;
    return iters < 100000 ? 100000 : iters;  /* 下限保护 */
}

/* 打印使用说明 */
static void print_usage(const char *prog)
{
    printf("Usage:\n");
    printf("  %s              Test all strides, generate results.csv\n", prog);
    printf("  %s <stride>     Test only the specified stride\n", prog);
    printf("  %s --verbose    Verbose mode, output raw data for each run\n", prog);
    printf("  %s --help       Show this help message\n", prog);
}

/* 对指定步长执行一次计时遍历，返回耗时（纳秒） */
static long run_once(int stride, long iterations)
{
    struct timespec start, end;

    clock_gettime(CLOCK_MONOTONIC, &start);

    volatile unsigned char sum = 0;
    size_t index = 0;
    for (long k = 0; k < iterations; k++) {
        sum += g_array[index];
        index = (index + (size_t)stride) % ARRAY_SIZE;
    }
    (void)sum;

    clock_gettime(CLOCK_MONOTONIC, &end);

    return (end.tv_sec - start.tv_sec) * 1000000000L
         + (end.tv_nsec - start.tv_nsec);
}

/* 对指定步长执行预热 + REPEATS 次计时，将结果填入 results 数组 */
static void test_stride(int stride, long iterations, long results[REPEATS])
{
    /* 预热：与正式循环相同，不计时 */
    {
        volatile unsigned char sum = 0;
        size_t index = 0;
        for (long k = 0; k < iterations; k++) {
            sum += g_array[index];
            index = (index + (size_t)stride) % ARRAY_SIZE;
        }
        (void)sum;
    }

    /* 正式计时 */
    for (int r = 0; r < REPEATS; r++) {
        results[r] = run_once(stride, iterations);
    }
}

/* 从 REPEATS 次结果中计算 avg / min / max */
static void compute_stats(const long results[REPEATS], long *avg, long *min_val, long *max_val)
{
    *min_val = results[0];
    *max_val = results[0];
    long sum = 0;
    for (int r = 0; r < REPEATS; r++) {
        if (results[r] < *min_val) *min_val = results[r];
        if (results[r] > *max_val) *max_val = results[r];
        sum += results[r];
    }
    *avg = sum / REPEATS;
}

int main(int argc, char *argv[])
{
    int verbose = 0;
    int single_stride = -1;

    /* 解析命令行参数 */
    for (int a = 1; a < argc; a++) {
        if (strcmp(argv[a], "--help") == 0) {
            print_usage(argv[0]);
            return 0;
        } else if (strcmp(argv[a], "--verbose") == 0) {
            verbose = 1;
        } else {
            single_stride = atoi(argv[a]);
            if (single_stride <= 0) {
                fprintf(stderr, "Invalid stride: %s\n", argv[a]);
                print_usage(argv[0]);
                return 1;
            }
        }
    }

    /* 分配 64 字节对齐的 32MB 内存 */
    void *ptr = NULL;
    if (posix_memalign(&ptr, 64, ARRAY_SIZE) != 0) {
        fprintf(stderr, "posix_memalign failed\n");
        return 1;
    }
    g_array = (volatile unsigned char *)ptr;

    /* 用固定种子初始化数组，保证可复现 */
    srandom(42);
    for (size_t i = 0; i < ARRAY_SIZE; i++) {
        ((unsigned char *)ptr)[i] = (unsigned char)(random() & 0xFF);
    }

    int all_strides[] = {1, 2, 4, 8, 16, 32, 64, 128, 256};

    /* ===== 单步长模式 ===== */
    if (single_stride > 0) {
        long iterations = calc_iterations(single_stride);
        long results[REPEATS];

        printf("正在测试 stride=%d (iterations=%ld) ...\n", single_stride, iterations);
        test_stride(single_stride, iterations, results);

        long avg_ns, min_ns, max_ns;
        compute_stats(results, &avg_ns, &min_ns, &max_ns);

        if (verbose) {
            for (int r = 0; r < REPEATS; r++) {
                printf("  run %d: %ld ns\n", r + 1, results[r]);
            }
        }

        printf("stride=%d, avg=%ld ns, min=%ld ns, max=%ld ns, iterations=%ld\n",
               single_stride, avg_ns, min_ns, max_ns, iterations);

        free(ptr);
        return 0;
    }

    /* ===== 全步长模式 ===== */
    long avg_ns[NUM_STRIDES], min_ns[NUM_STRIDES], max_ns[NUM_STRIDES];
    long iterations_arr[NUM_STRIDES];

    for (int i = 0; i < NUM_STRIDES; i++) {
        int stride = all_strides[i];
        long iterations = calc_iterations(stride);
        iterations_arr[i] = iterations;
        long results[REPEATS];

        printf("正在测试 stride=%d (iterations=%ld) ...\n", stride, iterations);
        test_stride(stride, iterations, results);
        compute_stats(results, &avg_ns[i], &min_ns[i], &max_ns[i]);

        if (verbose) {
            for (int r = 0; r < REPEATS; r++) {
                printf("  run %d: %ld ns\n", r + 1, results[r]);
            }
        }

        printf("stride=%d, avg=%ld ns, min=%ld ns, max=%ld ns, iterations=%ld\n",
               stride, avg_ns[i], min_ns[i], max_ns[i], iterations);
    }

    /* 写入 CSV */
    FILE *fp = fopen("results.csv", "w");
    if (!fp) {
        fprintf(stderr, "Failed to open results.csv for writing\n");
        free(ptr);
        return 1;
    }

    fprintf(fp, "stride,avg_time_ns,min_time_ns,max_time_ns,iterations\n");
    for (int i = 0; i < NUM_STRIDES; i++) {
        fprintf(fp, "%d,%ld,%ld,%ld,%ld\n",
                all_strides[i], avg_ns[i], min_ns[i], max_ns[i], iterations_arr[i]);
    }

    fclose(fp);
    printf("Results written to results.csv\n");

    free(ptr);
    return 0;
}
