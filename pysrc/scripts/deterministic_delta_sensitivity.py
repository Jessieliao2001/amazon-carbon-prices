import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pysrc.optimization import PlannerSolution, solve_planner_problem
from pysrc.replication.parameters import CarbonPriceKey, carbon_price
from pysrc.services.data_service import load_productivity_params, load_site_data
from pysrc.services.file_service import get_path


@dataclass(frozen=True)
class TrajectoryMetrics:
    z_share_pct: np.ndarray
    capture_gt: np.ndarray


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


def summarize_difference(
    *,
    sites: int,
    pee: float,
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
        "pee": pee,
        "transfer": transfer,
        "price_emissions": pee + transfer,
        "base_delta": base_delta,
        "sensitivity_delta": sensitivity_delta,
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
    pee: float,
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
            "pee": pee,
            "transfer": transfer,
            "price_emissions": pee + transfer,
            "base_delta": base_delta,
            "sensitivity_delta": sensitivity_delta,
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
    args = parser.parse_args()

    if args.years > args.time_horizon:
        raise ValueError("--years cannot exceed --time-horizon.")

    summary_rows: list[dict[str, float]] = []
    all_trajectory_rows: list[dict[str, float]] = []

    for sites in args.sites:
        zbar, _, _ = load_site_data(sites)
        pee = carbon_price(
            CarbonPriceKey(
                context="parameter_ambiguity",
                model="det",
                sites=sites,
                xi="inf",
            )
        )
        for transfer in args.transfers:
            pe = pee + transfer
            print(
                "Solving deterministic delta sensitivity: "
                f"sites={sites}, transfer={transfer:g}, pe={pe:g}, "
                f"delta={args.base_delta:g} vs {args.sensitivity_delta:g}"
            )
            base_solution = solve_deterministic_trajectory(
                sites=sites,
                pe=pe,
                pa=args.pa,
                delta=args.base_delta,
                solver=args.solver,
                time_horizon=args.time_horizon,
            )
            sensitivity_solution = solve_deterministic_trajectory(
                sites=sites,
                pe=pe,
                pa=args.pa,
                delta=args.sensitivity_delta,
                solver=args.solver,
                time_horizon=args.time_horizon,
            )
            base = trajectory_metrics(base_solution, zbar, args.years)
            sensitivity = trajectory_metrics(sensitivity_solution, zbar, args.years)
            summary_rows.append(
                summarize_difference(
                    sites=sites,
                    pee=pee,
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
                    pee=pee,
                    transfer=transfer,
                    base_delta=args.base_delta,
                    sensitivity_delta=args.sensitivity_delta,
                    base=base,
                    sensitivity=sensitivity,
                )
            )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.trajectories_out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summary_rows).to_csv(args.out, index=False)
    pd.DataFrame(all_trajectory_rows).to_csv(args.trajectories_out, index=False)

    print(f"Wrote {len(summary_rows)} summary rows to {args.out}")
    print(f"Wrote {len(all_trajectory_rows)} trajectory rows to {args.trajectories_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
