# Replication Outputs

This directory records the current replication post-processing logic. The files here are generated from code outputs and repo-internal metadata, not from OCR or manual transcription from the PDF.

## Regenerate

Run the local post-processing check with:

```bash
./run.sh --steps postprocess-only
```

The normal replication workflow is self-contained and does not require any manuscript TeX or PDF file outside the repository. Maintainers can optionally pass `--paper-tex` directly to `pysrc/replication/build_paper_numbers.py` or `pysrc/replication/build_aux_input_tables.py` only when intentionally refreshing `paper_figure_inputs.csv`.

For long local runs, use the staged aliases documented in the root `README.md`:
`stage-data`, `stage-hmm`, `stage-deterministic`, `stage-hmc`, and `stage-mpc`.
The deterministic stage runs only the `xi=\infty` (`xi=10000`) shadow-price
searches; the HMC stage runs the finite-`xi` shadow-price searches and refreshes
the carbon-price file again before HMC outputs are built. The HMC sampling step
uses those derived prices, including the extra `xi=1` deterministic-price case
needed by the common-price HMC figures. HMC sampling is submitted as one
`(xi, price source, transfer)` command per job so transfer levels can run in
parallel. The HMC stage also runs `relative-entropy` before `hmc-maps`, because
Figure 16 reads `output/figures/entropy/site_1043/xi1.0/kl_divergences_theta_gamma.csv`.
The MPC stage includes the MPC shadow-price optimization grid before
`mpc-prices`, because `pysrc/mpc/mpc_compute_sp.py` parses those grid outputs.
Grid jobs recompute and overwrite existing output folders by default, matching
the original scripts and avoiding mixed old/new shadow-price outputs.
Large MPC Slurm steps are grouped five commands at a time; each MPC-HMC group
corresponds to one `(model, xi, id, trig)` case and its five transfer levels.
Within `stage-mpc`, the unconstrained MPC-HMC/pre/day-0/table/figure outputs are
run before the constrained MPC-HMC/pre/day-0/table outputs. Figure 14 is
unconstrained-only.
For example:

```bash
./run.sh --steps stage-hmc --backend local --jobs 3
./run.sh --steps stage-mpc --backend local --jobs 4
```

## Logic

- `pysrc/replication/derive_carbon_prices.py` builds `derived/carbon_prices.csv` from generated shadow-price outputs and logs, including original `run.out` files and local numbered `0001_run.out` files. Downstream tables read `P^{ee}` from this file.
- `pysrc/replication/derive_mpc_transition_probabilities.py` builds `derived/mpc_transition_probabilities.csv` from stage-specific numbered MPC-HMC logs, such as `job-outs/stage_mpc/*_mpc_hmc_*/*_run.out`. For each log it finds the first `year done: 1`, reads the immediately preceding `Parameters from current iteration` vector, uses the second-to-last value as "Prob from low to low", and uses `1 - last value` as "Prob from high to high".
- `replication/paper_figure_inputs.csv` is the repo-internal source of truth for figures used in the paper. `pysrc/replication/paper_assets.py` reads this file during normal replication and can optionally refresh it from a TeX source for maintenance.
- `replication/figure1/` stores the repo-internal World Bank inputs for Figure 1. `pysrc/scripts/figure1.py` turns those inputs into `output/figures/scatter_emission_gdp_log.png` and `replication/derived/figure1_source_data.csv`.
- `pysrc/replication/build_paper_numbers.py` writes `exhibit_manifest.csv`, `paper_numbers.csv`, and `paper_numbers_missing_summary.csv`.
- `pysrc/replication/build_aux_input_tables.py` writes `aux_input_table_manifest.csv`, `aux_input_figure_manifest.csv`, and refreshes `aux_input/` so it contains only generated `Table<number>_*.tex` and `Figure<number>_*` files.
- `replication/aux_input_table_templates/` stores stable table-format references so rerunning after `aux_input/` cleanup does not depend on removed unprefixed table files.

## Files

- `paper_figure_inputs.csv`: required repo-internal list of paper figure inputs used for replication tracking.
- `figure1/`: World Bank inputs, metadata, and reference standalone scripts for Figure 1.
- `exhibit_manifest.csv`: tables plus the repo-internal figure list used for replication tracking.
- `paper_numbers.csv`: output-derived table cells, carbon prices, and MPC transition probabilities.
- `paper_numbers_missing_summary.csv`: generated-output coverage by table/figure.
- `aux_input_table_manifest.csv`: source files and optional numeric-format checks for generated aux input tables.
- `aux_input_table_templates/`: cached table-format references used by `aux_input_table_manifest.csv`.
- `aux_input_figure_manifest.csv`: paper figure inputs matched to generated figure files copied into `aux_input/`.
