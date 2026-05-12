#!/bin/bash

#SBATCH --account=pi-lhansen
#SBATCH --job-name=mpc_trajectory
#SBATCH --output=./job-outs/mpc_trajectory/run.out
#SBATCH --error=./job-outs/mpc_trajectory/run.err
#SBATCH --time=1-11:00:00
#SBATCH --partition=caslake
#SBATCH --nodes=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G

module load python/anaconda-2022.05 gurobi/11.0 gcc/12.2.0
source .venv/bin/activate

echo "$SLURM_JOB_NAME"

echo "Program starts $(date)"
start_time=$(date +%s)

python3 -u /project/lhansen/HMC_rep26_robust_mac/amazon-carbon-prices/scripts/mpc_trajectory.py

echo "Program ends $(date)"
end_time=$(date +%s)
elapsed=$((end_time - start_time))

# eval "echo Elapsed time: $(date -ud "@$elapsed" +'$((${BASH_REMATCH[0]}/3600/24)) days %H hr %M min %S sec')"
echo "Elapsed time: $((elapsed / 86400)) days $(date -ud "@$elapsed" +'%H hr %M min %S sec')"