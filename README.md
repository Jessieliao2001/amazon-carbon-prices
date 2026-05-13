# Project Amazon

## Requirements
- Python 3.9
- Gurobi 11.0
- gcc 12.2
## Data Requirements
To replicate, make sure to download the raw data into the directory structure below:
```
.
└── data
    └── raw
        ├── esa
        ├── fgv
        ├── global_forest_watch
        ├── ibge
        ├── ipea
        ├── mapbiomas
        ├── seabpr
        ├── seeg
        ├── worldbank
        └── worldclim
```

## Installation

0. Clone git repository
```bash
git clone <repo-url>
```
1. Create and activate a new virtual environment
```
module avail python gurobi gcc
module load python/anaconda-2022.05 gurobi/11.0 gcc/12.2.0
/software/python-anaconda-2022.05-el8-x86_64/bin/python3 -m venv .venv
source .venv/bin/activate
```
2. Install python dependencies
```
python -m pip install -e '.[all]'
```

3. Install CmdStan
```
install_cmdstan --overwrite
```

4. Install pre-commit hooks (required for contributors)
```
pre-commit install
```

## Replication

### Preparation
1. Create the data folder
```bash
mkdir data
```

2. Download the `raw` data folder

3. Move `raw` into `data` folder

4. Run `.Rprofile`
```R
R
source(".Rprofile")
```

5. Restore R packages if missing
```R
R
renv::restore()
```

6. Run masterfile
```R
R
source("rsrc/_masterfile_all.R")
```
### Run on Midway server
#### When you use `sbatch` to run the code, remember to create a corresponding new folder in the job-out folder. 
#### Deterministic Part
7. Run the baseline script to get Table 23,24,25:
```bash
python pysrc/sampling/baseline.py
python pysrc/sampling/baseline.py --sites 78
```

8. Run below to update the carbon prices for both 78 sites and 1043 sites (Table 1)
```bash
bash bash_files/hmc_shadow_price.sh
```

9. Run below to get Table 2, 3, 13 and Figure 5 & 6 (update with new `pee`)
```bash
python scripts/conduction_det.py
```
if not enough space, just run the bash file
```bash
sbatch bash_files/det_conduction.sh
```

#### HMC Part
10. Run below in server (update with new `pee`)
```bash
bash bash_files/hmc_sampling.sh
bash bash_files/hmc_relative_entropy.sh
```

11. Run below in server to get Table 4, 14, 15, 16, 17, and Figure 9,10,11,12,13,17,18 (update with new `pee`, change in `scripts/conduction_hmc.py`)
Remember to get the correct site id from the job-out of `relative_entropy` and then modify the site id in the Python code of density plot.
```bash
python scripts/conduction_hmc.py
```
if not enough space, just run the bash file
```bash
sbatch bash_files/hmc_conduction.sh
```

#### MPC Part
12. Run below with current script:
```bash
bash bash_files/mpc_prepare.sh
bash bash_files/mpc_hmc_sp.sh
```

13. Run below to update the carbon prices (Table 5)
```bash
python pysrc/mpc/mpc_compute_sp.py
```
if not enough space, just run the bash file
```bash
sbatch bash_files/mpc_compute_sp.sh
```
Then get shadow price of MPC and update the python file line 84-93

14. Run MPC HMC sampling:
```bash
bash bash_files/mpc_hmc.sh
```
- run `bash_files/mpc_hmc.sh` (pee, xi)*2 (unconstrained, constrained) first with `trig=0`
  - `id 1-50, 997&998`
- get distorted probability in job-out (`id=997,998`)
  - from year 1 done: find `year done: 1`
  - last 2 probs (prob_hh and 1-prob_ll)
- use `prob_hh` and `prob_ll` to update tables of representative distorted transition probability (Table 7, 9, 20 and 22) and `pysrc/mpc/mpc_simulating.py` line 187 to the end for 
  - xi=0.5, 1
  - b=0,10,15,20,25
  - unconstrained and constrained

15. Run the following with `id=1`, `trig=2` to compute day-0 solutions for Table 6, 8, 12, 18, 19 and 21
```python
python3 pysrc/mpc/mpc_hmc.py --id 1 --pe 6.1 --xi 0.5 --trig 2 --type "unconstrained"
python3 pysrc/mpc/mpc_compute_day0.py
```
or 
```bash
bash bash_files/mpc_hmc.sh
```
```bash
sbatch bash_files/mpc_compute_day0.sh
```

16. Compute results to get value decomposition under simulation (Table 18)
```bash
python pysrc/mpc/mpc_compute.py
```
if not enough space, just run the bash file
```bash
sbatch bash_files/mpc_compute.sh
```
update with mpc new `pee`

17. Plot MPC trajectories to get Figure 14
```bash
python scripts/mpc_trajectory.py
```
if not enough space, just run the bash file
```bash
sbatch bash_files/mpc_trajectory.sh
```
update with mpc new `pee`

18. Run below to get Table 10, 11 and Figure 15:
```bash
python scripts/price_estimation.py
```
```bash
bash bash_files/price_estimation.sh
```

19. Run below to get Figure 21:
```bash
python scripts/bayesian_R2.py
```
```bash
sbatch bash_files/bayesian_R2.sh
```

### R analysis
1. Run below to get Figure 2:
```R
R
source("rsrc/analysis/carbon_capture_curves/_masterfile.R")
```
2. Run below to get Figure 3 & 4:
```R
R
source("rsrc/analysis/calibration_maps_78_sites.R")
source("rsrc/analysis/calibration_maps_1043_sites.R")
```
3. Run below to get Figure 7 & 8:
```R
source("rsrc/analysis/map_1043_det.R")
```
4. Run below to get Figure 16:
Remember to get the correct site id from the job-out of `relative_entropy` and then modify the site id in the correct R code.
```R
source("rsrc/analysis/map_kl.R")
```
5. Run below to get Figure 19 & 20:
```R
R
source("rsrc/analysis/map_1043_hmc_xi05.R")
source("rsrc/analysis/map_1043_hmc_xi1.R")
```

## Contributing
0. Open a new git branch
```
git checkout -b <new branch name>
```
1. Create new code changes

2. Stage changed files
```
git add <names of changed files>
```

3. Commit changed files
```
git commit
```

4. After several commits, push commits to remote (if it is the first time pushing this branch use the `--set-upstream` flag)
```
git push
```

5. Submit a pull request on GitHub
