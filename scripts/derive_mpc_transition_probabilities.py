from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pysrc.replication.parameters import CARBON_PRICE_FILE, normalize_xi
from pysrc.services.file_service import get_path


OUTPUT_COLUMNS = [
    "context",
    "model",
    "sites",
    "xi",
    "pe",
    "b",
    "mc",
    "prob_from_low_to_low",
    "prob_from_high_to_high",
    "source_file",
]
EXPECTED_B_VALUES = {0, 10, 15, 20, 25}
NUMBER_RE = re.compile(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?")
PARAMETERS_RE = re.compile(
    r"Parameters from current iteration:\s*\[(?P<params>[^\]]+)\]",
    re.S,
)
YEAR_DONE_RE = re.compile(r"\byear done:\s*1\b")


def _part_value(path: Path, prefix: str) -> str | None:
    for part in path.parts:
        if part.startswith(prefix):
            return part[len(prefix) :]
    return None


def _infer_b(model: str, xi: str, pe: float, prices: pd.DataFrame) -> float | None:
    if prices.empty:
        return None
    matches = prices[
        (prices["context"] == "price_stochasticity")
        & (prices["model"] == model)
        & (prices["xi"].map(normalize_xi) == xi)
    ]
    if matches.empty:
        return None
    pee = float(matches.iloc[0]["pee"])
    return round(pe - pee, 10)


def _canonical_b(value: float | None) -> float | None:
    if value is None:
        return None
    nearest = int(round(value))
    if nearest in EXPECTED_B_VALUES and abs(value - nearest) < 1e-6:
        return float(nearest)
    return None


def _year1_probabilities(path: Path) -> tuple[float, float] | None:
    text = path.read_text(errors="ignore")
    year_match = YEAR_DONE_RE.search(text)
    if year_match is None:
        return None

    prefix = text[: year_match.start()]
    matches = list(PARAMETERS_RE.finditer(prefix))
    if not matches:
        return None

    params = [float(value) for value in NUMBER_RE.findall(matches[-1].group("params"))]
    if len(params) < 2:
        return None

    prob_from_low_to_low = params[-2]
    prob_from_high_to_high = 1.0 - params[-1]
    return prob_from_low_to_low, prob_from_high_to_high


def collect_probabilities(
    root: Path,
    prices: pd.DataFrame,
    run_id: str = "998",
    trig: str = "0",
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    pattern = f"job-outs/mpc/xi_*/pe_*/id_{run_id}/trig_{trig}/type_*/run.out"
    for path in sorted(root.glob(pattern)):
        xi = normalize_xi(_part_value(path, "xi_"))
        pe = float(_part_value(path, "pe_") or "nan")
        mc = _part_value(path, "id_")
        model = _part_value(path, "type_") or ""
        probabilities = _year1_probabilities(path)
        if probabilities is None:
            continue
        prob_from_low_to_low, prob_from_high_to_high = probabilities
        b_value = _canonical_b(_infer_b(model, xi, pe, prices))
        if b_value is None:
            continue
        rows.append(
            {
                "context": "price_stochasticity",
                "model": model,
                "sites": 78,
                "xi": xi,
                "pe": pe,
                "b": b_value,
                "mc": mc,
                "prob_from_low_to_low": prob_from_low_to_low,
                "prob_from_high_to_high": prob_from_high_to_high,
                "source_file": str(path.relative_to(root)),
            }
        )
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Derive MPC distorted transition probabilities from MPC run logs. "
            "This script does not read values from the manuscript."
        )
    )
    parser.add_argument("--root", type=Path, default=get_path())
    parser.add_argument("--carbon-prices", type=Path, default=CARBON_PRICE_FILE)
    parser.add_argument("--run-id", default="998")
    parser.add_argument("--trig", default="0")
    parser.add_argument(
        "--out",
        type=Path,
        default=get_path("replication", "derived", "mpc_transition_probabilities.csv"),
    )
    args = parser.parse_args()

    prices = pd.DataFrame()
    if args.carbon_prices.exists():
        prices = pd.read_csv(args.carbon_prices)
        prices["xi"] = prices["xi"].map(normalize_xi)

    result = collect_probabilities(args.root, prices, run_id=args.run_id, trig=args.trig)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.out, index=False)
    print(f"Wrote {len(result)} transition-probability rows to {args.out}")
    if result.empty:
        print("No matching MPC run logs with year done: 1 were found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
