from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pysrc.replication.paper_assets import (
    DEFAULT_PAPER_TEX,
    PAPER_FIGURE_INPUTS_FILE,
    read_or_build_paper_figure_inputs,
    resolve_generated_figure,
)
from pysrc.replication.parameters import CARBON_PRICE_FILE, normalize_xi, xi_for_label
from pysrc.services.file_service import get_path


EXHIBITS = [
    {
        "exhibit": "Figure 1",
        "kind": "figure",
        "description": "Country emissions relative to GDP, with Brazilian Amazon highlighted",
        "output_pattern": "plots/emission_kuznets/*.png",
        "program": "not currently scripted in this repository",
        "status_note": "missing analysis script; data cleaning exists in rsrc/cleaning/clean_emission_kuznets.R",
    },
    {
        "exhibit": "Figure 2",
        "kind": "figure",
        "description": "Actual versus theoretical carbon recovery fraction",
        "output_pattern": "output/figures/carbon_capture/gamma_secondary_vegetation.png",
        "program": "Rscript rsrc/analysis/carbon_capture_curves/_masterfile.R",
        "status_note": "",
    },
    {
        "exhibit": "Figure 3",
        "kind": "figure",
        "description": "Initial agricultural area and carbon stock maps",
        "output_pattern": "plots/calibration/1043SitesModel/map_z2017_1043Sites.png|plots/calibration/1043SitesModel/map_x2017_1043Sites.png",
        "program": "Rscript rsrc/analysis/calibration_maps_1043_sites.R",
        "status_note": "",
    },
    {
        "exhibit": "Figure 4",
        "kind": "figure",
        "description": "Carbon sequestration and agricultural productivity maps",
        "output_pattern": "plots/calibration/1043SitesModel/map_gamma_fit.png|plots/calibration/1043SitesModel/map_theta_fit.png",
        "program": "Rscript rsrc/analysis/calibration_maps_1043_sites.R",
        "status_note": "",
    },
    {
        "exhibit": "Figure 5",
        "kind": "figure",
        "description": "Agricultural area and cumulative CO2 capture",
        "output_pattern": "output/figures/pred_zshare_1043_sites_det.png|output/figures/plot_pred_x_1043_sites_det.png",
        "program": "python pysrc/scripts/conduction_det.py",
        "status_note": "",
    },
    {
        "exhibit": "Figure 6",
        "kind": "figure",
        "description": "Evolution of transfer payments",
        "output_pattern": "output/figures/net_transfers.png",
        "program": "python pysrc/scripts/conduction_det.py",
        "status_note": "",
    },
    {
        "exhibit": "Figure 7",
        "kind": "figure",
        "description": "Agricultural area changes after 30 years",
        "output_pattern": "plots/1043-det/map_z0z30GammaTheta_1043Sites_allPrices_det.png",
        "program": "Rscript rsrc/analysis/map_1043_det.R",
        "status_note": "",
    },
    {
        "exhibit": "Figure 8",
        "kind": "figure",
        "description": "Agricultural area evolution over time",
        "output_pattern": "plots/1043-det/map_zDecades_1043Sites_pe*_det.png",
        "program": "Rscript rsrc/analysis/map_1043_det.R",
        "status_note": "",
    },
    {
        "exhibit": "Figure 9",
        "kind": "figure",
        "description": "Ambiguity-adjusted densities for four sites",
        "output_pattern": "output/figures/density/site_1043/xi1*/**/*.png",
        "program": "python pysrc/scripts/conduction_hmc.py --figures density --xi 1",
        "status_note": "",
    },
    {
        "exhibit": "Figure 10",
        "kind": "figure",
        "description": "Timing histogram at common business-as-usual carbon price",
        "output_pattern": "output/figures/decision_histogram_pehmc_*_pedet_*_xi_1.0.png",
        "program": "python pysrc/scripts/conduction_hmc.py --figures histograms --xi 1",
        "status_note": "",
    },
    {
        "exhibit": "Figure 11",
        "kind": "figure",
        "description": "Agricultural area under ambiguity neutrality and aversion at common price",
        "output_pattern": "output/figures/aggregate_percentage_Z_b0_pehmc_*_pedet_*_xi_1.0.png",
        "program": "python pysrc/scripts/conduction_hmc.py --figures trajectories --xi 1",
        "status_note": "",
    },
    {
        "exhibit": "Figure 12",
        "kind": "figure",
        "description": "Timing histograms using corresponding shadow prices",
        "output_pattern": "output/figures/decision_histogram_pehmc_*_pedet_*_xi_1.0.png",
        "program": "python pysrc/scripts/conduction_hmc.py --figures histograms --xi 1",
        "status_note": "",
    },
    {
        "exhibit": "Figure 13",
        "kind": "figure",
        "description": "Agricultural area using corresponding shadow prices",
        "output_pattern": "output/figures/aggregate_percentage_Z_b*_pehmc_*_pedet_*_xi_1.0.png",
        "program": "python pysrc/scripts/conduction_hmc.py --figures trajectories --xi 1",
        "status_note": "",
    },
    {
        "exhibit": "Figure 14",
        "kind": "figure",
        "description": "Agricultural area under price uncertainty",
        "output_pattern": "output/figures/mpc_landallocation_b_0_adjust.png|output/figures/mpc_landallocation_b_15_adjust.png",
        "program": "python pysrc/scripts/mpc_trajectory.py",
        "status_note": "",
    },
    {
        "exhibit": "Figure 15",
        "kind": "figure",
        "description": "Smoothed hidden-state probabilities",
        "output_pattern": "output/figures/smooth_prob_uncon.png|output/figures/smooth_prob_con.png",
        "program": "python pysrc/scripts/price_estimation.py",
        "status_note": "",
    },
    {
        "exhibit": "Figure 16",
        "kind": "figure",
        "description": "Relative entropy by site",
        "output_pattern": "plots/1043-hmc/re_theta_b0.png|plots/1043-hmc/re_theta_b15.png|plots/1043-hmc/re_gamma_b0.png|plots/1043-hmc/re_gamma_b15.png",
        "program": "Rscript rsrc/analysis/map_kl.R",
        "status_note": "",
    },
    {
        "exhibit": "Figure 17",
        "kind": "figure",
        "description": "Ambiguity-adjusted densities, xi=2",
        "output_pattern": "output/figures/density/site_1043/xi2*/**/*.png",
        "program": "python pysrc/scripts/conduction_hmc.py --figures density --xi 2",
        "status_note": "",
    },
    {
        "exhibit": "Figure 18",
        "kind": "figure",
        "description": "Ambiguity-adjusted densities, xi=0.5",
        "output_pattern": "output/figures/density/site_1043/xi0.5*/**/*.png",
        "program": "python pysrc/scripts/conduction_hmc.py --figures density --xi 0.5",
        "status_note": "",
    },
    {
        "exhibit": "Figure 19",
        "kind": "figure",
        "description": "Agricultural area evolution with ambiguity aversion, xi=1",
        "output_pattern": "plots/1043-hmc_xi1/map_zDecades_1043Sites_pe*_hmc.png",
        "program": "Rscript rsrc/analysis/map_1043_hmc_xi1.R",
        "status_note": "",
    },
    {
        "exhibit": "Figure 20",
        "kind": "figure",
        "description": "Agricultural area evolution with ambiguity aversion, xi=0.5",
        "output_pattern": "plots/1043-hmc_xi05/map_zDecades_1043Sites_pe*_hmc.png",
        "program": "Rscript rsrc/analysis/map_1043_hmc_xi05.R",
        "status_note": "",
    },
    {
        "exhibit": "Figure 21",
        "kind": "figure",
        "description": "Bayesian R-squared densities",
        "output_pattern": "output/figures/bayesian_r2_gamma_1043.png|output/figures/bayesian_r2_theta_1043.png",
        "program": "python pysrc/scripts/bayesian_R2.py",
        "status_note": "",
    },
    {
        "exhibit": "Table 1",
        "kind": "table",
        "description": "Business-as-usual prices under parameter ambiguity",
        "output_pattern": "replication/derived/carbon_prices.csv",
        "program": "python pysrc/replication/derive_carbon_prices.py",
        "status_note": "xi infinity is represented as xi=inf, not as 8",
    },
    {
        "exhibit": "Table 2",
        "kind": "table",
        "description": "Present-value decomposition under ambiguity neutrality",
        "output_pattern": "output/tables/present_value_site1043_pa41.11_det.tex",
        "program": "python pysrc/scripts/conduction_det.py",
        "status_note": "",
    },
    {
        "exhibit": "Table 3",
        "kind": "table",
        "description": "Transfer costs under ambiguity neutrality",
        "output_pattern": "output/tables/transfer_cost_1043site_41.11pa_15year_det.tex|output/tables/transfer_cost_1043site_41.11pa_30year_det.tex",
        "program": "python pysrc/scripts/conduction_det.py",
        "status_note": "",
    },
    {
        "exhibit": "Table 4",
        "kind": "table",
        "description": "Present-value decomposition under parameter ambiguity, xi=1",
        "output_pattern": "output/tables/present_value_site_ambiguity_comparison_xi_1.0.tex",
        "program": "python pysrc/scripts/conduction_hmc.py --tables ambiguity --xi 1",
        "status_note": "",
    },
    {
        "exhibit": "Table 5",
        "kind": "table",
        "description": "Business-as-usual prices with stochastic agricultural prices",
        "output_pattern": "replication/derived/carbon_prices.csv",
        "program": "python pysrc/replication/derive_carbon_prices.py",
        "status_note": "uses MPC shadow-price logs",
    },
    {
        "exhibit": "Table 6",
        "kind": "table",
        "description": "MPC present-value decomposition for b=0",
        "output_pattern": "output/mpc/*present_value_mpc_b0_sites78_xi_*_unconstrained.tex",
        "program": "python pysrc/mpc/mpc_compute.py --model unconstrained --b 0 --xi all",
        "status_note": "",
    },
    {
        "exhibit": "Table 7",
        "kind": "table",
        "description": "Uncertainty-adjusted transition probabilities for b=0",
        "output_pattern": "replication/derived/mpc_transition_probabilities.csv",
        "program": "python pysrc/replication/derive_mpc_transition_probabilities.py",
        "status_note": "derived from MPC run.out logs at year done: 1, not from the paper",
    },
    {
        "exhibit": "Table 8",
        "kind": "table",
        "description": "MPC present-value decomposition for b=15",
        "output_pattern": "output/mpc/*present_value_mpc_b15_sites78_xi_*_unconstrained.tex",
        "program": "python pysrc/mpc/mpc_compute.py --model unconstrained --b 15 --xi all",
        "status_note": "",
    },
    {
        "exhibit": "Table 9",
        "kind": "table",
        "description": "Uncertainty-adjusted transition probabilities for b=15",
        "output_pattern": "replication/derived/mpc_transition_probabilities.csv",
        "program": "python pysrc/replication/derive_mpc_transition_probabilities.py",
        "status_note": "derived from MPC run.out logs at year done: 1, not from the paper",
    },
    {
        "exhibit": "Table 10",
        "kind": "table",
        "description": "Hidden-state Markov estimates",
        "output_pattern": "output/tables/hmm_results_table.tex",
        "program": "python pysrc/scripts/price_estimation.py",
        "status_note": "",
    },
    {
        "exhibit": "Table 11",
        "kind": "table",
        "description": "Hidden-state likelihood and information criteria",
        "output_pattern": "output/tables/hmm_information_criteria.tex",
        "program": "python pysrc/scripts/price_estimation.py",
        "status_note": "",
    },
    {
        "exhibit": "Table 12",
        "kind": "table",
        "description": "Common-variance hidden-state MPC decomposition",
        "output_pattern": "output/mpc/*present_value_mpc_b*_sites78_xi_*_constrained.tex",
        "program": "python pysrc/mpc/mpc_compute.py --model constrained --b all --xi all",
        "status_note": "",
    },
    {
        "exhibit": "Table 13",
        "kind": "table",
        "description": "Present-value decomposition under ambiguity neutrality for 78 sites",
        "output_pattern": "output/tables/present_value_site78_pa41.11_det.tex",
        "program": "python pysrc/scripts/conduction_det.py",
        "status_note": "",
    },
    {
        "exhibit": "Table 14",
        "kind": "table",
        "description": "Transfer costs under ambiguity, 15 years",
        "output_pattern": "output/tables/transfer_cost_1043site_41.11pa_15year_hmc_xi_1.0.tex",
        "program": "python pysrc/scripts/conduction_hmc.py --tables transfer-cost --xi 1",
        "status_note": "",
    },
    {
        "exhibit": "Table 15",
        "kind": "table",
        "description": "Transfer costs under ambiguity, 30 years",
        "output_pattern": "output/tables/transfer_cost_1043site_41.11pa_30year_hmc_xi_1.0.tex",
        "program": "python pysrc/scripts/conduction_hmc.py --tables transfer-cost --xi 1",
        "status_note": "",
    },
    {
        "exhibit": "Table 16",
        "kind": "table",
        "description": "Present-value decomposition under parameter ambiguity, xi=2",
        "output_pattern": "output/tables/present_value_site_ambiguity_comparison_xi_2.0.tex",
        "program": "python pysrc/scripts/conduction_hmc.py --tables ambiguity --xi 2",
        "status_note": "",
    },
    {
        "exhibit": "Table 17",
        "kind": "table",
        "description": "Present-value decomposition under parameter ambiguity, xi=0.5",
        "output_pattern": "output/tables/present_value_site_ambiguity_comparison_xi_0.5.tex",
        "program": "python pysrc/scripts/conduction_hmc.py --tables ambiguity --xi 0.5",
        "status_note": "",
    },
    {
        "exhibit": "Table 18",
        "kind": "table",
        "description": "MPC initial-period versus simulation value decomposition",
        "output_pattern": "output/mpc/day0_present_value_mpc_*.tex",
        "program": "python pysrc/mpc/mpc_compute_day0.py",
        "status_note": "",
    },
    {
        "exhibit": "Table 19",
        "kind": "table",
        "description": "MPC decomposition for b=10",
        "output_pattern": "output/mpc/*present_value_mpc_b10_sites78_xi_*_unconstrained.tex",
        "program": "python pysrc/mpc/mpc_compute.py --model unconstrained --b 10 --xi all",
        "status_note": "",
    },
    {
        "exhibit": "Table 20",
        "kind": "table",
        "description": "Representative distorted transition probabilities, b=10",
        "output_pattern": "replication/derived/mpc_transition_probabilities.csv",
        "program": "python pysrc/replication/derive_mpc_transition_probabilities.py",
        "status_note": "derived from MPC run.out logs at year done: 1, not from the paper",
    },
    {
        "exhibit": "Table 21",
        "kind": "table",
        "description": "MPC decomposition for b=25",
        "output_pattern": "output/mpc/*present_value_mpc_b25_sites78_xi_*_unconstrained.tex",
        "program": "python pysrc/mpc/mpc_compute.py --model unconstrained --b 25 --xi all",
        "status_note": "",
    },
    {
        "exhibit": "Table 22",
        "kind": "table",
        "description": "Representative distorted transition probabilities, b=25",
        "output_pattern": "replication/derived/mpc_transition_probabilities.csv",
        "program": "python pysrc/replication/derive_mpc_transition_probabilities.py",
        "status_note": "derived from MPC run.out logs at year done: 1, not from the paper",
    },
    {
        "exhibit": "Table 23",
        "kind": "table",
        "description": "Theta posterior quantiles",
        "output_pattern": "output/tables/theta_percentiles_1043.csv",
        "program": "python pysrc/sampling/baseline.py --sites 1043",
        "status_note": "",
    },
    {
        "exhibit": "Table 24",
        "kind": "table",
        "description": "Gamma posterior quantiles",
        "output_pattern": "output/tables/gamma_percentiles_1043.csv",
        "program": "python pysrc/sampling/baseline.py --sites 1043",
        "status_note": "",
    },
    {
        "exhibit": "Table 25",
        "kind": "table",
        "description": "Sigma posterior quantiles",
        "output_pattern": "output/tables/sigma_percentiles_1043.csv",
        "program": "python pysrc/sampling/baseline.py --sites 1043",
        "status_note": "",
    },
]


def _split_patterns(patterns: str) -> list[str]:
    return [p for p in patterns.split("|") if p]


def _is_usable_output(path: Path) -> bool:
    if path.name.startswith("._"):
        return False
    if not path.exists() or path.stat().st_size == 0:
        return False
    if path.suffix.lower() == ".csv":
        try:
            data = pd.read_csv(path)
        except pd.errors.EmptyDataError:
            return False
        return len(data.columns) > 0 and not data.empty
    return path.is_file()


def _matches(root: Path, pattern: str) -> list[Path]:
    path = root / pattern
    if any(token in pattern for token in ["*", "?", "["]):
        return sorted(p for p in root.glob(pattern) if _is_usable_output(p))
    return [path] if _is_usable_output(path) else []


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _manifest_records(figure_inputs: pd.DataFrame | None = None) -> list[dict[str, str]]:
    table_records = [record for record in EXHIBITS if record["kind"] == "table"]
    if figure_inputs is None or figure_inputs.empty:
        figure_records = [record for record in EXHIBITS if record["kind"] == "figure"]
        return figure_records + table_records

    figure_defaults = {
        record["exhibit"]: record for record in EXHIBITS if record["kind"] == "figure"
    }
    figure_records: list[dict[str, str]] = []
    sorted_inputs = figure_inputs.sort_values(
        ["figure_number", "paper_include_path"],
        kind="stable",
    )
    for figure_number, group in sorted_inputs.groupby("figure_number", sort=True):
        exhibit = f"Figure {int(float(figure_number))}"
        default = figure_defaults.get(exhibit, {})
        include_paths = _ordered_unique(
            [str(value) for value in group["paper_include_path"].tolist()]
        )
        figure_records.append(
            {
                "exhibit": exhibit,
                "kind": "figure",
                "description": default.get(
                    "description", "Paper TeX includegraphics inputs"
                ),
                "output_pattern": "|".join(include_paths),
                "program": default.get("program", ""),
                "status_note": default.get(
                    "status_note",
                    "figure list read from replication/paper_figure_inputs.csv",
                ),
            }
        )
    return figure_records + table_records


def write_manifest(
    path: Path,
    figure_inputs: pd.DataFrame | None = None,
) -> pd.DataFrame:
    df = pd.DataFrame(_manifest_records(figure_inputs))
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return df


def _figure_missing_row(
    record: dict[str, object],
    root: Path,
    figure_inputs: pd.DataFrame,
) -> dict[str, object]:
    group = figure_inputs[figure_inputs["exhibit"] == record["exhibit"]]
    matched: list[str] = []
    missing: list[str] = []
    for item in group.to_dict("records"):
        source = resolve_generated_figure(root, str(item["source_basename"]))
        if source is not None and _is_usable_output(source):
            matched.append(str(source.relative_to(root)))
        else:
            missing.append(str(item["paper_include_path"]))
    return {
        "exhibit": record["exhibit"],
        "kind": record["kind"],
        "status": "complete" if not missing and not group.empty else "missing",
        "missing_patterns": "|".join(_ordered_unique(missing)),
        "matched_files": "|".join(_ordered_unique(matched)),
        "program": record["program"],
        "status_note": record.get("status_note", ""),
    }


def write_missing_summary(
    manifest: pd.DataFrame,
    root: Path,
    path: Path,
    figure_inputs: pd.DataFrame | None = None,
) -> pd.DataFrame:
    rows = []
    for record in manifest.to_dict("records"):
        if (
            record["kind"] == "figure"
            and figure_inputs is not None
            and not figure_inputs.empty
        ):
            rows.append(_figure_missing_row(record, root, figure_inputs))
            continue

        patterns = _split_patterns(record["output_pattern"])
        matched = []
        missing = []
        for pattern in patterns:
            found = _matches(root, pattern)
            if found:
                matched.extend(str(p.relative_to(root)) for p in found)
            else:
                missing.append(pattern)
        rows.append(
            {
                "exhibit": record["exhibit"],
                "kind": record["kind"],
                "status": "complete" if patterns and not missing else "missing",
                "missing_patterns": "|".join(missing),
                "matched_files": "|".join(matched),
                "program": record["program"],
                "status_note": record.get("status_note", ""),
            }
        )
    df = pd.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return df


def _latex_rows(path: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in path.read_text(errors="ignore").splitlines():
        clean = line.strip()
        if not clean or clean.startswith("\\") or "&" not in clean:
            continue
        clean = re.sub(r"\\\\.*$", "", clean)
        cells = [cell.strip().strip("{}") for cell in clean.split("&")]
        rows.append(cells)
    return rows


def collect_output_numbers(
    root: Path,
    carbon_price_path: Path,
    mpc_probability_path: Path,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    if carbon_price_path.exists():
        prices = pd.read_csv(carbon_price_path)
        for idx, row in prices.iterrows():
            xi = normalize_xi(row["xi"])
            rows.append(
                {
                    "number_id": f"carbon_price_{idx+1}",
                    "source_file": str(carbon_price_path.relative_to(root)),
                    "source_type": "derived_carbon_price",
                    "row": idx + 1,
                    "column": "pee",
                    "value": row["pee"],
                    "context": row.get("context", ""),
                    "label": f"{row.get('context', '')} {row.get('model', '')} xi={xi_for_label(xi)}",
                }
            )

    if mpc_probability_path.exists():
        probabilities = pd.read_csv(mpc_probability_path)
        for idx, row in probabilities.iterrows():
            xi = normalize_xi(row["xi"])
            b_value = float(row["b"])
            b_label = int(b_value) if b_value.is_integer() else b_value
            source_file = row.get("source_file") or str(
                mpc_probability_path.relative_to(root)
            )
            for column in ["prob_from_low_to_low", "prob_from_high_to_high"]:
                rows.append(
                    {
                        "number_id": f"mpc_transition_{idx+1}_{column}",
                        "source_file": source_file,
                        "source_type": "mpc_run_log_transition_probability",
                        "row": idx + 1,
                        "column": column,
                        "value": row[column],
                        "context": row.get("context", ""),
                        "label": (
                            f"b={b_label} {row.get('model', '')} "
                            f"xi={xi_for_label(xi)} pe={row.get('pe', '')} "
                            f"mc={row.get('mc', '')}"
                        ),
                    }
                )

    for folder in [root / "output" / "tables", root / "output" / "mpc"]:
        if not folder.exists():
            continue
        for tex_path in sorted(p for p in folder.glob("*.tex") if _is_usable_output(p)):
            for row_index, cells in enumerate(_latex_rows(tex_path), start=1):
                for col_index, value in enumerate(cells, start=1):
                    rows.append(
                        {
                            "number_id": f"{tex_path.stem}_r{row_index}_c{col_index}",
                            "source_file": str(tex_path.relative_to(root)),
                            "source_type": "latex_table_cell",
                            "row": row_index,
                            "column": col_index,
                            "value": value,
                            "context": "",
                            "label": "",
                        }
                    )
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build replication manifest and extract reported numbers from generated outputs. "
            "This script never reads values from the manuscript PDF."
        )
    )
    parser.add_argument("--root", type=Path, default=get_path())
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=get_path("replication", "exhibit_manifest.csv"),
    )
    parser.add_argument(
        "--numbers-out",
        type=Path,
        default=get_path("replication", "paper_numbers.csv"),
    )
    parser.add_argument(
        "--missing-out",
        type=Path,
        default=get_path("replication", "paper_numbers_missing_summary.csv"),
    )
    parser.add_argument("--carbon-prices", type=Path, default=CARBON_PRICE_FILE)
    parser.add_argument(
        "--mpc-probabilities",
        type=Path,
        default=get_path("replication", "derived", "mpc_transition_probabilities.csv"),
    )
    parser.add_argument(
        "--paper-tex",
        type=Path,
        default=DEFAULT_PAPER_TEX,
        help=(
            "Optional manuscript TeX file for refreshing replication/paper_figure_inputs.csv. "
            "Normal replication uses the repo-internal cached CSV."
        ),
    )
    parser.add_argument(
        "--figure-inputs-out",
        type=Path,
        default=PAPER_FIGURE_INPUTS_FILE,
    )
    args = parser.parse_args()

    figure_inputs = read_or_build_paper_figure_inputs(
        args.paper_tex,
        args.figure_inputs_out,
    )
    manifest = write_manifest(args.manifest_out, figure_inputs)
    missing = write_missing_summary(
        manifest,
        args.root,
        args.missing_out,
        figure_inputs,
    )
    numbers = collect_output_numbers(
        args.root,
        args.carbon_prices,
        args.mpc_probabilities,
    )
    args.numbers_out.parent.mkdir(parents=True, exist_ok=True)
    numbers.to_csv(args.numbers_out, index=False, quoting=csv.QUOTE_MINIMAL)

    print(f"Wrote manifest: {args.manifest_out}")
    print(f"Wrote output-derived numbers: {args.numbers_out}")
    print(f"Wrote missing-output summary: {args.missing_out}")
    print(f"Complete exhibits: {(missing['status'] == 'complete').sum()} / {len(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
