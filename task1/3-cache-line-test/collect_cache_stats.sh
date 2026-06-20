#!/bin/bash

# Collect perf stat data for each stride using /tmp to avoid NFS issues



mkdir -p results



for s in 1 2 4 8 16 32 64 128 256; do

    echo "Collecting stride=$s ..."

    perf stat -e L1-dcache-load-misses,LLC-load-misses ./src/cache_line_test $s &> /tmp/perf_${s}.txt

    mv /tmp/perf_${s}.txt results/stride_${s}.txt

    echo "Finished stride=$s"

    sync

    sleep 1

done



echo "All strides collected successfully."

ls -la results/
