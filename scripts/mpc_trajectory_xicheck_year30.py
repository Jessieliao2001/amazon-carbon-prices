import numpy as np
import os
import pandas as pd
from pysrc.services.file_service import get_path
from pysrc.services.data_service import load_site_data

solver = "gurobi"
num_sites = 78

xi = 0.5
pe = 6.9
pa = 41.1

simulation_ids = range(1, 51)

baseline_year = 30
search_end_year = 50

# 这里的 TOL 是 zper 的容忍误差，单位是 percentage point
TOL = 1e-10

(zbar, _, _) = load_site_data(num_sites)
zbar = np.asarray(zbar)


def read_z(result_directory):
    Z = np.loadtxt(os.path.join(result_directory, "Z.txt"), delimiter=",")
    return Z / 1e2


def get_result_directory(mc_id):
    return (
        str(get_path("output"))
        + f"/optimization/mpc_worstcase/{solver}/{num_sites}sites/xi_{xi}/pa_{pa}/"
        + f"pe_{pe}/mc_{mc_id}/unconstrained"
    )


site_records = []
summary_records = []

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

    if baseline_year >= n_years:
        print(f"mc_{mc_id}: baseline year {baseline_year} is not available. Z has shape {Z.shape}")
        continue

    if search_end_year is None:
        this_end_year = n_years - 1
    else:
        this_end_year = min(search_end_year, n_years - 1)

    if baseline_year >= this_end_year:
        print(
            f"mc_{mc_id}: no years after baseline year {baseline_year} available. "
            f"Z has shape {Z.shape}"
        )
        continue

    # 每个 site 的 zper
    # Zper[t, i] = Z[t, i] / zbar[i] * 100
    Zper = (Z / zbar.reshape(1, -1)) * 100

    # year 30 的 zper，作为 baseline
    zper_baseline = Zper[baseline_year, :]

    # 只检查 year 31 到 search_end_year
    years_after = np.arange(baseline_year + 1, this_end_year + 1)

    # compare_matrix[k, i] = True 表示 site i 在某个 year 的 zper 低于 year 30
    compare_matrix = Zper[years_after, :] < zper_baseline.reshape(1, -1) - TOL

    # 每个 site 在 year 30 以后是否曾经低于 year 30
    has_drop_after_30_vs_30 = np.any(compare_matrix, axis=0)

    first_below_30_year = np.full(n_sites, np.nan)
    first_below_30_amount = np.full(n_sites, np.nan)
    min_zper_after_30 = np.min(Zper[years_after, :], axis=0)
    min_zper_after_30_year = years_after[np.argmin(Zper[years_after, :], axis=0)]
    total_change_30_to_end = Zper[this_end_year, :] - zper_baseline

    if np.any(has_drop_after_30_vs_30):
        first_idx_sub = np.argmax(compare_matrix[:, has_drop_after_30_vs_30], axis=0)
        first_year = years_after[first_idx_sub]

        site_indices_with_drop = np.where(has_drop_after_30_vs_30)[0]

        first_below_30_year[has_drop_after_30_vs_30] = first_year
        first_below_30_amount[has_drop_after_30_vs_30] = (
            Zper[first_year, site_indices_with_drop]
            - zper_baseline[site_indices_with_drop]
        )

    for site_idx in range(n_sites):
        site_records.append({
            "mc": mc_id,
            "site_idx_python": site_idx,
            "site_id": site_idx + 1,

            "zper_year30": zper_baseline[site_idx],

            "has_zper_drop_after_30_vs_30": bool(has_drop_after_30_vs_30[site_idx]),
            "first_year_below_year30_zper": first_below_30_year[site_idx],
            "first_drop_amount_vs_year30": first_below_30_amount[site_idx],

            "min_zper_after_30": min_zper_after_30[site_idx],
            "min_zper_after_30_year": min_zper_after_30_year[site_idx],
            "min_drop_amount_vs_year30": min_zper_after_30[site_idx] - zper_baseline[site_idx],

            f"change_30_to_{this_end_year}": total_change_30_to_end[site_idx],
        })

    num_drop_after_30_vs_30 = np.sum(has_drop_after_30_vs_30)

    summary_records.append({
        "mc": mc_id,
        "num_sites": n_sites,

        "num_sites_zper_below_year30_after30": num_drop_after_30_vs_30,
        "fraction_sites_zper_below_year30_after30": num_drop_after_30_vs_30 / n_sites,

        "num_sites_not_below_year30_after30": n_sites - num_drop_after_30_vs_30,

        "avg_zper_year30": np.mean(zper_baseline),
        f"avg_zper_year{this_end_year}": np.mean(Zper[this_end_year, :]),
        f"avg_change_30_to_{this_end_year}": np.mean(total_change_30_to_end),

        "aggregate_zper_year30": np.sum(Z[baseline_year, :]) / np.sum(zbar) * 100,
        f"aggregate_zper_year{this_end_year}": np.sum(Z[this_end_year, :]) / np.sum(zbar) * 100,
        f"aggregate_change_30_to_{this_end_year}": (
            np.sum(Z[this_end_year, :]) / np.sum(zbar) * 100
            - np.sum(Z[baseline_year, :]) / np.sum(zbar) * 100
        ),
    })


df_sites = pd.DataFrame(site_records)
df_summary = pd.DataFrame(summary_records)

print("\n=== Site-level: zper below year 30 after year 30 ===")
print(df_sites.to_string(index=False))

print("\n=== Summary by simulation ===")
print(df_summary.to_string(index=False))

output_folder = str(get_path("output"))

site_csv_path = os.path.join(
    output_folder,
    f"zper_below_year30_by_site_xi_{xi}_pe_{pe}.csv"
)

summary_csv_path = os.path.join(
    output_folder,
    f"zper_below_year30_summary_xi_{xi}_pe_{pe}.csv"
)

df_sites.to_csv(site_csv_path, index=False)
df_summary.to_csv(summary_csv_path, index=False)

print(f"\nSaved site-level results to: {site_csv_path}")
print(f"Saved summary results to: {summary_csv_path}")