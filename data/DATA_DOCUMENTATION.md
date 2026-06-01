# Data Documentation Companion

This companion file mirrors the source inventory in the root README. The root README is the authoritative documentation required by JPE. This directory contains the inputs and generated data products used by the
Amazon Carbon Prices replication workflow. The final journal archive should
include the complete `data/` directory. A GitHub mirror may omit large raw and
intermediate files, but the journal archive is the authoritative replication
package.

## Availability Statement

The package is designed to be reproducible from public administrative, market,
climate, remote-sensing, and carbon-price data. The final archive should include
the exact raw extracts used by the authors under `data/raw/`, plus generated
`data/processed/`, `data/clean/`, and `data/calibration/` files. No confidential
human-subject microdata are used.

After journal archiving, cite the archive DOI assigned by the journal
repository in the root `README.md`. Source-specific version numbers and access
dates should be retained when they are available from the original downloads or
embedded metadata.

## Raw Data Sources

The table below documents the current source-level structure. Source-specific
licenses and citation requirements remain with the original providers.

| Folder | Provider/source | Contents used in this project | Access and license notes |
| --- | --- | --- | --- |
| `data/raw/esa/above_ground_biomass/` | European Space Agency biomass products | Above-ground biomass raster inputs used to construct biomass/carbon-stock measures. | Public remote-sensing data; cite the ESA product/version used in the final archive. |
| `data/raw/fgv/deflator_ipa/` | Fundacao Getulio Vargas, Instituto Brasileiro de Economia | Deflator series used to prepare real price variables. | Public/third-party economic series; retain provider citation and terms. |
| `data/raw/ibge/` | Instituto Brasileiro de Geografia e Estatistica | Municipal boundaries, Amazon biome boundaries, agricultural census land-use variables, and cattle variables. | Public Brazilian statistical/geographic data; cite IBGE datasets and years. |
| `data/raw/ipea/` | Instituto de Pesquisa Economica Aplicada | Farm-gate price and distance-to-capital inputs. | Public Brazilian economic/geographic data; cite IPEA source tables. |
| `data/raw/mapbiomas/` | MapBiomas | Land-use/cover, municipal land-use cover, pasture quality, basin boundaries, and secondary vegetation age. | Public MapBiomas products; cite collection/version and follow MapBiomas terms. |
| `data/raw/seabpr/commodity_prices/` | Secretaria da Agricultura e do Abastecimento do Parana / DERAL | Commodity price inputs used in price preparation. | Public state agricultural price series; cite provider and access date. |
| `data/raw/seeg/emission/` | Sistema de Estimativas de Emissoes e Remocoes de Gases de Efeito Estufa | Emissions data used in data cleaning and Figure 1 support inputs. | Public emissions data; cite SEEG version/year. |
| `data/raw/worldbank/` | World Bank | Carbon-price and emission/GDP inputs, including repo-internal Figure 1 World Bank files in `replication/figure1/`. | Public World Bank data; metadata files are stored under `replication/figure1/documentation/`. |
| `data/raw/worldclim/` | WorldClim | Temperature and precipitation rasters. | Public climate data; cite WorldClim version/resolution. |

## Generated Data Products

| Folder | Description | Main scripts |
| --- | --- | --- |
| `data/processed/` | Intermediate municipal, pixel, biomass, land-use, emissions, and raster summaries generated from raw sources. | `rsrc/processing/_masterfile.R` and scripts under `rsrc/processing/`. |
| `data/clean/` | Cleaned source-specific R and raster objects used by processing and calibration scripts. | `rsrc/cleaning/_masterfile.R` and scripts under `rsrc/cleaning/`. |
| `data/calibration/` | Final calibrated site grids, model parameters, fitted productivity and carbon-response inputs used by Python and R analysis scripts. | `rsrc/calibration/_masterfile.R` and scripts under `rsrc/calibration/`. |
| `replication/derived/` | Output-derived CSVs used for paper-number audits and post-processing. | Scripts under `pysrc/replication/`. |

## Open-Format Equivalents For R Data Files

Some R scripts read `.Rdata` objects directly. Where practical, the archive also
contains CSV or GeoJSON equivalents for inspection outside R.

| R object | Open-format companion | Notes |
| --- | --- | --- |
| `data/calibration/calibration_1043_sites.Rdata` | `data/calibration/calibration_1043_sites.csv`, `data/calibration/grid_1043_sites.geojson` | Main 1043-site calibration panel and spatial grid. |
| `data/calibration/calibration_78_sites.Rdata` | `data/calibration/calibration_78_sites.csv`, `data/calibration/grid_78_sites.geojson` | Main 78-site calibration panel and spatial grid. |
| `data/calibration/gamma_calibration_1043_sites.Rdata` | `data/calibration/gamma_fit_1043.geojson`, `data/calibration/gamma_reg.geojson` | Carbon response calibration geometry and fitted values. |
| `data/calibration/gamma_calibration_78_sites.Rdata` | `data/calibration/gamma_fit_78.geojson` | 78-site carbon response calibration geometry and fitted values. |
| `data/calibration/theta_calibration_78_sites.Rdata` | `data/calibration/theta_fit_78.geojson`, `data/calibration/theta_reg.geojson` | 78-site productivity calibration geometry and fitted values. |
| `data/calibration/productivity_params_1043.csv` and `data/calibration/productivity_params_78.csv` | CSV native | Final fitted `gamma_fit` and `theta_fit` inputs. |
| `data/calibration/distribution_parameters_all_1043.csv` and `data/calibration/distribution_parameters_all_78.csv` | CSV native | Posterior/distribution parameter summaries. |
| `data/calibration/carbon_capture_curves/*.Rdata` and `.tif` files | Raster/native analysis files | Spatial/raster inputs for carbon-capture curve figures; these are not tabular but are open raster formats where possible. |

## Main Calibration Variables

`data/calibration/calibration_1043_sites.csv` and
`data/calibration/calibration_78_sites.csv` contain the main site-level analysis
variables. Important columns include:

- `id`: site identifier.
- `share_agricultural_use_*`, `share_forest_*`, `share_other_*`: land-cover shares by year.
- `site_area_ha`: site area in hectares.
- `share_amazon_biome`, `area_amazon_biome`: Amazon biome share and area.
- `z_1995`, `z_2008`, `z_2017`: carbon-stock related calibrated state variables.
- `zbar_1995`, `zbar_2008`, `zbar_2017`: site-level benchmark carbon-stock quantities.
- `gamma`, `gamma_fit`: carbon recovery/sequestration response parameters.
- `theta`, `theta_fit`: agricultural productivity parameters.
- `x_1995`, `x_2008`, `x_2017`: agricultural allocation variables.
- `mean_pa_2017`: agricultural price input used in calibration.
- `pasture_area_2017`: pasture area input.

The analysis scripts are the authoritative source for any transformations from
raw variables to model variables. Run `./run.sh --steps stage-data --backend
local` to rebuild the generated data products from raw inputs.
