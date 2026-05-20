#!/bin/bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
BACKEND="${1:-}"
STAGE="${2:-}"
ACTION_NAME="mpc"
OFFSETS=(0 10 15 20 25)

usage() {
    echo "Usage: bash bash_files/mpc_hmc.sh <local|slurm> <all|pre|formal|figure14|day0>"
    echo
    echo "  local   Run jobs sequentially on this machine and write logs to job-outs/mpc/..."
    echo "  slurm   Generate one run.sh per job and submit with sbatch."
    echo
    echo "Stages:"
    echo "  pre       Transition-probability jobs: trig=0, ids 997-998."
    echo "  figure14  Formal MPC path jobs: trig=0, ids 1-50."
    echo "  day0      Day-0 present-value decomposition jobs: trig=2, id 1."
    echo "  formal    figure14 + day0."
    echo "  all       pre + formal."
}

price_model_for_type() {
    local type="$1"
    if [ "$type" = "constrained" ]; then
        echo "common_variance"
    else
        echo "distinct_variance"
    fi
}

base_pe_for() {
    local type="$1"
    local xi="$2"
    local price_model
    price_model="$(price_model_for_type "$type")"
    "$PYTHON_BIN" - "$type" "$xi" "$price_model" <<'PY'
import sys

from pysrc.replication.parameters import CarbonPriceKey, carbon_price, normalize_xi

model, xi, price_model = sys.argv[1:4]
price = carbon_price(
    CarbonPriceKey(
        context="price_stochasticity",
        model=model,
        sites=78,
        xi=normalize_xi(xi),
        price_model=price_model,
    )
)
print(f"{price:g}")
PY
}

pe_values_for() {
    local base_pe="$1"
    shift
    "$PYTHON_BIN" - "$base_pe" "$@" <<'PY'
import sys

base = float(sys.argv[1])
offsets = [float(value) for value in sys.argv[2:]]
print(" ".join(f"{base + offset:g}" for offset in offsets))
PY
}

job_dir_for() {
    local xi="$1"
    local pe="$2"
    local id="$3"
    local trig="$4"
    local type="$5"
    echo "job-outs/${ACTION_NAME}/xi_${xi}/pe_${pe}/id_${id}/trig_${trig}/type_${type}"
}

script_dir_for() {
    local xi="$1"
    local pe="$2"
    local id="$3"
    local trig="$4"
    local type="$5"
    echo "bash/${ACTION_NAME}/xi_${xi}/pe_${pe}/id_${id}/trig_${trig}/type_${type}"
}

run_local_job() {
    local xi="$1"
    local pe="$2"
    local id="$3"
    local trig="$4"
    local type="$5"
    local out_dir
    out_dir="$(job_dir_for "$xi" "$pe" "$id" "$trig" "$type")"
    mkdir -p "$out_dir"

    echo "[local] xi=${xi} pe=${pe} id=${id} trig=${trig} type=${type}"
    {
        echo "Program starts $(date)"
        start_time=$(date +%s)
        "$PYTHON_BIN" -u pysrc/mpc/mpc_hmc.py --id "$id" --pe "$pe" --xi "$xi" --trig "$trig" --type "$type"
        echo "Program ends $(date)"
        end_time=$(date +%s)
        elapsed=$((end_time - start_time))
        days=$((elapsed / 86400))
        hours=$(((elapsed % 86400) / 3600))
        minutes=$(((elapsed % 3600) / 60))
        seconds=$((elapsed % 60))
        printf "Elapsed time: %d days %02d hr %02d min %02d sec\n" "$days" "$hours" "$minutes" "$seconds"
    } > "${out_dir}/run.out" 2> "${out_dir}/run.err"
}

submit_slurm_job() {
    local xi="$1"
    local pe="$2"
    local id="$3"
    local trig="$4"
    local type="$5"
    local out_dir
    local script_dir
    local run_script

    out_dir="$(job_dir_for "$xi" "$pe" "$id" "$trig" "$type")"
    script_dir="$(script_dir_for "$xi" "$pe" "$id" "$trig" "$type")"
    run_script="${script_dir}/run.sh"

    mkdir -p "$out_dir" "$script_dir"

    cat > "$run_script" <<EOF
#!/bin/bash
#SBATCH --account=pi-lhansen
#SBATCH --job-name=id_${id}_${ACTION_NAME}
#SBATCH --output=${out_dir}/run.out
#SBATCH --error=${out_dir}/run.err
#SBATCH --time=1-11:00:00
#SBATCH --partition=caslake
#SBATCH --nodes=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G

set -e
cd "$REPO_ROOT"

if command -v module >/dev/null 2>&1; then
    module load python/anaconda-2022.05 || true
    module load gurobi/11.0 || true
fi

if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi

echo "\$SLURM_JOB_NAME"
echo "Program starts \$(date)"
start_time=\$(date +%s)

$PYTHON_BIN -u pysrc/mpc/mpc_hmc.py --id ${id} --pe ${pe} --xi ${xi} --trig ${trig} --type ${type}

echo "Program ends \$(date)"
end_time=\$(date +%s)
elapsed=\$((end_time - start_time))
days=\$((elapsed / 86400))
hours=\$(((elapsed % 86400) / 3600))
minutes=\$(((elapsed % 3600) / 60))
seconds=\$((elapsed % 60))
printf "Elapsed time: %d days %02d hr %02d min %02d sec\n" "\$days" "\$hours" "\$minutes" "\$seconds"
EOF

    echo "[slurm] xi=${xi} pe=${pe} id=${id} trig=${trig} type=${type}"
    sbatch "$run_script"
}

run_one_job() {
    local xi="$1"
    local pe="$2"
    local id="$3"
    local trig="$4"
    local type="$5"
    if [ "$BACKEND" = "local" ]; then
        run_local_job "$xi" "$pe" "$id" "$trig" "$type"
    else
        submit_slurm_job "$xi" "$pe" "$id" "$trig" "$type"
    fi
}

run_spec() {
    local label="$1"
    local trig="$2"
    local id_start="$3"
    local id_end="$4"
    local type="$5"
    local xi="$6"
    local base_pe
    local pe_values

    base_pe="$(base_pe_for "$type" "$xi")"
    pe_values="$(pe_values_for "$base_pe" "${OFFSETS[@]}")"

    echo "== ${label}: trig=${trig}, ids=${id_start}-${id_end}, type=${type}, xi=${xi}, base_pe=${base_pe} =="
    for id in $(seq "$id_start" "$id_end"); do
        for pe in $pe_values; do
            run_one_job "$xi" "$pe" "$id" "$trig" "$type"
        done
    done
}

run_pre_stage() {
    run_spec "pre 1.1.1" 0 997 998 unconstrained 10000
    run_spec "pre 1.1.2" 0 997 998 unconstrained 1
    run_spec "pre 1.1.3" 0 997 998 unconstrained 0.5
    run_spec "pre 1.2.1" 0 997 998 constrained 10000
    run_spec "pre 1.2.2" 0 997 998 constrained 1
    run_spec "pre 1.2.3" 0 997 998 constrained 0.5
}

run_figure14_stage() {
    run_spec "formal 2.1.1" 0 1 50 unconstrained 10000
    run_spec "formal 2.1.2" 0 1 50 unconstrained 1
    run_spec "formal 2.1.3" 0 1 50 unconstrained 0.5
    run_spec "formal 2.2.1" 0 1 50 constrained 10000
    run_spec "formal 2.2.2" 0 1 50 constrained 1
    run_spec "formal 2.2.3" 0 1 50 constrained 0.5
}

run_day0_stage() {
    run_spec "formal 3.1.1" 2 1 1 unconstrained 10000
    run_spec "formal 3.1.2" 2 1 1 unconstrained 1
    run_spec "formal 3.1.3" 2 1 1 unconstrained 0.5
    run_spec "formal 3.2.1" 2 1 1 constrained 10000
    run_spec "formal 3.2.2" 2 1 1 constrained 1
    run_spec "formal 3.2.3" 2 1 1 constrained 0.5
}

if [ "$BACKEND" = "-h" ] || [ "$BACKEND" = "--help" ] || [ "$BACKEND" = "help" ]; then
    usage
    exit 0
fi

if [ -z "$BACKEND" ] || [ -z "$STAGE" ]; then
    usage
    exit 0
fi

if [ "$BACKEND" != "local" ] && [ "$BACKEND" != "slurm" ]; then
    usage
    exit 2
fi

if [ "$BACKEND" = "slurm" ] && ! command -v sbatch >/dev/null 2>&1; then
    echo "ERROR: sbatch was not found. Use local backend or run on a Slurm server."
    exit 1
fi

case "$STAGE" in
    pre)
        run_pre_stage
        ;;
    figure14)
        run_figure14_stage
        ;;
    day0)
        run_day0_stage
        ;;
    formal)
        run_figure14_stage
        run_day0_stage
        ;;
    all)
        run_pre_stage
        run_figure14_stage
        run_day0_stage
        ;;
    -h|--help|help)
        usage
        ;;
    *)
        usage
        exit 2
        ;;
esac
