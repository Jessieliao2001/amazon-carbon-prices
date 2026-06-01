# Amazon Carbon Prices Replication Package

This repository contains the data-cleaning, estimation, optimization, and
post-processing code for the Amazon carbon-prices manuscript. The replication
workflow is organized around a single driver, `run.sh`, and the exhibit audit
files in `replication/`.

The package is structured to be usable both on a local machine and on a server
or cluster. Local runs execute commands directly. Server runs can submit the
same steps through Slurm.

## Quick Start

Most users should use a local machine for R data/plot steps and a Slurm server
for the computationally heavy Python/Gurobi/CmdStan steps. The full workflow is
controlled by one entry point, `run.sh`.

```bash
git clone <repo-url>
cd amazon-carbon-prices
source ./setup_env.sh local
./run.sh --steps stage-data --backend local
```

Then sync the repository, `data/`, and any generated inputs to the server and
run the heavy non-R stages:

```bash
source ./setup_env.sh server
./run.sh --steps stage-hmm stage-deterministic stage-time-consistency stage-hmc stage-mpc --backend slurm --slurm-account pi-<pi_account_name>
```

When those server jobs finish, sync `job-outs/`, `output/`, `plots/`, and
`replication/derived/` back to the local machine, then run the R maps and final
audit locally:

```bash
./run.sh --steps maps hmc-maps --backend local --jobs 1
./run.sh --steps postprocess-only --backend local
```

If the server has R and the R environment has been restored there, submit the
complete workflow, including R data and map steps, in one command:

```bash
./run.sh --steps all --backend slurm --slurm-account pi-<pi_account_name> --run-r-on-slurm
```

Before any long run, inspect the exact plan without executing commands:

```bash
./run.sh --steps all --backend slurm --slurm-account pi-<pi_account_name> --run-r-on-slurm --dry-run
```

## Choosing Local Or Server Runs

| Use case | Recommended run location | Command pattern |
| --- | --- | --- |
| Build raw data products and R maps | Local machine, unless server R is configured | `./run.sh --steps stage-data --backend local`; after model outputs exist, `./run.sh --steps maps hmc-maps --backend local` |
| Run Python/Gurobi/CmdStan model jobs | Slurm server | `./run.sh --steps stage-hmm stage-deterministic stage-time-consistency stage-hmc stage-mpc --backend slurm --slurm-account <account>` |
| Server has no R | Run R stages locally, sync `data/`, then run non-R stages on Slurm | `./run.sh --steps stage-hmm stage-deterministic stage-time-consistency stage-hmc stage-mpc --backend slurm --slurm-account <account>` |
| Server has R and `renv` restored | Run everything on Slurm | `./run.sh --steps all --backend slurm --slurm-account <account> --run-r-on-slurm` |
| Heavy outputs already exist | Refresh tables, manifests, and `results_in_paper/` locally | `./run.sh --steps postprocess-only --backend local` |

## Workflow Overview And Runtime

The table below summarizes what each stage does, whether it needs R, and the
approximate runtime observed in the completed replication logs. Times are
hardware- and queue-dependent. The `observed wall time` column reflects the
logged wall-clock span when parallel jobs were allowed to run together; the
heavy MPC stage would take much longer if run strictly serially.

| Stage | Main tools | Needs R? | Parallel? | Observed wall time | Notes |
| --- | --- | --- | --- | --- | --- |
| `stage-data` | R, Python | Yes for raw data processing; Python only for Figure 1 | Mostly serial | About 4 hours | Builds `data/processed/`, `data/clean/`, `data/calibration/`, and Figure 1. |
| `stage-hmm` | Python, CmdStan | No | Partly parallel | About 1.5 hours | Price estimation, baseline sampling summaries, Bayesian R2. |
| `stage-deterministic` | Python, Gurobi, R maps | R only for maps | Parallel shadow-price jobs | About 2-3 hours | Deterministic shadow prices, deterministic tables, maps. |
| `stage-time-consistency` | Python, Gurobi | No | Two independent jobs | About 7.3 hours | Runs `bf=3.75` and `bf=5`. |
| `stage-hmc` | Python, CmdStan, Gurobi, R maps | R only for maps | Highly parallel | About 16 hours | Finite-`xi` shadow prices and HMC sampling are the bottlenecks. |
| `stage-mpc` | Python, Gurobi | No | Highly parallel | About 13-14 hours | MPC shadow-price grid and Figure 14 simulation jobs dominate. |
| `stage-postprocess` | Python | No | Mostly serial | Less than 1 minute | Builds audit CSVs, paper numbers, and `results_in_paper/`. |

With enough Slurm parallelism, the completed logs imply an end-to-end run of
roughly two days after environment setup and data placement are ready. The same
commands can run locally, but a one-worker local run is not practical for a fresh
full replication: the MPC Figure 14 simulation jobs alone accumulated more than
2,400 job-hours across parallel tasks. For local verification, prefer
`postprocess-only`, R map refreshes, or one stage at a time.

The most expensive steps are `stage_hmc/shadow_prices_hmc`,
`stage_hmc/hmc_sampling`, `stage_mpc/mpc_sp_grid`,
`stage_mpc/mpc_hmc_figure14_unconstrained`, and
`stage_time_consistency/time_consistency`. These are designed for parallel or
grouped Slurm execution. The required ordering is:

```text
data
  -> HMM and baseline sampling
  -> deterministic and HMC shadow-price searches
  -> derived carbon-price CSVs
  -> deterministic/HMC/MPC model outputs, maps, and tables
  -> postprocess-final and results_in_paper/
```

More specifically, HMC sampling must finish before `relative-entropy` and HMC
density/map figures; the MPC shadow-price grid must finish before `mpc-prices`;
and the MPC simulation jobs must finish before Table 18 and Figure 14 are
rebuilt. The only named steps that call `Rscript` are `data`, `maps`, and
`hmc-maps`; the other stages are Python, Gurobi, or CmdStan steps.

## Repository Layout

- `data/raw/`: raw input data. The final journal archive should include this folder; GitHub mirrors may omit large raw files.
- `data/processed/`, `data/clean/` and `data/calibration/`: processed, cleaned and calibrated data generated from the raw inputs.
- `data/codebook.csv`: source-level data inventory, access notes, generated-data descriptions, and open-format companion notes.
- `data/source_permissions.csv`: source-by-source audit record for access, license or terms, redistribution status, and final-review notes.
- `rsrc/`: R data-cleaning, calibration, and map/figure scripts.
- `pysrc/`: Python package code for sampling, optimization, MPC, and shared
  helpers.
- `pysrc/scripts/`: user-facing Python scripts that run analysis, estimation,
  figures, and workflow orchestration.
- `pysrc/replication/`: replication post-processing code that turns raw model
  outputs and logs into derived CSVs, manifests, paper numbers, and `results_in_paper`
  assets.
  The previous top-level `scripts` layout has been folded into `pysrc/` so
  Python code lives under one importable package tree.
- `replication/figure1/`: repo-internal World Bank inputs and
  `FIGURE1_DOCUMENTATION.md` notes for reproducing Figure 1 through
  `pysrc/scripts/figure1.py`.
- `job-outs/`: generated local or Slurm logs. The audit logs used to derive
  paper numbers are version controlled; routine run logs remain ignored.
- `output/` and `plots/`: generated tables, figures, and model outputs, not
  version controlled.
- `replication/`: static replication inputs, package manifests, generated
  manifests, and output-derived manuscript numbers.

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

The final journal replication archive should include the complete `data/`
directory: `data/raw/`, `data/processed/`, `data/clean/`, and
`data/calibration/`. A GitHub mirror may omit large raw and intermediate files;
if so, use the archived replication package as the authoritative data source.
During pre-archive review, the same raw-data bundle can be downloaded
[here](https://www.dropbox.com/scl/fo/n6gsyl7w2mki77eqew8ts/AMUKehiyaTFH2fjO5VotYwE?rlkey=iuk47v413domc1utvoa8x3yfp&st=ie2dyrzx&dl=0). The GitHub replication branch also provides
`data/calibration/` calibrated inputs as a reference and as a starting point for
users who want to skip raw-data calibration and reproduce the model, table, and
figure outputs directly.

Data availability statement: The package is designed to be reproducible from
public administrative, market, climate, remote-sensing, and carbon-price data.
The final JPE archive should contain the exact raw extracts used by the authors
plus the generated processed, cleaned, and calibrated data. No confidential
human-subject microdata are used. The data-source inventory, access notes,
provider names, generated-file descriptions, and `.Rdata` open-format
equivalents are documented below and in `data/codebook.csv`.
After journal archiving, cite the permanent archive DOI assigned by the journal
repository as the authoritative source for the complete replication package.
Because the full `data/`, `output/`, and `plots/` directories can exceed 10GB,
authors should coordinate with the JPE Data Editor before final upload if the
accepted archive must be split across multiple files.

Raw Excel files. Several third-party source files are archived in their
original `.xls` or `.xlsx` formats under `data/raw/` to preserve the exact raw
extracts used by the authors. These Excel files are raw archived sources, not
the final analysis data used in the paper tables and figures. The
data-processing scripts read the archived raw files and write generated CSV,
Rdata, GeoJSON, and raster products under `data/processed/`, `data/clean/`,
`data/calibration/`, and `replication/derived/`; those generated files are the
analysis inputs used by the model, table, figure, and post-processing scripts.

Data sources and citations. The manuscript's Appendix A describes the data construction in detail. The table below maps the data sources mentioned in the manuscript and used by the code to the package folders. All source-specific licenses and citation requirements remain with the original providers.

| Source | Package location | Use in paper/code | Citation or access note |
| --- | --- | --- | --- |
| World Bank / World Development Indicators and Climate Watch | `data/raw/worldbank/emission_kuznets/`, `replication/figure1/input/` | GDP per capita and CO2 emissions for Figure 1. | Manuscript Figure 1 states World Bank data were downloaded in March 2021. Metadata files are stored under `replication/figure1/documentation/`. |
| Fatos da Amazonia 2021 / Amazonia 2030 | `replication/figure1/reference/` and generated `replication/derived/figure1_source_data.csv` | Brazilian Amazon point in Figure 1. | Manuscript Figure 1 cites Fatos da Amazonia 2021, www.amazonia2030.org. |
| MapBiomas Collection 5 and related MapBiomas products | `data/raw/mapbiomas/` | Land-use/cover, total available area, agricultural area, deforestation, secondary vegetation age, pasture quality, and basin inputs. | Manuscript Appendix A and Section 5 cite MapBiomas and Souza et al. (2020); the text identifies Collection 5. |
| ANA/PNRH water-basin layers distributed through MapBiomas | `data/raw/mapbiomas/basin/` | Basin groups for agricultural-productivity random effects in Appendix C.1. | Manuscript Appendix C.1 notes sub-basins of the National Water Resources Plan, level 2, ANA 2006, available through MapBiomas. |
| ESA Biomass Climate Change Initiative | `data/raw/esa/above_ground_biomass/` | Above-ground biomass density for carbon absorption/productivity. | Manuscript cites Santoro and Cartus (2021), ESA Biomass CCI global above-ground biomass, v3; Appendix A.2 uses 2017 data. |
| SEEG | `data/raw/seeg/emission/` | Agricultural net emissions used to calibrate emissions contributed by agriculture. | Manuscript Appendix A.4 cites Sistema de Estimativas de Emissoes e Remocoes de Gases de Efeito Estufa and http://seeg.eco.br/. |
| IBGE | `data/raw/ibge/` | Municipal boundaries, Amazon biome, agricultural census land-use and cattle outputs. | Manuscript cites IBGE (2017), Censo Agropecuario Tables 6882 and 6911. |
| SEAB-PR / DERAL via IPEA | `data/raw/seabpr/commodity_prices/`, `data/raw/ipea/farm_gate_price/` | Monthly deflated cattle-price series and farm-gate prices. | Manuscript Appendix A.8 cites SEAB-PR (2021), IPEA distributor, accessed February 22, 2021. |
| IPEA | `data/raw/ipea/distance_to_capital/` | Distance-to-state-capital regressor in agricultural productivity. | Public IPEA geographic/economic input; retain source table and access date when known. |
| WorldClim | `data/raw/worldclim/` | Historical precipitation and temperature regressors. | Manuscript Appendix C.1 cites Fick and Hijmans (2017); raw files are WorldClim 2.1, 2.5-minute rasters. |
| FGV IBRE | `data/raw/fgv/deflator_ipa/` | Deflator used in price preparation. | Public/third-party economic series; retain provider citation and terms. |
| World Bank Carbon Pricing Dashboard / carbon-price files | `data/raw/worldbank/carbon_price/` | Carbon-pricing source inputs used by data-cleaning scripts and contextual outputs. | Include source files in the final archive; retain provider terms and access date when known. |

### Data References

The following data references are included here to make the replication package
self-contained. Provider-specific license and terms information should be
reviewed before the final JPE Dataverse deposit; the audit trail is maintained
in `data/source_permissions.csv`.

- Amazonia 2030. 2021. *Fatos da Amazonia 2021*. Amazonia 2030. URL:
  https://amazonia2030.org.br/. Used for the Brazilian Amazon point in Figure
  1. Access note: cited in the manuscript Figure 1 source note; retain the
  downloaded reference files under `replication/figure1/reference/`.
- Agencia Nacional de Aguas e Saneamento Basico (ANA). 2006. *National Water
  Resources Plan basin layers, level 2*. Distributed through MapBiomas basin
  inputs. URL: https://www.gov.br/ana/. Used for basin groups in Appendix C.1.
- European Space Agency Climate Change Initiative Biomass Project. 2021. *ESA
  Biomass Climate Change Initiative (Biomass_cci): Global Datasets of Forest
  Above-Ground Biomass for the Years 2010, 2017 and 2018, v3*. NERC EDS
  Centre for Environmental Data Analysis. DOI: 10.5285/5f331c418e9f4935b8eb1b836f8a91b8.
  URL: https://climate.esa.int/en/projects/biomass/. Used for 2017
  above-ground biomass inputs.
- Fick, Stephen E., and Robert J. Hijmans. 2017. "WorldClim 2: New 1-km
  Spatial Resolution Climate Surfaces for Global Land Areas." *International
  Journal of Climatology* 37 (12): 4302-4315. DOI: 10.1002/joc.5086.
  Project URL: https://www.worldclim.org/. The package uses WorldClim 2.1,
  2.5-minute historical temperature and precipitation rasters.
- Fundacao Getulio Vargas, Instituto Brasileiro de Economia (FGV IBRE).
  Deflator series used for price preparation. URL: https://portalibre.fgv.br/.
  Access note: retain exact raw files and access metadata in the final archive.
- Instituto Brasileiro de Geografia e Estatistica (IBGE). 2017. *Censo
  Agropecuario 2017*, including Tables 6882 and 6911, and associated municipal
  and biome geographies. URL: https://www.ibge.gov.br/. Used for agricultural
  census, cattle, municipal boundary, and Amazon biome inputs.
- Instituto de Pesquisa Economica Aplicada (IPEA). Ipeadata tables for
  distance-to-capital and farm-gate or commodity-price inputs. URL:
  https://www.ipeadata.gov.br/. Access notes: the manuscript reports SEAB-PR
  price data distributed through IPEA were accessed on February 22, 2021; the
  distance raw filename records an August 21, 2023 extract.
- MapBiomas Project. *Collection 5 Annual Land Cover and Land Use Maps of
  Brazil* and related MapBiomas products. URL: https://mapbiomas.org/. Used for
  land-use/cover, total available area, agricultural area, deforestation,
  secondary vegetation age, pasture quality, and basin inputs. See also Souza
  Jr. et al. (2020), cited in the manuscript.
- Secretaria da Agricultura e do Abastecimento do Parana, Departamento de
  Economia Rural (SEAB-PR/DERAL). 2021. Commodity price series distributed
  through IPEA. URL: https://www.agricultura.pr.gov.br/. Used for monthly
  cattle-price inputs; manuscript Appendix A.8 reports access through IPEA on
  February 22, 2021.
- Sistema de Estimativas de Emissoes e Remocoes de Gases de Efeito Estufa
  (SEEG). Greenhouse-gas emissions and removals data. URL: https://seeg.eco.br/.
  Used for agricultural net emissions and emissions calibration; raw filenames
  record a 2020.11.05 extract.
- Souza Jr., Carlos M., Julia Z. Shimbo, Marcos R. Rosa, Leandro L. Parente,
  Ane A. Alencar, Bernardo F. T. Rudorff, Heinrich Hasenack, et al. 2020.
  "Reconstructing Three Decades of Land Use and Land Cover Changes in Brazilian
  Biomes with Landsat Archive and Earth Engine." *Remote Sensing* 12 (17):
  2735. DOI: 10.3390/rs12172735. Cited by the manuscript for MapBiomas.
- World Bank. World Development Indicators and World Bank source files used for
  Figure 1, GDP per capita, emissions, and carbon-pricing inputs. URLs:
  https://data.worldbank.org/, https://databank.worldbank.org/source/world-development-indicators,
  and https://carbonpricingdashboard.worldbank.org/. Access note: manuscript
  Figure 1 reports World Bank data were downloaded in March 2021.
- World Resources Institute. Climate Watch data used with World Bank inputs for
  Figure 1 emissions context. URL: https://www.climatewatchdata.org/. Access
  note: retain exact downloaded extracts and metadata under `replication/figure1/`
  and `data/raw/worldbank/`.

Generated data and metadata. The archive includes `data/processed/`, `data/clean/`, and `data/calibration/` as generated analysis inputs. Some R scripts read `.Rdata` files directly. Where practical, the package includes open-format companions: for example, `calibration_1043_sites.Rdata` has `calibration_1043_sites.csv` and `grid_1043_sites.geojson`; `calibration_78_sites.Rdata` has `calibration_78_sites.csv` and `grid_78_sites.geojson`; carbon and productivity calibration objects have `gamma_fit_*.geojson`, `theta_fit_*.geojson`, and related CSV files. The machine-readable source inventory is in `data/codebook.csv`; source access and redistribution-review notes are in `data/source_permissions.csv`; and final archive inclusion/exclusion decisions are summarized in `replication/package_manifest.csv`.

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
   In the completed local replication logs, the full R data-processing stage took about 4 hours. The Python-only Figure 1 step took only a few seconds.

   If the server has R available, the same data step can be submitted to Slurm
   with:

   ```bash
   ./run.sh --steps stage-data --backend slurm --slurm-account pi-<pi_account_name> --run-r-on-slurm
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

A full local run is useful for transparency but is not recommended for the heavy
HMC and MPC stages unless the machine can run for many days. The server workflow
is the intended route for `stage-hmc`, `stage-mpc`, and `stage-time-consistency`.

2. Or run the workflow in shorter local stages, which is easier to monitor:

```bash
./run.sh --steps stage-data --backend local
./run.sh --steps stage-hmm --backend local --jobs 2
./run.sh --steps stage-deterministic --backend local --jobs 2
./run.sh --steps stage-time-consistency --backend local --jobs 2
./run.sh --steps stage-hmc --backend local --jobs 2
./run.sh --steps stage-mpc --backend local --jobs 2
./run.sh --steps stage-postprocess --backend local
```

3. If you ran the heavy computations elsewhere and only need to refresh the final replication outputs locally, run:

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
   export REPLICATION_SLURM_ACCOUNT="pi-<pi_account_name>"
   ```

   The same setting can be supplied inline:

   ```bash
   ./run.sh --steps stage-hmm --backend slurm --slurm-account pi-<pi_account_name>
   ```

   If your allocation uses a specific partition, also set
   `REPLICATION_SLURM_PARTITION` or pass `--slurm-partition`.

3. Large non-MPC parallel steps can be grouped on Slurm when a step has at
   least `--slurm-group-min-commands` runnable commands. Each grouped Slurm job
   runs `--slurm-commands-per-job` replication commands sequentially, while each
   command still gets its own numbered `*_run.out` and `*_run.err`. The command
   line is written at the top of each `*_run.out` for auditing.

   The completed MPC outputs in this package were generated with one replication
   command per Slurm job for the large MPC steps, including `mpc-sp-grid`,
   `mpc-hmc-pre-unconstrained`, `mpc-hmc-figure14-unconstrained`, and `mpc-day0-*`. This
   keeps each MPC output and log isolated, but it submits many jobs. If a cluster
   has strict job-submission limits, one feasible adjustment is to group the five
   transfer commands `b=0,10,15,20,25` for each `(model, xi, id, trig)` case by
   increasing `MPC_COMMANDS_PER_GROUP` in `pysrc/scripts/run_replication.py`,
   then inspecting the plan with `--dry-run` before submission.

   To group non-MPC large steps, use for example:

   ```bash
   ./run.sh --steps stage-hmc --backend slurm --slurm-account pi-<pi_account_name> --slurm-commands-per-job 25
   ```

   Use a smaller value if grouped jobs are close to the Slurm time limit, or
   `--slurm-commands-per-job 1` to submit one Slurm job per command. To change
   the threshold for what counts as a large step, use `--slurm-group-min-commands`.

4. If the server does not have R, run the R data step locally first, then sync
   `data/processed/`, `data/clean/`, and `data/calibration/` to the server.
   Submit the non-R computation stages on the server with:

   ```bash
   ./run.sh --steps stage-hmm stage-deterministic stage-time-consistency stage-hmc stage-mpc --backend slurm --slurm-account pi-<pi_account_name>
   ```

   This submits the non-R computation jobs at once, but step order is preserved
   through Slurm dependencies. Commands inside parallel-safe steps are submitted
   together; later steps wait for upstream jobs to finish successfully. After
   these jobs finish, sync the outputs back to the local machine, run
   `maps hmc-maps`, and then run `postprocess-only` so the final audit includes
   the R figures.

5. If prepared data already exist on the server but R is not available, this is
   also valid. It skips `Rscript` steps and runs the Python/Gurobi/CmdStan
   parts:

   ```bash
   ./run.sh --steps all --backend slurm --slurm-account pi-<pi_account_name>
   ```

6. If the server has R and the R environment has been restored there, submit the
   complete workflow including R data and plot steps with:

   ```bash
   ./run.sh --steps all --backend slurm --slurm-account pi-<pi_account_name> --run-r-on-slurm
   ```

7. Before submitting a long server run, inspect the exact Slurm plan:

   ```bash
   ./run.sh --steps stage-hmm stage-deterministic stage-time-consistency stage-hmc stage-mpc --backend slurm --slurm-account pi-<pi_account_name> --dry-run
   ./run.sh --steps all --backend slurm --slurm-account pi-<pi_account_name> --run-r-on-slurm --dry-run
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

5. `stage-time-consistency` runs the carrot-policy time-consistency evidence
   jobs for `bf=3.75` and `bf=5` at 1043 sites. These jobs are independent and
   can run in parallel. They write cached optimization objects and auditable
   summaries under `output/time_consistency/bf_*/`.

6. `stage-mpc` first creates MPC simulation paths, then runs the MPC
   shadow-price optimization grid (`xi=0.5,1,10000`, `P^{ee}=5.0,...,7.0`,
   constrained and unconstrained) before `mpc-prices` parses those grid outputs.
   The grid jobs are parallel-safe and are required before
   `pysrc/mpc/mpc_compute_sp.py` can read `output/optimization/mpc_shadow_price/`.
   By default, each grid job recomputes and overwrites its output folder, matching
   the original scripts and avoiding mixed old/new shadow-price outputs.
   After the MPC carbon prices are derived, the driver runs the unconstrained
   MPC-HMC pre/day-0/table/figure block first, then runs the constrained
   day-0/table block. The constrained MPC-HMC pre and constrained probability
   steps are not part of the current replication workflow. In the driver,
   The workflow uses the explicit unconstrained step names for MPC-HMC pre,
   MPC probabilities, Figure 14 simulations, and MPC figures. Tables 6, 8, 12, 19,
   and 21 are reconstructed from day-0 outputs; Table 18 additionally uses
   simulation rows from `mpc_compute.py`, so those rows run only after the
   unconstrained Figure 14 MPC-HMC simulation jobs. Figure 14 is generated only
   from the unconstrained MPC-HMC jobs.
   The completed MPC Slurm outputs were generated with one replication command
   per Slurm job, so each MPC output and numbered log is isolated. To reduce job
   count on a constrained cluster, consider grouping the five transfer commands
   for each `(model, xi, id, trig)` case by increasing `MPC_COMMANDS_PER_GROUP`
   in `pysrc/scripts/run_replication.py` and checking the result with
   `--dry-run`.

7. `stage-postprocess` runs after `stage-mpc` and is intentionally separate
   from the heavy MPC jobs. Carbon prices are derived earlier, immediately
   after the shadow-price and MPC price-search outputs that downstream steps
   need. The final stage refreshes MPC transition probabilities, paper-number
   manifests, results-in-paper tables, and results-in-paper figures.

   The computational dependencies are intentionally one-way: downstream scripts
   read `replication/derived/carbon_prices.csv`,
   `replication/derived/mpc_transition_probabilities.csv`, `output/`, and
   `plots/`; they do not require manual edits to paper tables. Within a single
   Slurm invocation, the driver submits later stages with dependencies so they
   wait for earlier stages to finish successfully.

8. The first HMC/shadow-price job on a machine may compile
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
mpc-probabilities-unconstrained
postprocess-final
results-in-paper-figures
```

Those steps do the following:

- `pysrc/replication/derive_mpc_transition_probabilities.py` parses
  stage-specific numbered MPC-HMC logs such as
  `job-outs/stage_mpc/mpc_hmc_*/*_run.out`
  and writes
  `replication/derived/mpc_transition_probabilities.csv`.
- `pysrc/replication/build_paper_numbers.py` writes
  `replication/exhibit_manifest.csv`, `replication/paper_numbers.csv`, and
  `replication/paper_numbers_missing_summary.csv`.
- `pysrc/replication/build_results_in_paper.py` refreshes
  `results_in_paper/Table<number>_*.tex`, `results_in_paper/Figure<number>_*`,
  `replication/results_in_paper_table_manifest.csv`, and
  `replication/results_in_paper_figure_manifest.csv`.

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
replication/results_in_paper_table_manifest.csv
replication/results_in_paper_figure_manifest.csv
results_in_paper/
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
derive-prices-det
derive-prices-hmc
derive-prices-mpc
deterministic
time-consistency
hmc-sampling
hmc-neutral-sampling
hmc
relative-entropy
hmc-maps
mpc-prepare
mpc-sp-grid
mpc-prices
mpc-hmc-pre-unconstrained
mpc-probabilities-unconstrained
mpc-day0
mpc-day0-unconstrained
mpc-day0-constrained
mpc-tables
mpc-tables-unconstrained
mpc-tables-constrained
mpc-simulation-tables-unconstrained
mpc-hmc-figure14-unconstrained
mpc-figures-unconstrained
results-in-paper-figures
bayesian-r2
maps
postprocess-final
postprocess-only
stage-data
stage-hmm
stage-deterministic
stage-time-consistency
stage-hmc
stage-mpc
stage-postprocess
all
```

Server module defaults can be tuned without editing code:

```bash
REPLICATION_SLURM_ACCOUNT="pi-<pi_account_name>"
REPLICATION_MODULES="python/anaconda-2022.05 gurobi/11.0 gcc/12.2.0"
REPLICATION_SLURM_TIME="1-11:00:00"
REPLICATION_SLURM_CPUS="8"
REPLICATION_SLURM_MEM="32G"
REPLICATION_SLURM_PARTITION="<partition-name>"
REPLICATION_SLURM_COMMANDS_PER_JOB="10"
REPLICATION_SLURM_GROUP_MIN_COMMANDS="100"
```

The clean replication branch uses `run.sh` as the single entry point for both
local and Slurm runs.

### Step 6. Reproducibility Notes

- Downstream scripts read `P^{ee}` from
  `replication/derived/carbon_prices.csv`; do not manually edit `pee` values.
- `pysrc/replication/derive_mpc_transition_probabilities.py` finds
  `year done: 1` in each MPC log, reads the immediately preceding
  `Parameters from current iteration` vector, uses the second-to-last entry as
  `low -> low`, and uses one minus the last entry as `high -> high`.

### Rights And License

The code written for this replication package is released under the MIT License;
see `LICENSE.txt`. Author-created derived data, tables, figures, manifests, and
documentation are released for academic replication under the terms stated in
`LICENSE.txt`. Third-party raw data in `data/raw/` remain subject to the terms of
the original providers listed above and in `data/codebook.csv`; they are included
in the journal archive only to allow exact replication of the reported results.
Users who reuse the raw sources outside replication should consult and follow the
original providers' licenses and citation requirements.

I certify that the authors of the manuscript have legitimate access to and
permission to use the data used in this manuscript. I certify that the authors
have documented permission to redistribute or publish the data contained within
this replication package to the extent stated in `LICENSE.txt`; third-party raw
data remain subject to their original provider terms.
