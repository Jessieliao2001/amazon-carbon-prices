#!/usr/bin/env python3
"""
Reproduce Figure 1: emissions per capita vs. GDP per capita PPP, with
China, India, European Union, United States, and Brazilian Amazon highlighted.

Run from the root of the emissionKuznets_worldbank folder:
    python replicate_figure1.py

The script uses the World Bank WDI CSVs already in input/ and the country
metadata in documentation/. It writes a PNG, a PDF, and the plotted CSV to
output/results/other/.
"""

from __future__ import annotations

import argparse
import glob
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import NullLocator


YEAR = "2018"

# Brazilian Amazon values from Fatos da Amazonia 2021 / Juliano correspondence.
# GDP: R$ 22.3k, 66.4% of Brazil's GDP per capita. For the plot's PPP scale,
# the original R-history used roughly 9968 current international dollars.
AMAZON_GDP_PC_PPP_2018 = 9968.0
# Emissions: 1,137.13 MtCO2e / 28.1 million people = about 40.5; correspondence
# rounds to 40.6 tCO2e per capita.
AMAZON_EMISSIONS_PC_2018 = 40.6

HIGHLIGHTS = {
    "CHN": "C",
    "IND": "I",
    "EUU": "E",
    "USA": "U",
}


def one_match(pattern: str) -> Path:
    matches = sorted(glob.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No file matched: {pattern}")
    return Path(matches[0])


def read_wdi_csv(path: Path, value_name: str) -> pd.DataFrame:
    raw = pd.read_csv(path, skiprows=4)
    out = raw[["Country Name", "Country Code", YEAR]].copy()
    out = out.rename(columns={YEAR: value_name})
    out[value_name] = pd.to_numeric(out[value_name], errors="coerce")
    return out


def build_plot_data(base_dir: Path) -> pd.DataFrame:
    input_dir = base_dir / "input"
    doc_dir = base_dir / "documentation"

    gdp_file = one_match(str(input_dir / "API_NY.GDP.PCAP.PP.CD*.csv"))
    co2_file = one_match(str(input_dir / "API_EN.ATM.CO2E.PC*.csv"))
    metadata_file = one_match(str(doc_dir / "Metadata_Country_API_NY.GDP.PCAP.PP.CD*.csv"))

    gdp = read_wdi_csv(gdp_file, "gdp_pc_ppp_2018")
    co2 = read_wdi_csv(co2_file, "emissions_pc_2018")
    meta = pd.read_csv(metadata_file)[["Country Code", "Region"]]

    df = gdp.merge(co2[["Country Code", "emissions_pc_2018"]], on="Country Code", how="inner")
    df = df.merge(meta, on="Country Code", how="left")

    # Keep World Bank country/territory observations and add the EU aggregate,
    # matching the caption: countries in 2018 except for the European Union and
    # the Brazilian Amazon.
    is_country_or_territory = df["Region"].notna() & (df["Region"].astype(str).str.len() > 0)
    is_eu = df["Country Code"].eq("EUU")
    df = df.loc[is_country_or_territory | is_eu].copy()

    df = df[(df["gdp_pc_ppp_2018"] > 0) & (df["emissions_pc_2018"] > 0)].copy()
    df["gdp_pc_ppp_2018_100k"] = df["gdp_pc_ppp_2018"] / 100000.0
    df["plot_group"] = "World Bank country/territory or EU"

    amazon = pd.DataFrame(
        [
            {
                "Country Name": "Brazilian Amazon",
                "Country Code": "AMAZON",
                "gdp_pc_ppp_2018": AMAZON_GDP_PC_PPP_2018,
                "emissions_pc_2018": AMAZON_EMISSIONS_PC_2018,
                "Region": "Brazilian Amazon",
                "gdp_pc_ppp_2018_100k": AMAZON_GDP_PC_PPP_2018 / 100000.0,
                "plot_group": "Brazilian Amazon",
            }
        ]
    )
    return pd.concat([df, amazon], ignore_index=True)


def make_figure(plot_data: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    df = plot_data[plot_data["Country Code"].ne("AMAZON")].copy()
    amazon = plot_data[plot_data["Country Code"].eq("AMAZON")].iloc[0]

    fig, ax = plt.subplots(figsize=(8, 6), dpi=300)

    ax.scatter(
        df["gdp_pc_ppp_2018_100k"],
        df["emissions_pc_2018"],
        s=13,
        c="black",
        edgecolors="none",
        zorder=1,
    )

    # Highlight China, India, EU, and US.
    for code, label in HIGHLIGHTS.items():
        row = df[df["Country Code"].eq(code)].iloc[0]
        x = row["gdp_pc_ppp_2018_100k"]
        y = row["emissions_pc_2018"]
        ax.scatter([x], [y], s=18, c="red", edgecolors="none", zorder=3)
        ax.text(
            x * 1.035,
            y,
            label,
            color="red",
            fontsize=10,
            fontweight="bold",
            ha="left",
            va="center",
            zorder=4,
        )

    # Highlight Brazilian Amazon.
    ax.scatter(
        [amazon["gdp_pc_ppp_2018_100k"]],
        [amazon["emissions_pc_2018"]],
        s=18,
        c="green",
        edgecolors="none",
        zorder=3,
    )
    ax.text(
        amazon["gdp_pc_ppp_2018_100k"] * 1.035,
        amazon["emissions_pc_2018"],
        "Amazon",
        color="green",
        fontsize=10,
        fontweight="bold",
        ha="left",
        va="center",
        zorder=4,
    )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(0.006, 1.6)
    ax.set_ylim(0.02, 60)

    ax.set_xticks([0.01, 0.10, 1.00])
    ax.set_xticklabels(["0.01", "0.10", "1.00"])
    ax.set_yticks([0.1, 1.0, 10.0])
    ax.set_yticklabels(["0.1", "1.0", "10.0"])
    ax.xaxis.set_minor_locator(NullLocator())
    ax.yaxis.set_minor_locator(NullLocator())

    ax.set_xlabel("GDP per capita PPP in 2018 (100,000 int. dollars, log scale)", fontsize=13)
    ax.set_ylabel("Emission per capita in 2018 (metric tons CO2e, log scale)", fontsize=13)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="both", which="major", labelsize=10, length=3, width=0.8)

    fig.subplots_adjust(left=0.14, bottom=0.14, right=0.98, top=0.96)
    fig.savefig(output_dir / "figure1_replicated.png", dpi=300)
    fig.savefig(output_dir / "figure1_replicated.pdf")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Path to the figure1_replication folder.",
    )
    args = parser.parse_args()

    base_dir = args.base_dir.resolve()
    output_dir = base_dir / "output" / "results" / "other"
    plot_data = build_plot_data(base_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    plot_data.to_csv(output_dir / "figure1_source_data.csv", index=False)
    make_figure(plot_data, output_dir)

    print(f"Wrote: {output_dir / 'figure1_replicated.png'}")
    print(f"Wrote: {output_dir / 'figure1_replicated.pdf'}")
    print(f"Wrote: {output_dir / 'figure1_source_data.csv'}")


if __name__ == "__main__":
    main()
