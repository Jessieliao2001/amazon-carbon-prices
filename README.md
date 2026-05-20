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
- `data/clean/` and `data/calibration/`: cleaned and calibrated data generated
  from the raw inputs.
- `rsrc/`: R data-cleaning, calibration, and map/figure scripts.
- `pysrc/`: Python package code for sampling, optimization, MPC, and shared
  helpers.
- `scripts/`: user-facing Python scripts and replication post-processing.
- `bash_files/`: legacy cluster helper scripts.
- `job-outs/`: selected original run logs used to derive reported carbon prices.
  Only the `run.out` files needed for the replication audit are intended to be
  version controlled.
- `output/` and `plots/`: generated tables, figures, and model outputs.
- `replication/`: derived replication metadata, exhibit manifest, and
  output-derived manuscript numbers.

## Requirements

- Python >= 3.9 and < 3.12.
- R with `renv`.
- Gurobi >= 10.0.3 for the optimization steps.
- CmdStan through `cmdstanpy` for the Stan sampling steps.
- Slurm is optional and only needed for `--backend slurm`.

On the Midway server, a typical module setup is:

```bash
module load python/anaconda-2022.05 gurobi/11.0 gcc/12.2.0
```

## Local Environment Setup

Set up the local environment before running any replication step. The Python
package versions used by the replication code are pinned in `pyproject.toml`;
the external tools that must be installed separately are Gurobi, a C/C++
compiler, CmdStan, and R.

Clone the repository:

```bash
git clone <repo-url>
cd amazon-carbon-prices
```

Recommended local Python setup with conda or mamba:

```bash
conda create -n amazon-carbon python=3.9.12 pip -y
conda activate amazon-carbon
python -m pip install -U pip setuptools wheel
python -m pip install -e ".[all]"
```

If geospatial dependencies are difficult to build with `pip`, install the main
Python stack from conda-forge first, then install this repository without
reinstalling dependencies:

```bash
mamba install -c conda-forge \
  numpy=1.25.2 pandas=2.1.0 geopandas=0.14.4 pyomo=6.6.2 \
  cmdstanpy=1.2.0 scipy=1.11.1 matplotlib=3.7.3 seaborn=0.13.2 \
  jinja2=3.1.6 hmmlearn=0.3.3 ipykernel black ruff pre-commit -y
python -m pip install -e . --no-deps
```

A plain virtual environment also works when system libraries are already
available:

```bash
python3.9 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install -e ".[all]"
```

Install Gurobi 11.0.x locally and configure a valid license. The server module
uses `gurobi/11.0`; local patch versions such as 11.0.3 are fine. After
installation, confirm both the command-line solver and Pyomo interface work:

```bash
gurobi_cl --version
python -m pip install "gurobipy==11.0.*"
python - <<'PY'
import pyomo.environ as pyo
solver = pyo.SolverFactory("gurobi")
print("gurobi available:", solver.available())
PY
```

On macOS, Gurobi usually also needs shell environment variables. Adjust the
folder name to your installed version:

```bash
export GUROBI_HOME="/Library/gurobi1103/macos_universal2"
export PATH="$GUROBI_HOME/bin:$PATH"
export DYLD_LIBRARY_PATH="$GUROBI_HOME/lib:${DYLD_LIBRARY_PATH:-}"
export GRB_LICENSE_FILE="$HOME/gurobi.lic"
```

Install a C/C++ compiler for Stan. On the server this is `gcc/12.2.0`; on macOS,
Apple Clang plus Homebrew GCC 12 is usually sufficient:

```bash
xcode-select --install
brew install gcc@12
gcc-12 --version
g++-12 --version
```

Install CmdStan if it is not already available:

```bash
install_cmdstan --overwrite
```

or equivalently:

```bash
python -m cmdstanpy.install_cmdstan --overwrite
```

Restore the R environment recorded in `renv.lock`:

```bash
Rscript -e 'install.packages("renv")'
Rscript -e 'renv::restore()'
```

Finally, run a quick local environment check:

```bash
python --version
python - <<'PY'
import numpy, pandas, geopandas, pyomo, cmdstanpy, scipy, matplotlib, seaborn, hmmlearn
print("python packages ok")
PY
gurobi_cl --version
Rscript -e 'renv::status()'
```

Activate the Python environment in every new shell before running replication
commands. For conda, use `conda activate amazon-carbon`; for a virtual
environment, use `source .venv/bin/activate`.

## Data Inputs

Place the raw data folder at `data/raw/` with the following structure:

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

Then generate the cleaned data:

```bash
./run.sh --steps data
```

The full workflow assumes the cleaned and calibration data have been produced
before the estimation and optimization steps are run.

## Main Driver

The main replication entry point is:

```bash
./run.sh
```

By default, this runs the lightweight post-processing workflow:

```bash
./run.sh --steps postprocess-only
```

This validates the existing output chain, derives carbon prices from run logs,
builds the exhibit manifest, and extracts manuscript numbers from generated
output files. It does not run the computationally heavy estimation or
optimization steps.

To run the full workflow locally:

```bash
./run.sh --steps all --backend local
```

To run independent pieces in parallel on a local machine, add `--jobs`. A
conservative laptop run might use:

```bash
./run.sh --steps all --backend local --jobs 4
```

To submit the same workflow on a Slurm server:

```bash
./run.sh --steps all --backend slurm
```

The Slurm backend submits a dependency chain: independent commands inside a
parallel-safe step are submitted together, and later steps wait on them with
`afterok` dependencies. The following environment variables can tune the Slurm
job wrapper without editing code:

```bash
REPLICATION_MODULES="python/anaconda-2022.05 gurobi/11.0 gcc/12.2.0"
REPLICATION_SLURM_TIME="1-11:00:00"
REPLICATION_SLURM_CPUS="8"
REPLICATION_SLURM_MEM="32G"
REPLICATION_SLURM_PARTITION="<partition-name>"
```

To inspect commands without running them:

```bash
./run.sh --steps all --dry-run
```

You can also run specific steps:

```bash
./run.sh --steps data price-estimation baseline shadow-prices derive-prices deterministic postprocess
```

## Staged Local Replication

For a local machine, it is often easier to run the replication in separate
stages. Run them in this order:

```bash
# 1. Data processing
./run.sh --steps stage-data --backend local

# 2. HMM, baseline posterior summaries, and Bayesian R2
./run.sh --steps stage-hmm --backend local --jobs 2

# 3. Deterministic model, carbon prices, and non-HMC maps
./run.sh --steps stage-deterministic --backend local --jobs 4

# 4. HMC ambiguity outputs and HMC maps
./run.sh --steps stage-hmc --backend local --jobs 3

# 5. MPC outputs and final post-processing audit
./run.sh --steps stage-mpc --backend local --jobs 4
```

The `stage-hmm` stage includes `baseline` because the Bayesian R2 figures and
posterior quantile tables use the baseline posterior/calibration outputs. The
`stage-deterministic` stage includes `shadow-prices` and `derive-prices` because
the downstream deterministic and HMC/MPC tables read carbon prices from
`replication/derived/carbon_prices.csv`.

If the original shadow-price logs are already available in `job-outs/` and you
only want a faster deterministic refresh, you can skip recomputing the
shadow-price jobs and run:

```bash
./run.sh --steps derive-prices deterministic maps --backend local --jobs 4
```

After any partial rerun, refresh the audit files with:

```bash
./run.sh --steps postprocess-only --backend local --jobs 4
```

The same stages work on Slurm:

```bash
./run.sh --steps stage-data --backend slurm
./run.sh --steps stage-hmm --backend slurm
./run.sh --steps stage-deterministic --backend slurm
./run.sh --steps stage-hmc --backend slurm
./run.sh --steps stage-mpc --backend slurm
```

When submitting stages separately on Slurm, wait for one stage to finish before
starting the next. If you want Slurm dependencies across the entire workflow in
one submission, use:

```bash
./run.sh --steps all --backend slurm
```

To choose local `--jobs`, first check your machine:

```bash
python -c "import os; print(os.cpu_count())"
python -c "import os; print(round(os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE') / 1024**3, 1), 'GB')"
```

As a rule of thumb, start with `--jobs 2` for memory-heavy optimization stages
and `--jobs 4` for a modern laptop or desktop. Increase only if CPU and memory
pressure stay comfortable. Avoid setting `--jobs` equal to the full logical CPU
count for the heavy HMC/MPC stages, because each job may also use solver,
BLAS/R, or Python worker threads internally.

Available step names are:

```text
data
price-estimation
baseline
shadow-prices
derive-prices
deterministic
mpc-prepare
mpc-prices
mpc-day0
mpc-probabilities
mpc-converge-paths
mpc-tables
mpc-figures
bayesian-r2
maps
hmc
hmc-maps
postprocess
postprocess-only
stage-data
stage-hmm
stage-deterministic
stage-hmc
stage-mpc
all
```

By default, the driver parallelizes independent commands within these steps:
`baseline`, `shadow-prices`, `mpc-prepare`, `mpc-day0`, `mpc-converge-paths`,
`mpc-tables`, `maps`, `hmc`, and `hmc-maps`. Use
`--parallel-steps none` to force serial execution, or pass an explicit list such
as `--parallel-steps hmc mpc-day0 mpc-tables`.

## Reported Numbers

The replication package does not read reported values from the manuscript PDF.
The manuscript PDF is useful for checking exhibit order, labels, and formatting,
but reported numbers are generated from code outputs.

Carbon prices are derived by:

```bash
python scripts/derive_carbon_prices.py
```

This script parses the original shadow-price and MPC run logs in `job-outs/`
and writes:

- `replication/derived/carbon_price_candidates.csv`
- `replication/derived/carbon_prices.csv`

Downstream scripts read these files through `pysrc.replication.parameters`
instead of requiring manual edits to `pee` values. The infinite ambiguity case
is represented internally as `xi=inf` and displayed as `\infty`; it is not the
number `8`.

The manuscript-number audit is built by:

```bash
python scripts/build_paper_numbers.py
```

It writes:

- `replication/exhibit_manifest.csv`: one row for each manuscript table or
  figure. Figure rows come from the repo-internal
  `replication/paper_figure_inputs.csv`, while table rows track the generated
  code outputs.
- `replication/paper_numbers.csv`: numbers extracted from generated outputs,
  including derived carbon prices and generated LaTeX tables.
- `replication/paper_numbers_missing_summary.csv`: which expected outputs are
  currently present, missing, or not yet generated in the working tree.

If an exhibit is marked as missing, run the command listed in the `program`
column of `replication/exhibit_manifest.csv` after creating the required
upstream model outputs.

Paper-formatted LaTeX inputs for the manuscript tables are built by:

```bash
python scripts/build_aux_input_tables.py
```

This writes `aux_input/Table<number>_*.tex` files from generated outputs and
derived CSV files, reads the repo-internal figure list in
`replication/paper_figure_inputs.csv`, and copies only those generated figures
to `aux_input/Figure<number>_*`. By default, it removes stale files from
`aux_input/` so the folder contains only the current code-generated manuscript
inputs. The table and figure numbers follow the current manuscript/PDF order
recorded in the repository. It also writes
`replication/aux_input_table_manifest.csv`,
`replication/paper_figure_inputs.csv`, and
`replication/aux_input_figure_manifest.csv`, which record the source output
files for the generated assets.

Table-format comparisons use stable cached templates in
`replication/aux_input_table_templates/`, not the cleaned `aux_input/` folder.
If old unprefixed table inputs are present, they are cached there before
cleanup; otherwise the cache is bootstrapped from the current generated
`Table<number>_*.tex` files.

The replication workflow is self-contained and does not require the manuscript
TeX file or PDF as an external input. The optional `--paper-tex` argument in
the build scripts is only for maintainers who intentionally want to refresh
`replication/paper_figure_inputs.csv`.

## Important Reproducibility Notes

- The old workflow required manually updating `pee` values in several scripts.
  The current workflow derives and reuses them from
  `replication/derived/carbon_prices.csv`.
- `scripts/build_paper_numbers.py` deliberately ignores the manuscript PDF and
  extracts numbers only from generated outputs.
- `scripts/derive_mpc_transition_probabilities.py` derives representative MPC
  transition probabilities from `job-outs/mpc/.../run.out`: for each log it
  finds `year done: 1`, reads the immediately preceding `Parameters from
  current iteration` vector, uses the second-to-last entry as `low -> low`, and
  uses one minus the last entry as `high -> high`. If those logs are absent, the
  corresponding tables remain marked as missing in
  `replication/paper_numbers_missing_summary.csv`.
- `pysrc/mpc/mpc_simulating.py --type converge_uncon` and
  `--type converge_con` read those derived transition probabilities; they do
  not rely on manually edited probability dictionaries.
- The current repo-internal figure list references a small number of inputs whose
  generated source files are not present in `output/` or `plots`; see
  `replication/paper_numbers_missing_summary.csv` and
  `replication/aux_input_figure_manifest.csv` for the exact list.
- The heavy steps require substantial compute and commercial solver access.
  For a laptop or non-server check, use `--steps postprocess-only`.

## Legacy Scripts

The scripts in `bash_files/` are retained for compatibility with earlier server
runs. New replication runs should start with `run.sh`, which calls the current
Python and R entry points and keeps local and Slurm execution paths aligned.
