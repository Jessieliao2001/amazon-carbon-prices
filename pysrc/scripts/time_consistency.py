"""
Run carrot-policy time-consistency checks for a user-supplied bf.
"""

import argparse
import csv
import os
import pickle

import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

from pysrc.analysis import value_decomposition
from pysrc.analysis.carrot_helper import compute_fund_balance, defection_years_by_tau
from pysrc.optimization import PlannerSolution, solve_planner_problem
from pysrc.services.data_service import load_productivity_params, load_site_data
from pysrc.services.file_service import get_path


# Command-line inputs, matching the style of shadow_price.py.
parser = argparse.ArgumentParser(description="carrot-policy time-consistency analysis")
parser.add_argument("--bf", type=float, required=True)
parser.add_argument("--sites", type=int, default=1043)
parser.add_argument("--tau-f-checks", type=str, default=None)
parser.add_argument("--no-plots", action="store_true")
parser.add_argument("--show-plots", action="store_true")
args = parser.parse_args()

bf = args.bf
num_sites = args.sites
make_plots = not args.no_plots
show_plots = args.show_plots

# Model parameters.
total_transfer = 25.0
b = total_transfer - bf
pee = 6.8
pa = 41.11
T = 200
h = 101
solver = "gurobi"


def default_tau_f_checks(bf_value):
    """Return the original notebook tau_f checks for common bf values."""
    if np.isclose(bf_value, 3.75):
        return [0, 15, 21]
    return [0]


def parse_tau_f_checks(text):
    """Parse a comma-separated tau_f string."""
    if text is None:
        return default_tau_f_checks(bf)

    values = [value.strip() for value in text.split(",") if value.strip()]
    if len(values) == 0:
        raise ValueError("tau-f-checks must contain at least one integer.")

    return [int(value) for value in values]


def format_number_for_filename(value):
    """Format numbers for stable folder and pickle names."""
    text = f"{value:.10g}"
    if "." in text:
        text = text.rstrip("0").rstrip(".").replace(".", "p")
    return text


def make_output_folders(bf_value):
    """Create output and figure folders using the project file service."""
    bf_tag = format_number_for_filename(bf_value)

    output_folder = (
        get_path("output")
        / "time_consistency"
        / f"bf_{bf_tag}"
    )

    figures_folder = (
        get_path("output")
        / "figures"
        / "time_consistency"
        / f"bf_{bf_tag}"
    )

    os.makedirs(output_folder, exist_ok=True)
    os.makedirs(figures_folder, exist_ok=True)

    return output_folder, figures_folder


def dump_pkl(path, obj):
    """Save an object as a pickle file."""
    os.makedirs(path.parent, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)


def load_pkl(path):
    """Load a pickle file."""
    with open(path, "rb") as f:
        return pickle.load(f)


def cache_paths_for_params(cache_dir, b_value, bf_value):
    """Return cache paths for one (b, bf) run."""
    tag = (
        f"T{T}_"
        f"b{format_number_for_filename(b_value)}_"
        f"bf{format_number_for_filename(bf_value)}"
    )

    return {
        "results_pkl": cache_dir / f"results_{tag}_new.pkl",
        "V_pkl": cache_dir / f"V_{tag}_new.pkl",
        "W_pkl": cache_dir / f"W_{tag}_new.pkl",
        "W_ckpt_pkl": cache_dir / f"W_ckpt_{tag}_new.pkl",
    }


def load_inputs(sitenum):
    """Load site data, productivity parameters, and initial carbon stock."""
    zbar_2017, z_2017, forest_area_2017 = load_site_data(sitenum)
    theta, gamma = load_productivity_params(sitenum)
    x0_vals = gamma * forest_area_2017

    return zbar_2017, z_2017, theta, gamma, x0_vals


def plot_group_map(sitenum, figures_dir):
    """Plot site groups from the calibration GeoJSON."""
    geojson_path = get_path("data") / "calibration" / f"gamma_fit_{sitenum}.geojson"
    gdf = gpd.read_file(geojson_path)

    unique_groups = sorted(gdf["id_group"].unique())
    colors = np.vstack(
        [
            plt.cm.tab20(np.linspace(0, 1, 20)),
            plt.cm.tab20b(np.linspace(0, 1, 20)),
            plt.cm.tab20c(np.linspace(0, 1, 20)),
            plt.cm.Set1(np.linspace(0, 1, 9)),
            plt.cm.Set2(np.linspace(0, 1, 9)),
        ]
    )

    rng = np.random.default_rng(42)
    color_ids = rng.permutation(len(colors))[: len(unique_groups)]
    color_map = {group: colors[color_ids[i]] for i, group in enumerate(unique_groups)}

    fig, ax = plt.subplots(figsize=(14, 10))
    for group in unique_groups:
        gdf[gdf["id_group"] == group].plot(
            ax=ax,
            color=color_map[group],
            linewidth=0.2,
            edgecolor="black",
        )

    legend_patches = [
        mpatches.Patch(color=color_map[group], label=f"Group {int(group)}")
        for group in unique_groups
    ]
    ax.legend(
        handles=legend_patches,
        title="id_group",
        bbox_to_anchor=(1.02, 1),
        loc="upper left",
        fontsize=9,
        title_fontsize=8,
        ncol=2,
    )

    ax.set_title(f"id_group ({sitenum} sites in {len(unique_groups)} groups)")
    ax.set_axis_off()
    fig.tight_layout()

    fig.savefig(figures_dir / "id_group_map.png", dpi=300, bbox_inches="tight")
    if show_plots:
        plt.show()
    plt.close(fig)


def plot_z100_map(results, sitenum, figures_dir):
    """Plot each site's share of aggregate z(100)."""
    z_100_percent = np.asarray(results.Z[100] / results.Z[100].sum()).flatten() * 100
    grid_path = get_path("data") / "calibration" / f"grid_{sitenum}_sites.geojson"

    gdf = gpd.read_file(grid_path)
    gdf["id"] = gdf["id"].astype(int)

    if len(z_100_percent) < gdf["id"].max():
        raise ValueError(
            f"z_100 has length {len(z_100_percent)}, "
            f"but max grid id is {gdf['id'].max()}."
        )

    gdf["z_100"] = gdf["id"].apply(lambda site_id: z_100_percent[site_id - 1])

    fig, ax = plt.subplots(figsize=(10, 8))
    gdf.plot(
        column="z_100",
        cmap="Blues",
        linewidth=0.2,
        edgecolor="black",
        legend=True,
        ax=ax,
        legend_kwds={"label": "z(100) (%)", "shrink": 0.7},
    )

    ax.set_title("z(100) / total z(100) (%) mapped across sites")
    ax.set_axis_off()
    fig.tight_layout()

    bf_tag = format_number_for_filename(bf)
    fig.savefig(figures_dir / f"z100_perc_map_bf{bf_tag}_new.png", dpi=300, bbox_inches="tight")
    if show_plots:
        plt.show()
    plt.close(fig)


def solve_or_load_cooperative_plan(cache_paths, theta, gamma, x0_vals, zbar_2017, z_2017):
    """Solve or load the cooperative planner problem."""
    results_path = cache_paths["results_pkl"]

    if results_path.exists():
        results = load_pkl(results_path)
        print(f"loaded results: {results_path}")
        return results

    results = solve_planner_problem(
        time_horizon=T + h,
        theta=theta,
        gamma=gamma,
        x0=x0_vals,
        zbar=zbar_2017,
        z0=z_2017,
        price_emissions=pee + b + bf,
        price_cattle=pa,
        solver=solver,
    )

    dump_pkl(results_path, results)
    print(f"solved and saved results: {results_path}")

    return results


def compute_or_load_continuation_values(cache_paths, theta, results):
    """Compute or load cooperative continuation values V[t]."""
    V_path = cache_paths["V_pkl"]

    if V_path.exists():
        V = load_pkl(V_path)
        print(f"loaded V: {V_path}")
        return V

    V = [
        value_decomposition(
            T=T,
            pee=pee,
            pa=pa,
            b=b + bf,
            theta=theta,
            solution=PlannerSolution(
                results.Z[t:],
                results.X[t:],
                results.U[t:],
                results.V[t:],
            ),
        )["total_PV"]
        for t in range(h)
    ]

    dump_pkl(V_path, V)
    print(f"computed and saved V: {V_path}")

    return V


def compute_or_load_defection_values(cache_paths, theta, gamma, zbar_2017, results):
    """Compute or load autarky defection values W[t]."""
    W_path = cache_paths["W_pkl"]
    checkpoint_path = cache_paths["W_ckpt_pkl"]

    if W_path.exists():
        W = load_pkl(W_path)
        print(f"loaded W: {W_path}")
        return W

    if checkpoint_path.exists():
        checkpoint = load_pkl(checkpoint_path)
        W = checkpoint["W"]
        start_t = len(W)
        print(f"resuming W computation from t={start_t}")
    else:
        W = []
        start_t = 0

    for t in range(start_t, h):
        defection_sol = solve_planner_problem(
            time_horizon=T,
            theta=theta,
            gamma=gamma,
            x0=results.X[t],
            zbar=zbar_2017,
            z0=results.Z[t],
            price_emissions=pee,
            price_cattle=pa,
            solver=solver,
        )

        W_t = value_decomposition(
            T=T,
            pee=pee,
            pa=pa,
            b=0,
            theta=theta,
            solution=defection_sol,
        )["total_PV"]

        W.append(W_t)
        dump_pkl(checkpoint_path, {"t_done": t, "W": W})

        if (t + 1) % 5 == 0:
            print(f"W progress: {t + 1}/{h}")

    dump_pkl(W_path, W)
    checkpoint_path.unlink(missing_ok=True)
    print(f"computed and saved W: {W_path}")

    return W


def print_defection_years(defection_map):
    """Print first defection year by tau_f."""
    for tau_f, first_defection_year in defection_map.items():
        if first_defection_year is None:
            print(f"tau_f={tau_f}: never defects")
        else:
            print(
                f"tau_f={tau_f}: first defect at year {first_defection_year} "
                f"(0-index), year {first_defection_year + 1} (1-index)"
            )


def print_tau_f_checks(results, V, W, tau_f_checks):
    """Print the original notebook tau_f checks."""
    print(f"bf = {bf}")
    print(f"V(0) = {V[0]:.6f}")
    print(f"V(100) = {V[100]:.6f}")
    print(f"W(100) = {W[100]:.6f}")

    for tau_f in tau_f_checks:
        B = compute_fund_balance(X=results.X, Z=results.Z, bf=bf, tau_f=tau_f)
        print(f"tau_f={tau_f}: B(100) = {B[100]:.6f}")
        print(f"  B(100) - W(100) = {B[100] - W[100]:.6f}")
        print(f"  V(100) - [W(100) - B(100)] = {V[100] - (W[100] - B[100]):.6f}")


def write_summary_csv(path, results, V, W, defection_map):
    """Write auditable in-text-number evidence for each tau_f."""
    rows = []
    for tau_f, first_defection_year in defection_map.items():
        B = compute_fund_balance(X=results.X, Z=results.Z, bf=bf, tau_f=tau_f)
        rows.append(
            {
                "sites": num_sites,
                "bf": bf,
                "b": b,
                "total_transfer": total_transfer,
                "pee": pee,
                "pa": pa,
                "tau_f": tau_f,
                "V_0": V[0],
                "V_100": V[100],
                "W_100": W[100],
                "B_100": B[100],
                "B_100_minus_W_100": B[100] - W[100],
                "V_100_minus_W_100_minus_B_100": V[100] - (W[100] - B[100]),
                "first_defection_year_zero_index": (
                    "" if first_defection_year is None else first_defection_year
                ),
                "first_defection_year_one_index": (
                    "" if first_defection_year is None else first_defection_year + 1
                ),
                "never_defects": first_defection_year is None,
            }
        )

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote summary CSV: {path}")


tau_f_checks = parse_tau_f_checks(args.tau_f_checks)
output_folder, figures_dir = make_output_folders(bf)
cache_paths = cache_paths_for_params(output_folder, b, bf)

zbar_2017, z_2017, theta, gamma, x0_vals = load_inputs(num_sites)

print(f"Loaded site grid: sitenum={num_sites}")
print(f"Scenario params: b={b}, bf={bf}, pee={pee}, pa={pa}")
print(f"Cooperative emissions price: {pee + b + bf}")

if make_plots:
    plot_group_map(num_sites, figures_dir)

results = solve_or_load_cooperative_plan(
    cache_paths,
    theta,
    gamma,
    x0_vals,
    zbar_2017,
    z_2017,
)

print(f"Solution shapes: Z{results.Z.shape}, X{results.X.shape}")

if make_plots:
    plot_z100_map(results, num_sites, figures_dir)

print(f"z(0) total = {results.Z[0].sum()}")
print(f"z(100) total = {results.Z[100].sum()}")
print(f"z(100) max = {results.Z[100].max()}")
print(f"z(100) mean = {results.Z[100].mean()}")

V = compute_or_load_continuation_values(cache_paths, theta, results)

print(f"Computed continuation values V (length: {len(V)})")
print(f"V[0] = ${V[0]:.2f} billion")
print(f"V[{h - 1}] = ${V[h - 1]:.2f} billion")

W = compute_or_load_defection_values(cache_paths, theta, gamma, zbar_2017, results)

print(f"Computed defection values W (length: {len(W)})")

print("\n" + "=" * 60)
print(f"Post-computations for b={b}, bf={bf}")

defection_map = defection_years_by_tau(
    X=results.X,
    Z=results.Z,
    V=V,
    W=W,
    bf=bf,
)

print_defection_years(defection_map)

never_defect_taus = [tau for tau, year in defection_map.items() if year is None]
print(f"Never-defect tau_f values: {never_defect_taus}")

print_tau_f_checks(results, V, W, tau_f_checks)
write_summary_csv(output_folder / "time_consistency_summary.csv", results, V, W, defection_map)
