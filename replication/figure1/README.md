# Figure 1 Inputs

This folder contains the repo-internal inputs used to reproduce Figure 1,
which plots 2018 emissions per capita against 2018 GDP per capita PPP and
highlights China, India, the European Union, the United States, and the
Brazilian Amazon.

Run it through the main replication driver:

```bash
./run.sh --steps figure1 --backend local
```

The full `stage-data` and `all` workflows also run this step. On Slurm, the
same command works with `--backend slurm`; unlike the R data-cleaning command,
the Figure 1 step is Python-only and can run on a server without R.

Inputs:

- `input/`: World Bank WDI CSV files for GDP per capita PPP and emissions per
  capita.
- `documentation/`: World Bank country and indicator metadata.

Generated outputs:

- `output/figures/scatter_emission_gdp_log.png`
- `output/figures/scatter_emission_gdp_log.pdf`
- `replication/derived/figure1_source_data.csv`

The `reference/` folder preserves the standalone scripts that came with the
original Figure 1 package. The integrated replication workflow uses
`pysrc/scripts/figure1.py` so paths and output names match the rest of this
repository.
