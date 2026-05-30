from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pysrc.scripts.hmc_sampling import run_one_sample


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compatibility entry point for one HMC sampling job."
    )
    parser.add_argument("--pee", type=float, required=True)
    parser.add_argument("--xi", type=float, required=True)
    parser.add_argument("--id", type=float, required=True, help="Transfer level b.")
    parser.add_argument("--sites", type=int, default=1043)
    parser.add_argument("--solver", default="gurobi")
    parser.add_argument("--pa", type=float, default=41.11)
    parser.add_argument("--horizon", type=int, default=200)
    parser.add_argument("--weight", type=float, default=0.25)
    parser.add_argument("--max-iter", type=int, default=100)
    parser.add_argument("--final-sample-size", type=int, default=4000)
    parser.add_argument("--iter-sampling", type=int, default=4000)
    parser.add_argument("--iter-warmup", type=int, default=500)
    parser.add_argument("--chains", type=int, default=4)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--tol", type=float, default=0.005)
    parser.add_argument("--show-console", action="store_true", default=True)
    parser.add_argument("--no-progress", action="store_true")
    args = parser.parse_args()

    run_one_sample(
        args,
        xi=args.xi,
        pee=args.pee,
        price_source="explicit",
        transfer=args.id,
    )


if __name__ == "__main__":
    main()
