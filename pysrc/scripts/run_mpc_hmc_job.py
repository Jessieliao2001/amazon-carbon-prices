from __future__ import annotations

import argparse
import shlex
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
            "Run one MPC-HMC job. Stdout/stderr are left attached to the caller "
            "so the replication driver stores the full MPC-HMC log under the "
            "current stage-specific job-outs folder."
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
    print(f"MPC-HMC command: {shlex.join(command)}")
    start = time.time()
    print(f"MPC-HMC child starts {time.ctime(start)}")
    sys.stdout.flush()
    result = subprocess.run(command, cwd=root)
    end = time.time()
    print(f"MPC-HMC child ends {time.ctime(end)}")
    elapsed = int(end - start)
    days, rem = divmod(elapsed, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    print(f"MPC-HMC child elapsed time: {days} days {hours:02d} hr {minutes:02d} min {seconds:02d} sec")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
