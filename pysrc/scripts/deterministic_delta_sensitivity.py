import argparse
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

cache_root = Path(tempfile.gettempdir()) / "amazon_carbon_prices_cache"
(cache_root / "matplotlib").mkdir(parents=True, exist_ok=True)
(cache_root / "xdg").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(cache_root / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(cache_root / "xdg"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pysrc.optimization import PlannerSolution, solve_planner_problem
from pysrc.replication.parameters import CarbonPriceKey, carbon_price
from pysrc.services.data_service import (
    load_price_data,
    load_productivity_params,
    load_site_data,
    load_site_data_1995,
)
from pysrc.services.file_service import get_path


@dataclass(frozen=True)
class TrajectoryMetrics:
    z_share_pct: np.ndarray
    capture_gt: np.ndarray


@dataclass(frozen=True)
class CarbonPriceSearch:
    pee: float
    metric: float
    candidates: pd.DataFrame


def delta_slug(delta: float) -> str:
    return f"delta_{delta:g}".replace("-", "m").replace(".", "p")


def format_number(value: float) -> str:
    return f"{value:g}"


def solution_dir(
    *,
    outputs_root: Path,
    delta: float,
    solver: str,
    sites: int,
    pa: float,
    pe: float,
) -> Path:
    return (
        outputs_root
        / delta_slug(delta)
        / "optimization"
        / "det"
        / solver
        / f"{sites}sites"
        / f"pa_{format_number(pa)}"
        / f"pe_{format_number(pe)}"
    )


def figures_dir(*, outputs_root: Path, delta: float) -> Path:
    return outputs_root / delta_slug(delta) / "figures"


def save_solution(solution: PlannerSolution, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    np.savetxt(output_dir / "Z.txt", solution.Z, delimiter=",")
    np.savetxt(output_dir / "X.txt", solution.X, delimiter=",")
    np.savetxt(output_dir / "U.txt", solution.U, delimiter=",")
    np.savetxt(output_dir / "V.txt", solution.V, delimiter=",")


def price_grid(low: float, high: float, step: float) -> np.ndarray:
    if step <= 0:
        raise ValueError("--price-step must be positive.")
    if high < low:
        raise ValueError("--price-high must be greater than or equal to --price-low.")
    count = int(np.floor((high - low) / step + 0.5)) + 1
    values = low + step * np.arange(count)
    return np.round(values, 10)


def deterministic_shadow_price_ratio(
    *,
    sites: int,
    pe: float,
    pa: float,
    delta: float,
    solver: str,
    time_horizon: int,
) -> float:
    if time_horizon < 13:
        raise ValueError("--price-time-horizon must be at least 13.")
    (
        zbar_1995,
        z_1995,
        forest_area_1995,
        z_2008,
        theta,
        gamma,
    ) = load_site_data_1995(sites)
    pa_list = load_price_data()
    if len(pa_list) >= time_horizon:
        price_cattle = pa_list[:time_horizon]
    else:
        price_cattle = np.concatenate((pa_list, np.full(time_horizon - len(pa_list), pa)))
    x0_vals_1995 = gamma * forest_area_1995
    solution = solve_planner_problem(
        time_horizon=time_horizon,
        theta=theta,
        gamma=gamma,
        x0=x0_vals_1995,
        zbar=zbar_1995,
        z0=z_1995,
        price_emissions=pe,
        price_cattle=price_cattle,
        delta=delta,
        solver=solver,
    )
    z_2008_agg = np.sum(z_2008) / 1e9
    return (np.sum(solution.Z[13]) - z_2008_agg) / z_2008_agg


def search_deterministic_carbon_price(
    *,
    sites: int,
    pa: float,
    delta: float,
    solver: str,
    price_low: float,
    price_high: float,
    price_step: float,
    time_horizon: int,
) -> CarbonPriceSearch:
    rows = []
    for pe in price_grid(price_low, price_high, price_step):
        print(
            "Solving deterministic shadow price search: "
            f"sites={sites}, pe={pe:g}, delta={delta:g}"
        )
        metric = deterministic_shadow_price_ratio(
            sites=sites,
            pe=float(pe),
            pa=pa,
            delta=delta,
            solver=solver,
            time_horizon=time_horizon,
        )
        rows.append(
            {
                "sites": sites,
                "delta": delta,
                "pee": float(pe),
                "metric": metric,
                "abs_metric": abs(metric),
            }
        )
    candidates = pd.DataFrame(rows)
    best = candidates.sort_values(["abs_metric", "pee"], ascending=[True, True]).iloc[0]
    return CarbonPriceSearch(
        pee=float(best["pee"]),
        metric=float(best["metric"]),
        candidates=candidates,
    )


def solve_deterministic_trajectory(
    *,
    sites: int,
    pe: float,
    pa: float,
    delta: float,
    solver: str,
    time_horizon: int,
) -> PlannerSolution:
    zbar, z0, forest_area = load_site_data(sites)
    theta, gamma = load_productivity_params(sites)
    x0 = gamma * forest_area
    return solve_planner_problem(
        time_horizon=time_horizon,
        theta=theta,
        gamma=gamma,
        x0=x0,
        zbar=zbar,
        z0=z0,
        price_emissions=pe,
        price_cattle=pa,
        delta=delta,
        solver=solver,
    )


def trajectory_metrics(solution: PlannerSolution, zbar: np.ndarray, years: int) -> TrajectoryMetrics:
    last_index = min(years, len(solution.Z) - 1)
    z = solution.Z[: last_index + 1]
    x = solution.X[: last_index + 1]
    z_share_pct = np.sum(z, axis=1) / np.sum(zbar) * 100
    capture_gt = np.sum(x, axis=1) - np.sum(x[0])
    return TrajectoryMetrics(z_share_pct=z_share_pct, capture_gt=capture_gt)


def plot_land_allocation_figures(
    *,
    sites: int,
    pee: float,
    delta: float,
    outputs_root: Path,
    zbar: np.ndarray,
    years: int,
    sensitivity_solutions: dict[float, PlannerSolution],
) -> None:
    output_dir = figures_dir(outputs_root=outputs_root, delta=delta)
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_transfers = [transfer for transfer in [0.0, 15.0, 25.0] if transfer in sensitivity_solutions]
    if not plot_transfers:
        print(f"No transfer levels available for land-allocation figures at delta={delta:g}.")
        return

    colors = {0.0: "red", 15.0: "green", 25.0: "blue"}
    labels = {transfer: format_number(transfer) for transfer in plot_transfers}
    metrics = {
        transfer: trajectory_metrics(solution, zbar, years)
        for transfer, solution in sensitivity_solutions.items()
    }

    plt.figure(figsize=(10, 6))
    plt.plot([], [], " ", label=f"$p^{{ee}}$={format_number(pee)}       $b$")
    for transfer in plot_transfers:
        time = list(range(len(metrics[transfer].z_share_pct)))
        plt.plot(
            time,
            metrics[transfer].z_share_pct,
            label=labels[transfer],
            linewidth=4,
            color=colors.get(transfer),
        )
    plt.xlabel("years", fontsize=16)
    plt.ylabel("Z(%)", fontsize=16)
    plt.xlim(0, max(time) + 2)
    plt.yticks([0, 5, 10, 15, 20], ["0", "5", "10", "15", "20"])
    plt.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.15),
        ncol=5,
        frameon=False,
        fontsize=16,
    )
    plt.savefig(
        output_dir / f"pred_zshare_{sites}_sites_det_{delta_slug(delta)}.png",
        format="png",
        bbox_inches="tight",
    )
    plt.close()

    plt.figure(figsize=(10, 6))
    ax = plt.gca()
    plt.plot([], [], " ", label=f"$p^{{ee}}$={format_number(pee)}       $b$")
    for transfer in plot_transfers:
        time = list(range(len(metrics[transfer].capture_gt)))
        plt.plot(
            time,
            metrics[transfer].capture_gt,
            label=labels[transfer],
            linewidth=4,
            color=colors.get(transfer),
        )
    ax.spines["bottom"].set_position(("data", 0))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.xaxis.set_ticks_position("bottom")
    ax.yaxis.set_ticks_position("left")
    plt.xlabel("years", fontsize=18)
    plt.ylabel("Capture (billions CO2e)", fontsize=18)
    plt.xlim(0, max(time) + 2)
    ax.set_xticks([10, 20, 30, 40, 50])
    plt.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.15),
        ncol=5,
        frameon=False,
        fontsize=18,
    )
    plt.savefig(
        output_dir / f"plot_pred_x_{sites}_sites_det_{delta_slug(delta)}.png",
        format="png",
        bbox_inches="tight",
    )
    plt.close()


def plot_net_transfers_figure(
    *,
    sites: int,
    delta: float,
    outputs_root: Path,
    sensitivity_solutions: dict[float, PlannerSolution],
    kappa: float = 2.094215255,
) -> None:
    output_dir = figures_dir(outputs_root=outputs_root, delta=delta)
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_transfers = [transfer for transfer in [15.0, 25.0] if transfer in sensitivity_solutions]
    if not plot_transfers:
        print(f"No transfer levels available for net-transfer figure at delta={delta:g}.")
        return

    colors = {15.0: "blue", 25.0: "red"}
    plt.figure(figsize=(10, 6))
    for transfer in plot_transfers:
        solution = sensitivity_solutions[transfer]
        x_dot = np.diff(solution.X, axis=0)
        transfers = -transfer * (kappa * solution.Z[1:] - x_dot).sum(axis=1)
        plt.plot(
            transfers[:50],
            label=f"b=${format_number(transfer)}",
            linewidth=4,
            color=colors.get(transfer),
        )
    plt.legend()
    plt.xlabel("years")
    plt.ylabel("Net Transfers ($ billion)")
    plt.savefig(
        output_dir / f"net_transfers_{sites}_sites_det_{delta_slug(delta)}.png",
        format="png",
        bbox_inches="tight",
    )
    plt.close()


def summarize_difference(
    *,
    sites: int,
    base_pee: float,
    sensitivity_pee: float,
    sensitivity_price_metric: float,
    transfer: float,
    base_delta: float,
    sensitivity_delta: float,
    years: int,
    base: TrajectoryMetrics,
    sensitivity: TrajectoryMetrics,
) -> dict[str, float]:
    z_diff = sensitivity.z_share_pct - base.z_share_pct
    capture_diff = sensitivity.capture_gt - base.capture_gt
    final_capture_base = base.capture_gt[-1]
    relative_capture_diff_pct = np.nan
    if final_capture_base != 0:
        relative_capture_diff_pct = capture_diff[-1] / final_capture_base * 100
    return {
        "sites": sites,
        "transfer": transfer,
        "base_delta": base_delta,
        "sensitivity_delta": sensitivity_delta,
        "base_pee": base_pee,
        "sensitivity_pee": sensitivity_pee,
        "sensitivity_price_metric": sensitivity_price_metric,
        "base_price_emissions": base_pee + transfer,
        "sensitivity_price_emissions": sensitivity_pee + transfer,
        "years_compared": years,
        "final_z_share_base_pct": base.z_share_pct[-1],
        "final_z_share_sensitivity_pct": sensitivity.z_share_pct[-1],
        "final_z_share_diff_pp": z_diff[-1],
        "max_abs_z_share_diff_pp": float(np.max(np.abs(z_diff))),
        "final_capture_base_gt": final_capture_base,
        "final_capture_sensitivity_gt": sensitivity.capture_gt[-1],
        "final_capture_diff_gt": capture_diff[-1],
        "max_abs_capture_diff_gt": float(np.max(np.abs(capture_diff))),
        "relative_final_capture_diff_pct": relative_capture_diff_pct,
    }


def trajectory_rows(
    *,
    sites: int,
    base_pee: float,
    sensitivity_pee: float,
    transfer: float,
    base_delta: float,
    sensitivity_delta: float,
    base: TrajectoryMetrics,
    sensitivity: TrajectoryMetrics,
) -> list[dict[str, float]]:
    z_diff = sensitivity.z_share_pct - base.z_share_pct
    capture_diff = sensitivity.capture_gt - base.capture_gt
    return [
        {
            "sites": sites,
            "transfer": transfer,
            "base_delta": base_delta,
            "sensitivity_delta": sensitivity_delta,
            "base_pee": base_pee,
            "sensitivity_pee": sensitivity_pee,
            "base_price_emissions": base_pee + transfer,
            "sensitivity_price_emissions": sensitivity_pee + transfer,
            "year": year,
            "base_z_share_pct": base.z_share_pct[year],
            "sensitivity_z_share_pct": sensitivity.z_share_pct[year],
            "diff_z_share_pp": z_diff[year],
            "base_capture_gt": base.capture_gt[year],
            "sensitivity_capture_gt": sensitivity.capture_gt[year],
            "diff_capture_gt": capture_diff[year],
        }
        for year in range(len(base.z_share_pct))
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare deterministic future trajectories under the baseline 2 percent "
            "discount rate and a 3 percent discount-rate sensitivity."
        )
    )
    parser.add_argument("--sites", type=int, nargs="+", default=[1043])
    parser.add_argument("--transfers", type=float, nargs="+", default=[0, 10, 15, 20, 25])
    parser.add_argument("--base-delta", type=float, default=0.02)
    parser.add_argument("--sensitivity-delta", type=float, default=0.03)
    parser.add_argument("--pa", type=float, default=41.11)
    parser.add_argument("--solver", default="gurobi")
    parser.add_argument("--time-horizon", type=int, default=200)
    parser.add_argument("--years", type=int, default=50)
    parser.add_argument("--price-low", type=float, default=5.0)
    parser.add_argument("--price-high", type=float, default=8.0)
    parser.add_argument("--price-step", type=float, default=0.1)
    parser.add_argument(
        "--price-time-horizon",
        type=int,
        default=200,
        help="Optimization horizon used to re-solve P^ee under the sensitivity delta.",
    )
    parser.add_argument(
        "--outputs-root",
        type=Path,
        default=get_path("output", "delta_sensitivity"),
        help="Root directory for delta-specific optimization outputs and figures.",
    )
    parser.add_argument(
        "--skip-figures",
        action="store_true",
        help="Only write the CSV sensitivity summaries.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=get_path("replication", "derived", "deterministic_delta_sensitivity.csv"),
    )
    parser.add_argument(
        "--trajectories-out",
        type=Path,
        default=get_path(
            "replication",
            "derived",
            "deterministic_delta_sensitivity_trajectories.csv",
        ),
    )
    parser.add_argument(
        "--prices-out",
        type=Path,
        default=get_path("replication", "derived", "deterministic_delta_sensitivity_prices.csv"),
    )
    args = parser.parse_args()

    if args.years > args.time_horizon:
        raise ValueError("--years cannot exceed --time-horizon.")

    summary_rows: list[dict[str, float]] = []
    all_trajectory_rows: list[dict[str, float]] = []
    all_price_rows: list[pd.DataFrame] = []
    solutions_for_figures: dict[int, tuple[float, np.ndarray, dict[float, PlannerSolution]]] = {}

    for sites in args.sites:
        zbar, _, _ = load_site_data(sites)
        base_pee = carbon_price(
            CarbonPriceKey(
                context="parameter_ambiguity",
                model="det",
                sites=sites,
                xi="inf",
            )
        )
        price_search = search_deterministic_carbon_price(
            sites=sites,
            pa=args.pa,
            delta=args.sensitivity_delta,
            solver=args.solver,
            price_low=args.price_low,
            price_high=args.price_high,
            price_step=args.price_step,
            time_horizon=args.price_time_horizon,
        )
        all_price_rows.append(price_search.candidates)
        sensitivity_pee = price_search.pee
        print(
            "Selected deterministic sensitivity carbon price: "
            f"sites={sites}, delta={args.sensitivity_delta:g}, "
            f"pee={sensitivity_pee:g}, metric={price_search.metric:g}"
        )
        for transfer in args.transfers:
            base_pe = base_pee + transfer
            sensitivity_pe = sensitivity_pee + transfer
            print(
                "Solving deterministic delta sensitivity: "
                f"sites={sites}, transfer={transfer:g}, "
                f"base_pe={base_pe:g}, sensitivity_pe={sensitivity_pe:g}, "
                f"delta={args.base_delta:g} vs {args.sensitivity_delta:g}"
            )
            base_solution = solve_deterministic_trajectory(
                sites=sites,
                pe=base_pe,
                pa=args.pa,
                delta=args.base_delta,
                solver=args.solver,
                time_horizon=args.time_horizon,
            )
            sensitivity_solution = solve_deterministic_trajectory(
                sites=sites,
                pe=sensitivity_pe,
                pa=args.pa,
                delta=args.sensitivity_delta,
                solver=args.solver,
                time_horizon=args.time_horizon,
            )
            save_solution(
                sensitivity_solution,
                solution_dir(
                    outputs_root=args.outputs_root,
                    delta=args.sensitivity_delta,
                    solver=args.solver,
                    sites=sites,
                    pa=args.pa,
                    pe=sensitivity_pe,
                ),
            )
            solutions_for_figures.setdefault(sites, (sensitivity_pee, zbar, {}))[2][float(transfer)] = (
                sensitivity_solution
            )
            base = trajectory_metrics(base_solution, zbar, args.years)
            sensitivity = trajectory_metrics(sensitivity_solution, zbar, args.years)
            summary_rows.append(
                summarize_difference(
                    sites=sites,
                    base_pee=base_pee,
                    sensitivity_pee=sensitivity_pee,
                    sensitivity_price_metric=price_search.metric,
                    transfer=transfer,
                    base_delta=args.base_delta,
                    sensitivity_delta=args.sensitivity_delta,
                    years=args.years,
                    base=base,
                    sensitivity=sensitivity,
                )
            )
            all_trajectory_rows.extend(
                trajectory_rows(
                    sites=sites,
                    base_pee=base_pee,
                    sensitivity_pee=sensitivity_pee,
                    transfer=transfer,
                    base_delta=args.base_delta,
                    sensitivity_delta=args.sensitivity_delta,
                    base=base,
                    sensitivity=sensitivity,
                )
            )

    if not args.skip_figures:
        for sites, (pee, zbar, sensitivity_solutions) in solutions_for_figures.items():
            plot_land_allocation_figures(
                sites=sites,
                pee=pee,
                delta=args.sensitivity_delta,
                outputs_root=args.outputs_root,
                zbar=zbar,
                years=args.years,
                sensitivity_solutions=sensitivity_solutions,
            )
            plot_net_transfers_figure(
                sites=sites,
                delta=args.sensitivity_delta,
                outputs_root=args.outputs_root,
                sensitivity_solutions=sensitivity_solutions,
            )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.trajectories_out.parent.mkdir(parents=True, exist_ok=True)
    args.prices_out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summary_rows).to_csv(args.out, index=False)
    pd.DataFrame(all_trajectory_rows).to_csv(args.trajectories_out, index=False)
    pd.concat(all_price_rows, ignore_index=True).to_csv(args.prices_out, index=False)

    print(f"Wrote {len(summary_rows)} summary rows to {args.out}")
    print(f"Wrote {len(all_trajectory_rows)} trajectory rows to {args.trajectories_out}")
    print(f"Wrote sensitivity carbon-price candidates to {args.prices_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
