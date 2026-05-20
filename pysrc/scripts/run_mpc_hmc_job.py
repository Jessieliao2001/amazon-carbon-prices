from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pysrc.replication.parameters import CarbonPriceKey, carbon_price, normalize_xi


def price_model_for(model: str) -> str:
    return "common_variance" if model == "constrained" else "distinct_variance"


def format_float(value: float) -> str:
    return f"{value:g}"


def xi_for_command(value: str) -> str:
    return "10000" if normalize_xi(value) == "inf" else normalize_xi(value)


def mpc_price(model: str, xi: str, b: float, explicit_pe: float | None) -> float:
    if explicit_pe is not None:
        return explicit_pe
    return (
        carbon_price(
            CarbonPriceKey(
                context="price_stochasticity",
                model=model,
                sites=78,
                xi=normalize_xi(xi),
                price_model=price_model_for(model),
            )
        )
        + b
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run one MPC-HMC job and save stdout/stderr under job-outs/mpc so "
            "the replication post-processing can parse the original log format."
        )
    )
    parser.add_argument("--id", type=int, required=True)
    parser.add_argument("--xi", required=True)
    parser.add_argument("--b", type=float, default=0.0)
    parser.add_argument("--pe", type=float)
    parser.add_argument("--trig", type=int, required=True)
    parser.add_argument("--type", choices=["unconstrained", "constrained"], required=True)
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    xi_arg = xi_for_command(args.xi)
    pe = mpc_price(args.type, args.xi, args.b, args.pe)
    pe_label = format_float(pe)

    out_dir = (
        root
        / "job-outs"
        / "mpc"
        / f"xi_{xi_arg}"
        / f"pe_{pe_label}"
        / f"id_{args.id}"
        / f"trig_{args.trig}"
        / f"type_{args.type}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    command = [
        args.python,
        "-u",
        "pysrc/mpc/mpc_hmc.py",
        "--id",
        str(args.id),
        "--pe",
        pe_label,
        "--xi",
        xi_arg,
        "--trig",
        str(args.trig),
        "--type",
        args.type,
    ]

    print(
        "Running MPC-HMC job: "
        f"xi={xi_arg} pe={pe_label} id={args.id} trig={args.trig} type={args.type}"
    )
    start = time.time()
    with (out_dir / "run.out").open("w") as stdout, (out_dir / "run.err").open("w") as stderr:
        stdout.write(f"Program starts {time.ctime(start)}\n")
        stdout.flush()
        result = subprocess.run(command, cwd=root, stdout=stdout, stderr=stderr)
        end = time.time()
        stdout.write(f"Program ends {time.ctime(end)}\n")
        elapsed = int(end - start)
        days, rem = divmod(elapsed, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        stdout.write(
            f"Elapsed time: {days} days {hours:02d} hr {minutes:02d} min {seconds:02d} sec\n"
        )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
