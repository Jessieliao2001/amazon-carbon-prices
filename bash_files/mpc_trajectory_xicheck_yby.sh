#!/bin/bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

xiarray=(1.0 0.5)

action_name="mpc_trajectory_xicheck_yby"

mkdir -p ./job-outs/${action_name}
mkdir -p ./bash/${action_name}

for xi in "${xiarray[@]}"; do

    if [ -f ./bash/${action_name}/xi_${xi}/run.sh ]; then
        rm ./bash/${action_name}/xi_${xi}/run.sh
    fi
    mkdir -p ./bash/${action_name}/xi_${xi}

    touch ./bash/${action_name}/xi_${xi}/run.sh

    tee -a ./bash/${action_name}/xi_${xi}/run.sh <<EOF
#!/bin/bash

#SBATCH --account=pi-lhansen
#SBATCH --job-name=${action_name}_xi_${xi}
#SBATCH --output=./job-outs/${action_name}/xi_${xi}.out
#SBATCH --error=./job-outs/${action_name}/xi_${xi}.err
#SBATCH --time=1-11:00:00
#SBATCH --partition=caslake
#SBATCH --nodes=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=4G

module load python/anaconda-2022.05 gurobi/11.0 gcc/12.2.0
source .venv/bin/activate

echo "\$SLURM_JOB_NAME"

echo "Program starts \$(date)"
start_time=\$(date +%s)

python3 -u scripts/mpc_trajectory_xi_yby.py --xi ${xi}

echo "Program ends \$(date)"
end_time=\$(date +%s)
elapsed=\$((end_time - start_time))
eval "echo Elapsed time: \$(date -ud "@\$elapsed" +'\$((%s/3600/24)) days %H hr %M min %S sec')"

EOF
    sbatch ./bash/${action_name}/xi_${xi}/run.sh
done
