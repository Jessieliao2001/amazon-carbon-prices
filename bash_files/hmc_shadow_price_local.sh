#!/bin/bash

set -e

xi=10000
sites=1043
action_name="shadow_price"

source .venv/bin/activate

# Optional: mimic the SLURM cpus-per-task=12 setting
export OMP_NUM_THREADS=12
export MKL_NUM_THREADS=12
export OPENBLAS_NUM_THREADS=12
export NUMEXPR_NUM_THREADS=12

for id in $(seq 60 70); do
    echo "========================================"
    echo "Running xi=${xi}, sites=${sites}, id=${id}"
    echo "Program starts $(date)"

    mkdir -p ./job-outs/${action_name}/xi_${xi}/id_${id}/sites_${sites}

    start_time=$(date +%s)

    python -u pysrc/bash/shadow_price.py \
        --id ${id} \
        --xi ${xi} \
        --sites ${sites} \
        > ./job-outs/${action_name}/xi_${xi}/id_${id}/sites_${sites}/run.out \
        2> ./job-outs/${action_name}/xi_${xi}/id_${id}/sites_${sites}/run.err

    end_time=$(date +%s)
    elapsed=$((end_time - start_time))

    echo "Program ends $(date)"
    echo "Elapsed time: $(date -ud "@$elapsed" +'%H hr %M min %S sec' 2>/dev/null || date -r "$elapsed" +'%H hr %M min %S sec')"
done