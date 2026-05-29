# Amazon Carbon Prices Replication Package

This repository contains the data-cleaning, estimation, optimization, and
post-processing code for the Amazon carbon-prices manuscript. The replication
workflow is organized around a single driver, `run.sh`, and the exhibit audit
files in `replication/`.

The package is structured to be usable both on a local machine and on a server
or cluster. Local runs execute commands directly. Server runs can submit the
same steps through Slurm.

## Repository Layout

- `data/raw/`: raw input data, supplied separately.
- `data/processed/`, `data/clean/` and `data/calibration/`: processed, cleaned and calibrated data generated from the raw inputs.
- `rsrc/`: R data-cleaning, calibration, and map/figure scripts.
- `pysrc/`: Python package code for sampling, optimization, MPC, and shared
  helpers.
- `pysrc/scripts/`: user-facing Python scripts that run analysis, estimation,
  figures, and workflow orchestration.
- `pysrc/replication/`: replication post-processing code that turns raw model
  outputs and logs into derived CSVs, manifests, paper numbers, and `aux_input`
  assets.
  The previous top-level `scripts` layout has been folded into `pysrc/` so
  Python code lives under one importable package tree.
- `replication/figure1/`: repo-internal World Bank inputs and documentation for
  reproducing Figure 1 through `pysrc/scripts/figure1.py`.
- `bash_files/`: legacy cluster helper scripts.
- `job-outs/`: selected original run logs used to derive reported carbon prices.
  Only the `run.out` files needed for the replication audit are intended to be
  version controlled.
- `output/` and `plots/`: generated tables, figures, and model outputs.
- `replication/`: derived replication metadata, exhibit manifest, and
  output-derived manuscript numbers.

## Requirements

- Python >= 3.9 and < 3.12.
- R with `renv` for local data processing and plot steps. Slurm server runs can
  skip R.
- Gurobi >= 10.0.3 for the optimization steps.
- CmdStan through `cmdstanpy` for the Stan sampling steps.
- Slurm is optional and only needed for `--backend slurm`.

On the Midway server, a typical module setup is:

```bash
module load python/anaconda-2022.05 gurobi/11.0 gcc/12.2.0
```

## Replication Workflow

Follow these steps in order. The commands work locally with `--backend local`
and on a Slurm server with `--backend slurm`.

### Step 1. Prepare The Environment

The setup can be run as one command from the repository root. Use `source` if
you want the environment to remain active in the current shell after setup
finishes.

```bash
git clone <repo-url>
cd amazon-carbon-prices
```

#### 1.1 Local Setup

Install Gurobi 11.0.x with a valid license, R, and a C/C++ compiler first.

Academic users can request a free academic license from the Gurobi Academic
License Program or Gurobi User Portal; after installing Gurobi, copy the
portal-provided `grbgetkey ...` command and run it on the local machine to
create `gurobi.lic`. Put `gurobi.lic` in a default Gurobi license directory, or
export `GRB_LICENSE_FILE=/full/path/to/gurobi.lic` before running this repo so
Gurobi and Pyomo can find the license.

On macOS, the compiler setup is usually:

```bash
xcode-select --install
brew install gcc@12
```

Then run:

```bash
source ./setup_env.sh local
```

The script creates `.venv`, installs the pinned Python dependencies from
`pyproject.toml`, installs `gurobipy==11.0.*`, installs CmdStan through
`cmdstanpy`, restores the R packages from `renv.lock`, and checks that Gurobi is
visible. If you do not want the script to activate `.venv` in the current
shell, run `./setup_env.sh local` instead. If you need to force a fresh CmdStan
install, add `--overwrite-cmdstan`.

If Gurobi on macOS is not found automatically, set these variables before
running the setup command. Adjust the folder name to your installed version:

```bash
export GUROBI_HOME="/Library/gurobi1103/macos_universal2"
export PATH="$GUROBI_HOME/bin:$PATH"
export DYLD_LIBRARY_PATH="$GUROBI_HOME/lib:${DYLD_LIBRARY_PATH:-}"
export GRB_LICENSE_FILE="$HOME/gurobi.lic"
```

#### 1.2 Server Setup

On the server, the same setup is also one command:

```bash
source ./setup_env.sh server
```

This loads the server modules, creates `.venv`, installs the Python package and
Gurobi Python package, installs CmdStan, and leaves the environment active in
the current shell. Server setup skips `renv::restore()` by default because the
server workflow is designed to skip `Rscript` steps unless R is explicitly
available. If the server has a working R installation and you want to run R
steps there, use:

```bash
source ./setup_env.sh server --with-renv
```

Internally the default server setup uses the same module setup as:

```bash
module avail python gurobi gcc
module load python/anaconda-2022.05 gurobi/11.0 gcc/12.2.0
/software/python-anaconda-2022.05-el8-x86_64/bin/python3 -m venv .venv
source .venv/bin/activate
```
For later server sessions:

```bash
cd amazon-carbon-prices
module load python/anaconda-2022.05 gurobi/11.0 gcc/12.2.0
source .venv/bin/activate
```

Keep environment setup separate from the replication run. Slurm jobs source the
existing `.venv`; they should not reinstall Python packages, CmdStan, or R
packages inside every submitted job.

### Step 2. Prepare The Data Inputs

The raw data and calibrated inputs used for computation can be downloaded
[here](https://www.dropbox.com/scl/fo/n6gsyl7w2mki77eqew8ts/AMUKehiyaTFH2fjO5VotYwE?rlkey=iuk47v413domc1utvoa8x3yfp&st=ie2dyrzx&dl=0).

1. Create the data folder:

```bash
mkdir -p data
```

2. Download the `raw` data folder from the link above.

3. Move `raw` into `data/`, so the final structure is:

```text
data/raw/
  esa/
  fgv/
  global_forest_watch/
  ibge/
  ipea/
  mapbiomas/
  seabpr/
  seeg/
  worldbank/
  worldclim/
```

If the download also includes prepared `processed`, `clean`, or `calibration`
folders, place them under `data/` with the same folder names.

4. Generate processed, cleaned, and calibration data when starting from raw
   inputs. This stage also builds the Python-only Figure 1 output from the
   repo-internal World Bank inputs in `replication/figure1/`:

```bash
./run.sh --steps stage-data --backend local
```

If the server has R available, the same data step can be submitted to Slurm
with:

```bash
./run.sh --steps stage-data --backend slurm --run-r-on-slurm
```

If the server does not have R, run the R data-processing part locally and sync
the generated `data/processed/`, `data/clean/`, and `data/calibration/` folders
to the server before starting non-R Slurm stages. The `figure1` step itself can
run locally or on Slurm because it uses Python only.

The full workflow assumes these data outputs exist before estimation,
optimization, and post-processing steps are run.

### Step 3. Run The Whole Project

The single driver is `run.sh`. It runs commands locally by default and saves
local command logs under `job-outs/`.

#### 3.1 Local Machine

1. Run the full workflow in one command when you are comfortable letting the
   machine run for a long time:

```bash
./run.sh --steps all --backend local --jobs 1
```

2. Or run the workflow in shorter local stages, which is easier to monitor:

```bash
./run.sh --steps stage-data --backend local
./run.sh --steps stage-hmm --backend local --jobs 2
./run.sh --steps stage-deterministic --backend local --jobs 2
./run.sh --steps stage-hmc --backend local --jobs 2
./run.sh --steps stage-mpc --backend local --jobs 2
./run.sh --steps stage-postprocess --backend local
```

3. If you ran the heavy computations elsewhere and only need to refresh the
   final replication outputs locally, run:

```bash
./run.sh --steps maps hmc-maps --backend local --jobs 1
./run.sh --steps postprocess-only --backend local
```

4. For long local stages, run inside `tmux` and use macOS `caffeinate` so the
   job continues if the terminal window is closed and the machine does not
   sleep:

```bash
brew install tmux
tmux new -s amazon
caffeinate -dimsu ./run.sh --steps stage-deterministic --backend local --jobs 4
```

Detach from the tmux session with `Ctrl-b` then `d`, and return later with:

```bash
tmux attach -t amazon
```

#### 3.2 Slurm Server

1. Use the same driver on Slurm. The server backend uses the same stage aliases
   and command lists as the local backend. The only intentional difference is
   that `Rscript` commands are skipped on Slurm unless `--run-r-on-slurm` is
   supplied.

2. On Midway, Slurm may require an account on every `sbatch` submission. Check
   the account available to your user, then either export it once or pass it to
   `run.sh`:

```bash
sacctmgr show assoc user=$USER format=Account,Partition,QOS%30
export REPLICATION_SLURM_ACCOUNT="pi-lhansen"
```

   The same setting can be supplied inline:

```bash
./run.sh --steps stage-hmm --backend slurm --slurm-account pi-lhansen
```

   If your allocation uses a specific partition, also set
   `REPLICATION_SLURM_PARTITION` or pass `--slurm-partition`.

3. Large parallel steps are grouped on Slurm by default only when a step has at
   least 100 runnable commands. Each submitted Slurm job then runs 10
   replication commands sequentially, while each command still gets its own
   numbered `*_run.out` and `*_run.err`. The command line is written at the top
   of each `*_run.out` for auditing. The large MPC steps
   `mpc-sp-grid`, `mpc-hmc-pre`, `mpc-hmc-pre-unconstrained`,
   `mpc-hmc-pre-constrained`, `mpc-hmc-figure14-unconstrained`, `mpc-day0`,
   `mpc-day0-unconstrained`, and `mpc-day0-constrained` are a special case:
   they are always grouped as five commands per Slurm job. For
   the MPC-HMC steps, those five commands are the transfer levels
   `b=0,10,15,20,25` for one `(type, xi, id, trig)` block. This keeps stages
   such as `mpc-hmc-figure14-unconstrained` below server job-submission limits without
   changing small steps such as `baseline`, `maps`, or `mpc-tables`. To submit
   fewer Slurm jobs for other large steps, increase the group size:

```bash
./run.sh --steps stage-mpc --backend slurm --slurm-account pi-lhansen --slurm-commands-per-job 25
```

   Use a smaller value if grouped jobs are close to the Slurm time limit, or
   `--slurm-commands-per-job 1` to submit one Slurm job per replication command.
   To change the threshold for what counts as a large step, use
   `--slurm-group-min-commands`.

4. If the server does not have R, run the R data step locally first, then sync
   `data/processed/`, `data/clean/`, and `data/calibration/` to the server.
   Submit the non-R computation stages on the server with:

```bash
./run.sh --steps stage-hmm stage-deterministic stage-hmc stage-mpc stage-postprocess --backend slurm
```

This submits all Slurm jobs at once, but step order is preserved through Slurm
dependencies. Commands inside parallel-safe steps are submitted together; later
steps wait for upstream jobs to finish successfully.

5. If prepared data already exist on the server but R is not available, this is
   also valid. It skips `Rscript` steps and runs the Python/Gurobi/CmdStan
   parts:

```bash
./run.sh --steps all --backend slurm
```

6. If the server has R and the R environment has been restored there, submit the
   complete workflow including R data and plot steps with:

```bash
./run.sh --steps all --backend slurm --run-r-on-slurm
```

7. Before submitting a long server run, inspect the exact Slurm plan:

```bash
./run.sh --steps stage-hmm stage-deterministic stage-hmc stage-mpc stage-postprocess --backend slurm --dry-run
./run.sh --steps all --backend slurm --run-r-on-slurm --dry-run
```

8. Monitor submitted jobs with:

```bash
squeue -u $USER
sacct -u $USER --format=JobID,JobName,State,ExitCode
```

9. After Slurm jobs finish, sync `job-outs/`, `output/`, `plots/`, and
   `replication/derived/` back to the local machine. If R was skipped on the
   server, run the R plot steps and final audit locally:

```bash
./run.sh --steps maps hmc-maps --backend local --jobs 1
./run.sh --steps postprocess-only --backend local
```

10. Slurm writes driver logs to the same stage folders as local runs, for
   example `job-outs/stage_deterministic/shadow_prices_det/0001_run.out`.
   When submitting stages separately on Slurm, wait for one stage to finish
   before starting the next, because dependencies are tracked only within one
   `run.sh` invocation.

#### 3.3 Stage Notes

1. `stage-data` runs the R data-processing driver and the Python-only Figure 1
   reproduction. On Slurm without R, the R command is skipped unless
   `--run-r-on-slurm` is supplied, but `figure1` can still run.

2. `stage-deterministic` runs only the deterministic parameter-ambiguity shadow
   prices (`xi=\infty`, represented in code as `xi=10000`) before refreshing
   `replication/derived/carbon_prices.csv`.

3. `stage-hmc` runs the finite-`xi` shadow prices (`xi=0.5,1,2`), refreshes
   the same carbon-price file, generates the HMC sampling outputs for the
   selected `P^{ee}` plus transfer levels, and then constructs HMC tables and
   figures. After HMC sampling, it also runs `relative-entropy` to create
   `output/figures/entropy/site_1043/xi1.0/kl_divergences_theta_gamma.csv`
   and `density_sites_from_relative_entropy.csv`; the latter selects the
   density-plot sites from the top KL-divergence sites before HMC density
   figures are regenerated, and Figure 16 reads the former. For `xi=1`, the
   sampling step also generates the deterministic `P^{ee}` case used by the
   common-price HMC figures; both prices are read from
   `replication/derived/carbon_prices.csv`. Each HMC sampling command is one
   `(xi, price source, transfer)` job, so
   `b=0,10,15,20,25` can run in parallel instead of being bundled into one long
   job.

4. The Slurm backend skips `Rscript` commands by default because the server may
   not have R installed. Add `--run-r-on-slurm` only when R is available and the
   R environment has been restored on the server.

5. `stage-mpc` first creates MPC simulation paths, then runs the MPC
   shadow-price optimization grid (`xi=0.5,1,10000`, `P^{ee}=5.0,...,7.0`,
   constrained and unconstrained) before `mpc-prices` parses those grid outputs.
   The grid jobs are parallel-safe and are required before
   `pysrc/mpc/mpc_compute_sp.py` can read `output/optimization/mpc_shadow_price/`.
   By default, each grid job recomputes and overwrites its output folder, matching
   the original scripts and avoiding mixed old/new shadow-price outputs.
   After the MPC carbon prices are derived, the driver runs the unconstrained
   MPC-HMC/pre/day-0/table/figure block first, then runs the
   constrained MPC-HMC/pre/day-0/table block. Tables 6, 8, 12, 19,
   and 21 are reconstructed from day-0 outputs; Table 18 additionally uses
   simulation rows from `mpc_compute.py`, so those rows run only after the
   unconstrained Figure 14 MPC-HMC simulation jobs. Figure 14 is generated only
   from the unconstrained MPC-HMC jobs.
   Large MPC Slurm steps are submitted in groups of five commands. For the
   MPC-HMC steps, each group is one `(model, xi, id, trig)` case with
   `b=0,10,15,20,25`, matching the old `mpc_hmc.sh` loop while reducing the
   number of submitted Slurm jobs.

6. `stage-postprocess` runs after `stage-mpc` and is intentionally separate
   from the heavy MPC jobs. It refreshes derived carbon prices, MPC transition
   probabilities, paper-number manifests, aux-input tables, and aux-input
   figures.

7. The first HMC/shadow-price job on a machine may compile
   `stan_model/adjusted` from `stan_model/adjusted.stan`. Parallel server jobs
   use a compile lock so only one job compiles at a time; other jobs wait and
   then reuse the executable. If a previous failed run left partial compilation
   files, remove them before resubmitting:

```bash
rm -f stan_model/adjusted stan_model/adjusted.o stan_model/adjusted.hpp stan_model/adjusted.compile.lock
```

### Step 4. Process Generated Raw Results And Check Paper Outputs

After model jobs have produced raw outputs in `job-outs/`, `output/`, and
`plots/`, run the post-processing chain and lightweight replication audit:

```bash
./run.sh --steps postprocess-only --backend local
```

This expands to:

```text
derive-prices
mpc-probabilities
postprocess-final
aux-figures
```

Those steps do the following:

- `pysrc/replication/derive_carbon_prices.py` parses shadow-price and MPC logs,
  including original `run.out` logs and local numbered `0001_run.out` logs, and
  writes `replication/derived/carbon_price_candidates.csv` and
  `replication/derived/carbon_prices.csv`.
- `pysrc/replication/derive_mpc_transition_probabilities.py` parses
  stage-specific numbered MPC-HMC logs such as
  `job-outs/stage_mpc/mpc_hmc_*/*_run.out`
  and writes
  `replication/derived/mpc_transition_probabilities.csv`.
- `pysrc/replication/build_paper_numbers.py` writes
  `replication/exhibit_manifest.csv`, `replication/paper_numbers.csv`, and
  `replication/paper_numbers_missing_summary.csv`.
- `pysrc/replication/build_aux_input_tables.py` refreshes
  `aux_input/Table<number>_*.tex`, `aux_input/Figure<number>_*`,
  `replication/aux_input_table_manifest.csv`, and
  `replication/aux_input_figure_manifest.csv`.

The post-processing scripts do not read values from the manuscript PDF. Reported
numbers are extracted from generated outputs and logs.
If you need to regenerate the MPC day-0 table files first, run
`mpc-tables-unconstrained` and/or `mpc-tables-constrained` before
`postprocess-final`.

After the command finishes, check these generated files:

```text
replication/exhibit_manifest.csv
replication/paper_numbers.csv
replication/paper_numbers_missing_summary.csv
replication/aux_input_table_manifest.csv
replication/aux_input_figure_manifest.csv
aux_input/
```

If `paper_numbers_missing_summary.csv` reports missing outputs, generate the
upstream outputs listed in `replication/exhibit_manifest.csv`, then rerun:

```bash
./run.sh --steps postprocess-only --backend local
```

The workflow is self-contained and does not require a manuscript TeX or PDF
outside the repository. The optional `--paper-tex` argument in the build scripts
is only for maintainers who intentionally want to refresh
`replication/paper_figure_inputs.csv`.

### Step 5. Logs, Parallelism, And Dry Runs

Local and Slurm driver logs are saved under `job-outs/`, grouped first by
replication stage and then by step. Step folders use only the step name; the
per-command files keep their numeric prefixes:

```text
job-outs/
  stage_deterministic/
    shadow_prices_det/
      0001_run.out
      0001_run.err
      0002_run.out
      0002_run.err
  stage_hmc/
    shadow_prices_hmc/
      0001_run.out
      0001_run.err
  stage_mpc/
    mpc_prepare/
      0001_run.out
      0001_run.err
```

When `run.sh` starts, it safely renames older two-digit step folders such as
`16_postprocess_final` to `postprocess_final`. If the unprefixed folder already
exists, the old folder is skipped instead of being moved inside it.

MPC-HMC child output is written directly into the same stage-specific numbered
logs shown above; the driver does not create nested `job-outs/mpc/.../run.out`
files. Slurm batch scripts are submitted inline rather than saved as per-run
`.sh` files. Slurm driver-level `out`/`err` files use the same stage folders shown above.
Slurm creates and writes those files only after the scheduled job actually
starts, so a pending job may have no `Program starts` line yet. New Slurm
submissions set `PYTHONUNBUFFERED=1`, so Python progress is written to logs
while the command is running instead of waiting for process exit.
For grouped Slurm submissions, the group-level files are named like
`group_0001_0001_0010.out` and print the group start/end; each command inside
the group still writes the numbered files shown above with its own command
start/end. The group log also prints which numbered command is currently
running.
Running an individual named step also uses its canonical stage folder; for
example, `./run.sh --steps maps --backend local` writes to
`job-outs/stage_deterministic/maps/`.

To inspect commands without running them:

```bash
./run.sh --steps all --dry-run
```

To choose a subfolder under `job-outs/` for local logs:

```bash
./run.sh --steps stage-mpc --backend local --local-log-dir stage_mpc_logs
```

That command writes logs under `job-outs/stage_mpc_logs/stage_mpc/...`.

To stream output directly to the terminal:

```bash
./run.sh --steps postprocess-only --backend local --no-local-logs
```

To choose local `--jobs`, first check your machine:

```bash
python -c "import os; print(os.cpu_count())"
python -c "import os; print(round(os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE') / 1024**3, 1), 'GB')"
```

Start with `--jobs 1` or `--jobs 2` for memory-heavy HMC/MPC stages. Increase
only if CPU and memory pressure stay comfortable.

Available step names:

```text
data
figure1
price-estimation
baseline
shadow-prices
shadow-prices-det
shadow-prices-hmc
derive-prices
deterministic
hmc-sampling
hmc
relative-entropy
hmc-maps
mpc-prepare
mpc-prices
mpc-hmc-pre
mpc-hmc-pre-unconstrained
mpc-hmc-pre-constrained
mpc-probabilities
mpc-probabilities-unconstrained
mpc-probabilities-constrained
mpc-day0
mpc-day0-unconstrained
mpc-day0-constrained
mpc-tables
mpc-tables-unconstrained
mpc-tables-constrained
mpc-simulation-tables-unconstrained
mpc-hmc-figure14
mpc-hmc-figure14-unconstrained
mpc-figures
mpc-figures-unconstrained
aux-figures
bayesian-r2
maps
postprocess
postprocess-final
postprocess-only
stage-data
stage-hmm
stage-deterministic
stage-hmc
stage-mpc
stage-postprocess
all
```

Server module defaults can be tuned without editing code:

```bash
REPLICATION_SLURM_ACCOUNT="pi-lhansen"
REPLICATION_MODULES="python/anaconda-2022.05 gurobi/11.0 gcc/12.2.0"
REPLICATION_SLURM_TIME="1-11:00:00"
REPLICATION_SLURM_CPUS="8"
REPLICATION_SLURM_MEM="32G"
REPLICATION_SLURM_PARTITION="<partition-name>"
REPLICATION_SLURM_COMMANDS_PER_JOB="10"
REPLICATION_SLURM_GROUP_MIN_COMMANDS="100"
```

The legacy server helper `bash_files/hmc_shadow_price.sh` now delegates to
`run.sh` so its Slurm logs use the same numbered `job-outs/` format. Use
`bash_files/hmc_shadow_price.sh det` for only `xi=\infty` shadow prices, or
`bash_files/hmc_shadow_price.sh hmc` for only finite-`xi` HMC shadow prices.
The other replication helper scripts in `bash_files/` that correspond directly
to named driver steps, such as `price_estimation.sh`, `det_conduction.sh`,
`hmc_conduction.sh`, `mpc_prepare.sh`, `mpc_compute.sh`, and `mpc_hmc.sh`, also
delegate to `run.sh --backend slurm`. Low-level diagnostic or sampler helpers
that are not part of the staged driver keep their raw output layouts.

### Step 6. Reproducibility Notes

- Downstream scripts read `P^{ee}` from
  `replication/derived/carbon_prices.csv`; do not manually edit `pee` values.
- The infinite ambiguity case is represented internally as `xi=inf` and
  displayed as `\infty`; it is not the number `8`.
- `pysrc/replication/derive_mpc_transition_probabilities.py` finds
  `year done: 1` in each MPC log, reads the immediately preceding
  `Parameters from current iteration` vector, uses the second-to-last entry as
  `low -> low`, and uses one minus the last entry as `high -> high`.
- `pysrc/mpc/mpc_simulating.py --type converge_uncon` and
  `--type converge_con` read those derived transition probabilities; they do
  not rely on manually edited probability dictionaries.
- For a laptop or non-server check, use `--steps postprocess-only`.

## Legacy Scripts

The scripts in `bash_files/` are retained for compatibility with earlier server
runs. New replication runs should start with `run.sh`, which calls the current
Python and R entry points and keeps local and Slurm execution paths aligned.
