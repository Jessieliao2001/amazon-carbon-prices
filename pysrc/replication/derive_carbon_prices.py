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


NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
SHADOW_RE = re.compile(rf"min_result\s+(?P<metric>{NUMBER})\s+min_pe\s+(?P<pee>{NUMBER})")
MPC_HEADER_RE = re.compile(
    rf"\bxi\s+(?P<xi>{NUMBER})\s+pe\s+(?P<pee>{NUMBER})\s+model\s+(?P<model>[A-Za-z_]+)"
)
RATIO_RE = re.compile(rf"\bratio\s+(?P<metric>{NUMBER})")
DEFAULT_DELTA = 0.02


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


def _command_from_log(log_path: Path, text: str | None = None) -> list[str]:
    command_path = _command_path_for(log_path)
    command_text = ""
    if command_path.exists():
        command_text = command_path.read_text(errors="ignore").strip()
    else:
        if text is None:
            text = log_path.read_text(errors="ignore")
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


def _command_contains(command: list[str], script_name: str) -> bool:
    return any(part.replace("\\", "/").endswith(script_name) for part in command)


def _option_value(command: list[str], option: str) -> str | None:
    try:
        index = command.index(option)
    except ValueError:
        return None
    if index + 1 >= len(command):
        return None
    return command[index + 1]


def _option_float(command: list[str], option: str, default: float) -> float:
    value = _option_value(command, option)
    if value is None:
        return default
    return float(value)


def _local_driver_logs(log_root: Path) -> list[Path]:
    candidates = list(log_root.rglob("*_run.out"))
    candidates.extend(
        path
        for path in log_root.rglob("run.out")
        if path.with_name("command.txt").exists()
    )
    return _unique_paths(candidates)


def _shadow_row(
    *,
    path: Path,
    root: Path,
    text: str,
    xi: str | None,
    sites: int | None,
    delta: float,
    source_kind: str,
) -> dict[str, object] | None:
    match = SHADOW_RE.search(text)
    if not match or xi is None or sites is None:
        return None
    xi = normalize_xi(xi)
    metric = float(match.group("metric"))
    return {
        "context": "parameter_ambiguity",
        "model": "det" if xi == "inf" else "hmc",
        "sites": sites,
        "xi": xi,
        "delta": delta,
        "price_model": "",
        "pee": float(match.group("pee")),
        "metric": metric,
        "abs_metric": abs(metric),
        "source_kind": source_kind,
        "source_file": _source_file(path, root),
    }


def parse_shadow_price_logs(log_root: Path, root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted(log_root.glob("shadow_price/xi_*/id_*/sites_*/run.out")):
        text = path.read_text(errors="ignore")
        row = _shadow_row(
            path=path,
            root=root,
            text=text,
            xi=_part_value(path, "xi_"),
            sites=int(_part_value(path, "sites_") or 0),
            delta=DEFAULT_DELTA,
            source_kind="shadow_price_log",
        )
        if row is not None:
            rows.append(row)

    for path in _local_driver_logs(log_root):
        text = path.read_text(errors="ignore")
        command = _command_from_log(path, text)
        if not _command_contains(command, "pysrc/bash/shadow_price.py"):
            continue
        sites = _option_value(command, "--sites")
        row = _shadow_row(
            path=path,
            root=root,
            text=text,
            xi=_option_value(command, "--xi"),
            sites=int(sites) if sites is not None else None,
            delta=_option_float(command, "--delta", DEFAULT_DELTA),
            source_kind="shadow_price_local_log",
        )
        if row is not None:
            rows.append(row)
    return rows


def _parse_mpc_shadow_price_file(
    path: Path,
    root: Path,
    *,
    source_kind: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for line in path.read_text(errors="ignore").splitlines():
        header = MPC_HEADER_RE.search(line)
        if header:
            current = {
                "xi": normalize_xi(header.group("xi")),
                "pee": float(header.group("pee")),
                "model": header.group("model"),
            }
            continue
        ratio = RATIO_RE.search(line)
        if ratio and current is not None:
            metric = float(ratio.group("metric"))
            model = str(current["model"])
            rows.append(
                {
                    "context": "price_stochasticity",
                    "model": model,
                    "sites": 78,
                    "xi": current["xi"],
                    "delta": DEFAULT_DELTA,
                    "price_model": (
                        "common_variance"
                        if model == "constrained"
                        else "distinct_variance"
                    ),
                    "pee": current["pee"],
                    "metric": metric,
                    "abs_metric": abs(metric),
                    "source_kind": source_kind,
                    "source_file": _source_file(path, root),
                }
            )
            current = None
    return rows


def parse_mpc_shadow_price_logs(log_root: Path, root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted(log_root.glob("mpc_compute_sp/run.out")):
        rows.extend(
            _parse_mpc_shadow_price_file(
                path,
                root,
                source_kind="mpc_shadow_price_log",
            )
        )

    for path in _local_driver_logs(log_root):
        text = path.read_text(errors="ignore")
        command = _command_from_log(path, text)
        if not _command_contains(command, "pysrc/mpc/mpc_compute_sp.py"):
            continue
        rows.extend(
            _parse_mpc_shadow_price_file(
                path,
                root,
                source_kind="mpc_shadow_price_local_log",
            )
        )
    return rows


def select_prices(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return candidates
    group_cols = ["context", "model", "sites", "xi", "price_model"]
    selected = (
        candidates.sort_values(["abs_metric", "pee"], ascending=[True, True])
        .groupby(group_cols, dropna=False, as_index=False)
        .head(1)
        .sort_values(group_cols)
        .reset_index(drop=True)
    )
    return selected


def filter_delta(candidates: pd.DataFrame, delta: float) -> pd.DataFrame:
    if candidates.empty:
        return candidates
    if "delta" not in candidates.columns:
        candidates = candidates.copy()
        candidates["delta"] = DEFAULT_DELTA
    return candidates.loc[candidates["delta"].astype(float).round(10) == round(delta, 10)].copy()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Derive business-as-usual carbon prices from model output logs. "
            "This script does not read numbers from the manuscript."
        )
    )
    parser.add_argument("--log-root", type=Path, default=get_path("job-outs"))
    parser.add_argument("--root", type=Path, default=get_path())
    parser.add_argument(
        "--delta",
        type=float,
        default=DEFAULT_DELTA,
        help=(
            "Only derive prices from logs run with this discount rate. "
            "Logs without an explicit --delta are treated as 0.02."
        ),
    )
    parser.add_argument("--out", type=Path, default=CARBON_PRICE_FILE)
    parser.add_argument(
        "--candidates-out",
        type=Path,
        default=get_path("replication", "derived", "carbon_price_candidates.csv"),
    )
    args = parser.parse_args()

    rows = []
    root = args.root.resolve()
    log_root = args.log_root.resolve()
    rows.extend(parse_shadow_price_logs(log_root, root))
    rows.extend(parse_mpc_shadow_price_logs(log_root, root))
    candidates = pd.DataFrame(rows)
    candidates = filter_delta(candidates, args.delta)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.candidates_out.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(args.candidates_out, index=False)

    selected = select_prices(candidates)
    selected.to_csv(args.out, index=False)

    print(f"Wrote {len(candidates)} candidate rows to {args.candidates_out}")
    print(f"Wrote {len(selected)} selected carbon prices to {args.out}")
    if selected.empty:
        print("No carbon-price logs were found. Run the shadow-price steps first.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
