from __future__ import annotations

import argparse
import re
import shlex
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

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
RUN_HEADER_RE = re.compile(
    r"Running MPC-HMC job:\s+"
    r"xi=(?P<xi>\S+)\s+"
    r"pe=(?P<pe>\S+)\s+"
    r"id=(?P<id>\S+)\s+"
    r"trig=(?P<trig>\S+)\s+"
    r"type=(?P<model>\S+)"
)


def _part_value(path: Path, prefix: str) -> str | None:
    for part in path.parts:
        if part.startswith(prefix):
            return part[len(prefix) :]
    return None


def _source_file(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in sorted(paths):
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def _command_path_for(log_path: Path) -> Path:
    if log_path.name.endswith("_run.out"):
        return log_path.with_name(log_path.name.replace("_run.out", "_command.txt"))
    return log_path.with_name("command.txt")


def _command_from_log(log_path: Path, text: str) -> list[str]:
    command_path = _command_path_for(log_path)
    command_text = ""
    if command_path.exists():
        command_text = command_path.read_text(errors="ignore").strip()
    else:
        for line in text.splitlines()[:5]:
            if line.startswith("Command:"):
                command_text = line.split(":", 1)[1].strip()
                break
    if not command_text:
        return []
    try:
        return shlex.split(command_text)
    except ValueError:
        return []


def _option_value(command: list[str], option: str) -> str | None:
    try:
        index = command.index(option)
    except ValueError:
        return None
    if index + 1 >= len(command):
        return None
    return command[index + 1]


def _metadata_from_path(path: Path) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for key, prefix in [
        ("xi", "xi_"),
        ("pe", "pe_"),
        ("id", "id_"),
        ("trig", "trig_"),
        ("model", "type_"),
    ]:
        value = _part_value(path, prefix)
        if value is not None:
            metadata[key] = value
    return metadata


def _metadata_from_text(text: str) -> dict[str, str]:
    match = RUN_HEADER_RE.search(text)
    if match is None:
        return {}
    return {
        "xi": match.group("xi"),
        "pe": match.group("pe"),
        "id": match.group("id"),
        "trig": match.group("trig"),
        "model": match.group("model"),
    }


def _metadata_from_command(command: list[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for key, option in [
        ("xi", "--xi"),
        ("pe", "--pe"),
        ("id", "--id"),
        ("trig", "--trig"),
        ("model", "--type"),
    ]:
        value = _option_value(command, option)
        if value is not None:
            metadata[key] = value
    return metadata


def _candidate_logs(root: Path) -> list[Path]:
    paths = list(root.glob("job-outs/mpc/xi_*/pe_*/id_*/trig_*/type_*/run.out"))
    paths.extend(root.glob("job-outs/mpc/xi_*/pe_*/id_*/trig_*/type_*/*_run.out"))
    paths.extend(root.glob("job-outs/**/*_mpc_hmc_*/*_run.out"))
    paths.extend(
        path
        for path in root.glob("job-outs/**/*_mpc_hmc_*/run.out")
        if path.with_name("command.txt").exists()
    )
    return _unique_paths(paths)


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
    model: str | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for path in _candidate_logs(root):
        text = path.read_text(errors="ignore")
        metadata = _metadata_from_path(path)
        metadata.update({k: v for k, v in _metadata_from_text(text).items() if v})
        command_metadata = _metadata_from_command(_command_from_log(path, text))
        metadata.update(
            {k: v for k, v in command_metadata.items() if v}
        )
        if metadata.get("id") != run_id or metadata.get("trig") != trig:
            continue
        if not {"xi", "pe", "model"}.issubset(metadata):
            continue
        xi = normalize_xi(metadata["xi"])
        pe = float(metadata["pe"])
        mc = metadata.get("id")
        log_model = metadata["model"]
        if model is not None and log_model != model:
            continue
        probabilities = _year1_probabilities(path)
        if probabilities is None:
            continue
        prob_from_low_to_low, prob_from_high_to_high = probabilities
        b_value = _canonical_b(_infer_b(log_model, xi, pe, prices))
        if b_value is None:
            continue
        rows.append(
            {
                "context": "price_stochasticity",
                "model": log_model,
                "sites": 78,
                "xi": xi,
                "pe": pe,
                "b": b_value,
                "mc": mc,
                "prob_from_low_to_low": prob_from_low_to_low,
                "prob_from_high_to_high": prob_from_high_to_high,
                "source_file": _source_file(path, root),
            }
        )
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def merge_model_rows(
    existing_path: Path,
    new_rows: pd.DataFrame,
    model: str | None,
) -> pd.DataFrame:
    if model is None or not existing_path.exists():
        return new_rows

    existing = pd.read_csv(existing_path)
    if existing.empty:
        return new_rows
    existing = existing.reindex(columns=OUTPUT_COLUMNS)
    existing = existing[existing["model"] != model]
    merged = pd.concat([existing, new_rows], ignore_index=True)
    return merged.reindex(columns=OUTPUT_COLUMNS)


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
    parser.add_argument("--model", choices=["unconstrained", "constrained"])
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

    result = collect_probabilities(
        args.root,
        prices,
        run_id=args.run_id,
        trig=args.trig,
        model=args.model,
    )
    result = merge_model_rows(args.out, result, args.model)
    if not result.empty:
        result = result.sort_values(["model", "xi", "b", "pe", "mc"]).reset_index(drop=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.out, index=False)
    print(f"Wrote {len(result)} transition-probability rows to {args.out}")
    if result.empty:
        print("No matching MPC run logs with year done: 1 were found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
