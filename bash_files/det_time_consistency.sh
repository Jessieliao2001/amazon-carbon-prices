bfarray=(3.75 5)
sites=1043

for bf in "${bfarray[@]}"; do

                            count=0
                                        
                            action_name="time_consistency"

                            dataname="${action_name}"

                            mkdir -p ./job-outs/${action_name}/bf_${bf}/

                            if [ -f ./bash/${action_name}/bf_${bf}/run.sh ]; then
                                rm ./bash/${action_name}/bf_${bf}/run.sh
                            fi

                            mkdir -p ./bash/${action_name}/bf_${bf}/

                            touch ./bash/${action_name}/bf_${bf}/run.sh

                            tee -a ./bash/${action_name}/bf_${bf}/run.sh <<EOF
#!/bin/bash

#SBATCH --account=pi-lhansen
#SBATCH --job-name=bf_${bf}_${action_name}
#SBATCH --output=./job-outs/$job_name/${action_name}/bf_${bf}/run.out
#SBATCH --error=./job-outs/$job_name/${action_name}/bf_${bf}/run.err
#SBATCH --time=1-11:00:00
#SBATCH --partition=caslake
#SBATCH --nodes=1
#SBATCH --cpus-per-task=12
#SBATCH --mem=32G

module load python/anaconda-2022.05  
module load gurobi/11.0
module load gcc/12.2.0
source .venv/bin/activate

echo "\$SLURM_JOB_NAME"

echo "Program starts \$(date)"
start_time=\$(date +%s)

python -u /project/lhansen/HMC_rep26_robust_mac/amazon-carbon-prices/pysrc/analysis/time_consistency.py --bf ${bf}
echo "Program ends \$(date)"
end_time=\$(date +%s)
elapsed=\$((end_time - start_time))

eval "echo Elapsed time: \$(date -ud "@\$elapsed" +'\$((%s/3600/24)) days %H hr %M min %S sec')"

EOF
    count=$((count + 1))
    sbatch ./bash/${action_name}/bf_${bf}/run.sh
done