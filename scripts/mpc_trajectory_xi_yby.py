import numpy as np
import os
import pandas as pd
from pysrc.services.file_service import get_path
from pysrc.services.data_service import load_site_data

import argparse
parser = argparse.ArgumentParser(description="parameter settings")
parser.add_argument("--xi",type=float,default=10000)
args = parser.parse_args()

solver = "gurobi"
num_sites = 78

xi = args.xi
pe = 6.9
pa = 41.1

simulation_ids = range(1, 51)
target_years = range(30, 51)
TOL = 1e-7

(zbar, _, _) = load_site_data(num_sites)
zbar = np.asarray(zbar)


def read_z(result_directory):
    Z = np.loadtxt(os.path.join(result_directory, "Z.txt"), delimiter=",")
    return Z / 1e2


def get_result_directory(mc_id):
    return (
        str(get_path("output"))
        + f"/optimization/mpc/{solver}/{num_sites}sites/xi_{xi}/pa_{pa}/"
        + f"pe_{pe}/mc_{mc_id}/unconstrained"
    )


summary_records = []
site_records = []

for mc_id in simulation_ids:
    result_directory = get_result_directory(mc_id)
    z_file = os.path.join(result_directory, "Z.txt")

    if not os.path.exists(z_file):
        print(f"Missing Z.txt for mc_{mc_id}: {z_file}")
        continue

    Z = read_z(result_directory)

    n_years, n_sites = Z.shape

    if n_sites != num_sites:
        print(f"Warning: mc_{mc_id} has {n_sites} sites, expected {num_sites}")

    if len(zbar) != n_sites:
        raise ValueError(f"zbar length is {len(zbar)}, but Z has {n_sites} sites")

    # 每个 site 的 zper
    Zper = (Z / np.sum(zbar)) * 100
    # Zper = (Z / zbar.reshape(1, -1)) * 100

    row = {
        "mc": mc_id,
        "num_sites": n_sites,
    }

    for year in target_years:
        prev_year = year - 1

        if year >= n_years:
            print(f"mc_{mc_id}: year {year} is not available. Z has shape {Z.shape}")
            row[f"drop_{year}_vs_{prev_year}_count"] = np.nan
            row[f"drop_{year}_vs_{prev_year}_fraction"] = np.nan
            continue

        # 计算每个 site 的 zper change
        zper_change = Zper[year, :] - Zper[prev_year, :]

        # 三类：下降、上升、不变
        decreased = zper_change < -TOL
        increased = zper_change > TOL
        unchanged = np.abs(zper_change) <= TOL

        drop_count = np.sum(decreased)
        rise_count = np.sum(increased)
        same_count = np.sum(unchanged)

        row[f"drop_{year}_vs_{prev_year}_count"] = drop_count
        row[f"drop_{year}_vs_{prev_year}_fraction"] = drop_count / n_sites

        row[f"rise_{year}_vs_{prev_year}_count"] = rise_count
        row[f"rise_{year}_vs_{prev_year}_fraction"] = rise_count / n_sites

        row[f"same_{year}_vs_{prev_year}_count"] = same_count
        row[f"same_{year}_vs_{prev_year}_fraction"] = same_count / n_sites

        row[f"sum_drop_change_{year}_vs_{prev_year}"] = np.sum(zper_change[decreased])
        row[f"sum_rise_change_{year}_vs_{prev_year}"] = np.sum(zper_change[increased])
        row[f"sum_same_change_{year}_vs_{prev_year}"] = np.sum(zper_change[unchanged])
        row[f"net_change_{year}_vs_{prev_year}"] = np.sum(zper_change)

        # 可选：site-level 记录，方便你之后看具体哪些 site 下降了
        for site_idx in range(n_sites):
            site_records.append({
                "mc": mc_id,
                "site_idx_python": site_idx,
                "site_id": site_idx + 1,
                "year": year,
                "prev_year": prev_year,
                "zper_prev_year": Zper[prev_year, site_idx],
                "zper_year": Zper[year, site_idx],
                "zper_change": Zper[year, site_idx] - Zper[prev_year, site_idx],
                "decreased": bool(decreased[site_idx]),
                "increased": bool(increased[site_idx]),
                "unchanged": bool(unchanged[site_idx]),
            })

    summary_records.append(row)


df_summary = pd.DataFrame(summary_records)
df_sites = pd.DataFrame(site_records)

print("\n=== Summary: zper decreases at target years ===")
print(df_summary.to_string(index=False))

mean_records = []

for year in target_years:
    prev_year = year - 1

    drop_fraction_col = f"drop_{year}_vs_{prev_year}_fraction"
    drop_count_col = f"drop_{year}_vs_{prev_year}_count"

    rise_fraction_col = f"rise_{year}_vs_{prev_year}_fraction"
    rise_count_col = f"rise_{year}_vs_{prev_year}_count"

    same_fraction_col = f"same_{year}_vs_{prev_year}_fraction"
    same_count_col = f"same_{year}_vs_{prev_year}_count"

    sum_drop_change_col = f"sum_drop_change_{year}_vs_{prev_year}"
    sum_rise_change_col = f"sum_rise_change_{year}_vs_{prev_year}"
    sum_same_change_col = f"sum_same_change_{year}_vs_{prev_year}"
    net_change_col = f"net_change_{year}_vs_{prev_year}"

    if drop_fraction_col not in df_summary.columns:
        print(f"Column not found: {drop_fraction_col}")
        continue

    mean_records.append({
        "year": year,
        "comparison": f"{year}_vs_{prev_year}",

        "mean_drop_count": df_summary[drop_count_col].mean(),
        "mean_drop_fraction": df_summary[drop_fraction_col].mean(),

        "mean_rise_count": df_summary[rise_count_col].mean(),
        "mean_rise_fraction": df_summary[rise_fraction_col].mean(),

        "mean_same_count": df_summary[same_count_col].mean(),
        "mean_same_fraction": df_summary[same_fraction_col].mean(),

        "mean_sum_drop_change": df_summary[sum_drop_change_col].mean(),
        "mean_sum_rise_change": df_summary[sum_rise_change_col].mean(),
        "mean_sum_same_change": df_summary[sum_same_change_col].mean(),
        "mean_net_change": df_summary[net_change_col].mean(),
    })
df_mean = pd.DataFrame(mean_records)

print("\n=== Average zper changes across simulations ===")
print(df_mean.to_string(
    index=False,
    formatters={
        "mean_drop_count": "{:.2f}".format,
        "mean_drop_fraction": "{:.6f}".format,

        "mean_rise_count": "{:.2f}".format,
        "mean_rise_fraction": "{:.6f}".format,

        "mean_same_count": "{:.2f}".format,
        "mean_same_fraction": "{:.6f}".format,

        "mean_sum_drop_change": "{:.8f}".format,
        "mean_sum_rise_change": "{:.8f}".format,
        "mean_sum_same_change": "{:.8f}".format,
        "mean_net_change": "{:.8f}".format,
    }
))

output_folder = str(get_path("output"))

summary_csv_path = os.path.join(
    output_folder,
    f"zper_drop_fraction_year30_40_50_xi_{xi}_pe_{pe}.csv"
)

site_csv_path = os.path.join(
    output_folder,
    f"zper_drop_sites_year30_40_50_xi_{xi}_pe_{pe}.csv"
)

df_summary.to_csv(summary_csv_path, index=False)
df_sites.to_csv(site_csv_path, index=False)

print(f"\nSaved summary results to: {summary_csv_path}")
print(f"Saved site-level results to: {site_csv_path}")