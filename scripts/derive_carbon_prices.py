from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pysrc.replication.parameters import CARBON_PRICE_FILE, normalize_xi
from pysrc.services.file_service import get_path


NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
SHADOW_RE = re.compile(rf"min_result\s+(?P<metric>{NUMBER})\s+min_pe\s+(?P<pee>{NUMBER})")
MPC_HEADER_RE = re.compile(
    rf"\bxi\s+(?P<xi>{NUMBER})\s+pe\s+(?P<pee>{NUMBER})\s+model\s+(?P<model>[A-Za-z_]+)"
)
RATIO_RE = re.compile(rf"\bratio\s+(?P<metric>{NUMBER})")


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


def parse_shadow_price_logs(log_root: Path, root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted(log_root.glob("shadow_price/xi_*/id_*/sites_*/run.out")):
        text = path.read_text(errors="ignore")
        match = SHADOW_RE.search(text)
        if not match:
            continue
        xi = normalize_xi(_part_value(path, "xi_"))
        sites = int(_part_value(path, "sites_") or 0)
        metric = float(match.group("metric"))
        rows.append(
            {
                "context": "parameter_ambiguity",
                "model": "det" if xi == "inf" else "hmc",
                "sites": sites,
                "xi": xi,
                "price_model": "",
                "pee": float(match.group("pee")),
                "metric": metric,
                "abs_metric": abs(metric),
                "source_kind": "shadow_price_log",
                "source_file": _source_file(path, root),
            }
        )
    return rows


def parse_mpc_shadow_price_logs(log_root: Path, root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted(log_root.glob("mpc_compute_sp/run.out")):
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
                        "price_model": (
                            "common_variance"
                            if model == "constrained"
                            else "distinct_variance"
                        ),
                        "pee": current["pee"],
                        "metric": metric,
                        "abs_metric": abs(metric),
                        "source_kind": "mpc_shadow_price_log",
                        "source_file": _source_file(path, root),
                    }
                )
                current = None
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Derive business-as-usual carbon prices from model output logs. "
            "This script does not read numbers from the manuscript."
        )
    )
    parser.add_argument("--log-root", type=Path, default=get_path("job-outs"))
    parser.add_argument("--root", type=Path, default=get_path())
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
