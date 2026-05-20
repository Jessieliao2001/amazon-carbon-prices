import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pysrc.analysis.figures import density, trajectory_diff
from pysrc.analysis.map import spatial_allocation
from pysrc.analysis.tables import ambiguity_decom, transfer_cost
from pysrc.replication.parameters import CarbonPriceKey, carbon_price, normalize_xi
from pysrc.services.get_opt import get_optimization


def _xi_values(values):
    if values == ["all"]:
        return [1.0, 2.0, 0.5]
    return [float(value) for value in values]


def _hmc_price(xi: float) -> float:
    return carbon_price(
        CarbonPriceKey(context="parameter_ambiguity", model="hmc", sites=1043, xi=xi)
    )


def _det_price() -> float:
    return carbon_price(
        CarbonPriceKey(context="parameter_ambiguity", model="det", sites=1043, xi="inf")
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run parameter-ambiguity outputs.")
    parser.add_argument("--xi", nargs="+", default=["1"], help="xi values or `all`")
    parser.add_argument("--solver", default="gurobi")
    parser.add_argument("--pa", type=float, default=41.11)
    parser.add_argument("--skip-optimization", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument(
        "--tables",
        nargs="+",
        choices=["ambiguity", "transfer-cost"],
        default=[],
    )
    parser.add_argument(
        "--figures",
        nargs="+",
        choices=["density", "histograms", "trajectories"],
        default=[],
    )
    args = parser.parse_args()

    if args.all:
        args.tables = ["ambiguity", "transfer-cost"]
        args.figures = ["density", "histograms", "trajectories"]

    det_pee = _det_price()
    for xi in _xi_values(args.xi):
        hmc_pee = _hmc_price(xi)
        xi_label = normalize_xi(xi)
        print(f"Running HMC outputs for xi={xi_label}, Pee={hmc_pee}")

        if not args.skip_optimization:
            get_optimization(
                num_sites=1043,
                pee=hmc_pee,
                model="hmc",
                xi=xi,
                solver=args.solver,
                pa=args.pa,
            )

        if "ambiguity" in args.tables:
            ambiguity_decom(
                num_sites=1043,
                pe_det=det_pee,
                pe_hmc=hmc_pee,
                xi=xi,
                solver=args.solver,
                pa=args.pa,
            )
        if "transfer-cost" in args.tables:
            transfer_cost(
                num_sites=1043,
                pee=hmc_pee,
                xi=xi,
                solver=args.solver,
                y=30,
                model="hmc",
                pa=args.pa,
            )
            transfer_cost(
                num_sites=1043,
                pee=hmc_pee,
                xi=xi,
                solver=args.solver,
                y=15,
                model="hmc",
                pa=args.pa,
            )

        if "density" in args.figures:
            density(num_sites=1043, pee=hmc_pee, xi=xi, solver=args.solver, pa=args.pa)
        if "trajectories" in args.figures:
            trajectory_diff(
                num_sites=1043,
                pe_hmc=hmc_pee,
                pe_det=det_pee,
                b=0,
                solver=args.solver,
                pa=args.pa,
                xi=xi,
            )
            trajectory_diff(
                num_sites=1043,
                pe_hmc=hmc_pee,
                pe_det=det_pee,
                b=15,
                solver=args.solver,
                pa=args.pa,
                xi=xi,
            )
        if "histograms" in args.figures:
            spatial_allocation(
                num_sites=1043,
                pe_hmc=hmc_pee,
                pe_det=det_pee,
                b=0,
                solver=args.solver,
                pa=args.pa,
                xi=xi,
            )
            spatial_allocation(
                num_sites=1043,
                pe_hmc=hmc_pee,
                pe_det=det_pee,
                b=15,
                solver=args.solver,
                pa=args.pa,
                xi=xi,
            )

    print("hmc All done!")


if __name__ == "__main__":
    main()
