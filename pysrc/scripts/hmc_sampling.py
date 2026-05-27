from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pysrc.replication.parameters import CarbonPriceKey, carbon_price, normalize_xi
from pysrc.sampling import adjusted
from pysrc.services.file_service import get_path


def xi_values(values: list[str]) -> list[float]:
    if values == ["all"]:
        return [1.0, 2.0, 0.5]
    return [float(value) for value in values]


def hmc_price(*, sites: int, xi: float) -> float:
    return carbon_price(
        CarbonPriceKey(
            context="parameter_ambiguity",
            model="hmc",
            sites=sites,
            xi=xi,
        )
    )


def deterministic_price(*, sites: int) -> float:
    return carbon_price(
        CarbonPriceKey(
            context="parameter_ambiguity",
            model="det",
            sites=sites,
            xi="inf",
        )
    )


def base_prices(args: argparse.Namespace, *, xi: float) -> list[tuple[str, float]]:
    include_hmc = args.price_source in {"hmc", "all"} or args.include_det_price
    include_det = args.price_source in {"det", "all"} or args.include_det_price

    prices: list[tuple[str, float]] = []
    if include_hmc:
        prices.append(("hmc", hmc_price(sites=args.sites, xi=xi)))
    if include_det:
        if normalize_xi(xi) != "1":
            raise ValueError("The deterministic-price HMC sampling case is only used for xi=1.")
        prices.append(("det", deterministic_price(sites=args.sites)))

    unique_prices: list[tuple[str, float]] = []
    seen: set[float] = set()
    for label, pee in prices:
        key = round(float(pee), 10)
        if key in seen:
            continue
        seen.add(key)
        unique_prices.append((label, pee))
    return unique_prices


def price_value(pee: float, transfer: float) -> float:
    return round(float(pee) + float(transfer), 10)


def sample_path(
    *,
    solver: str,
    sites: int,
    pa: float,
    xi: float,
    pe: float,
) -> Path:
    return (
        get_path("output")
        / "sampling"
        / solver
        / f"{sites}sites"
        / f"pa_{pa}"
        / f"xi_{xi}"
        / f"pe_{pe}"
        / "results.pcl"
    )


def run_one_sample(
    args: argparse.Namespace,
    *,
    xi: float,
    pee: float,
    price_source: str,
    transfer: float,
) -> None:
    pe = price_value(pee, transfer)
    outfile_path = sample_path(
        solver=args.solver,
        sites=args.sites,
        pa=args.pa,
        xi=xi,
        pe=pe,
    )
    if outfile_path.exists() and not args.force:
        print(f"Skipping existing HMC sampling output: {outfile_path}", flush=True)
        return

    print(
        f"Running HMC sampling for xi={normalize_xi(xi)}, "
        f"price_source={price_source}, pee={pee}, "
        f"transfer={transfer}, pe={pe}",
        flush=True,
    )
    results = adjusted.sample(
        xi=xi,
        pe=pe,
        pa=args.pa,
        weight=args.weight,
        num_sites=args.sites,
        T=args.horizon,
        solver=args.solver,
        max_iter=args.max_iter,
        final_sample_size=args.final_sample_size,
        iter_sampling=args.iter_sampling,
        iter_warmup=args.iter_warmup,
        show_progress=not args.no_progress,
        show_console=args.show_console,
        seed=args.seed,
        chains=args.chains,
        tol=args.tol,
    )

    outfile_path.parent.mkdir(parents=True, exist_ok=True)
    with outfile_path.open("wb") as outfile:
        pickle.dump(results, outfile)
    print(f"Results saved to {outfile_path}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate HMC sampling outputs used by HMC tables and figures."
    )
    parser.add_argument("--xi", nargs="+", default=["all"], help="xi values or `all`")
    parser.add_argument("--sites", type=int, default=1043)
    parser.add_argument("--solver", default="gurobi")
    parser.add_argument("--pa", type=float, default=41.11)
    parser.add_argument("--transfers", nargs="+", type=float, default=[0, 10, 15, 20, 25])
    parser.add_argument("--horizon", type=int, default=200)
    parser.add_argument("--weight", type=float, default=0.25)
    parser.add_argument("--max-iter", type=int, default=100)
    parser.add_argument("--final-sample-size", type=int, default=4000)
    parser.add_argument("--iter-sampling", type=int, default=4000)
    parser.add_argument("--iter-warmup", type=int, default=500)
    parser.add_argument("--chains", type=int, default=4)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--tol", type=float, default=0.005)
    parser.add_argument(
        "--price-source",
        choices=["hmc", "det", "all"],
        default="hmc",
        help="Which base carbon price to sample at before adding transfer levels.",
    )
    parser.add_argument(
        "--include-det-price",
        action="store_true",
        help=(
            "For xi=1, also generate samples at the deterministic carbon price. "
            "This supports the common-price HMC figures without hardcoding Pee."
        ),
    )
    parser.add_argument("--show-console", action="store_true")
    parser.add_argument("--no-progress", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    for xi in xi_values(args.xi):
        for price_source, pee in base_prices(args, xi=xi):
            for transfer in args.transfers:
                run_one_sample(
                    args,
                    xi=xi,
                    pee=pee,
                    price_source=price_source,
                    transfer=transfer,
                )

    print("HMC sampling outputs done.", flush=True)


if __name__ == "__main__":
    main()
