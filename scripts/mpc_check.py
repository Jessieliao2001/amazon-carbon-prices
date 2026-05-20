import re
import csv
import argparse
from pathlib import Path
from collections import defaultdict

from pysrc.replication.parameters import CarbonPriceKey, carbon_price
from pysrc.services.file_service import get_path


def _price_for_xi(xi):
    return f"{carbon_price(CarbonPriceKey(context='price_stochasticity', model='unconstrained', sites=78, xi=xi, price_model='distinct_variance')):g}"


parser = argparse.ArgumentParser(description="Summarize MPC run.out parameter logs.")
parser.add_argument("--base-dir", type=Path, default=get_path("job-outs", "mpc"))
args = parser.parse_args()

BASE_DIR = args.base_dir

XI_PE_PAIRS = [
    ("0.5", _price_for_xi(0.5)),
    ("1", _price_for_xi(1)),
    ("10000", _price_for_xi("inf")),
]

YEAR_MIN = 25
YEAR_MAX = 30

SAVE_DETAIL_CSV = True
DETAIL_CSV_NAME = "last_two_params_year25_30_detail.csv"

SAVE_AVG_CSV = True
AVG_CSV_NAME = "last_two_params_year25_30_avg.csv"
# =========================

# 匹配：
# Parameters from current iteration:
#     [....]
# ...
# year done: N
BLOCK_PATTERN = re.compile(
    r"Parameters from current iteration:\s*\[\s*(.*?)\s*\]\s*.*?year done:\s*(\d+)",
    re.S,
)

# 匹配浮点数/科学计数法
NUM_PATTERN = re.compile(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?")


def parse_one_file(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    results = []

    for m in BLOCK_PATTERN.finditer(text):
        param_block, year_str = m.groups()
        year = int(year_str)

        if YEAR_MIN <= year <= YEAR_MAX:
            nums = [float(x) for x in NUM_PATTERN.findall(param_block)]
            if len(nums) >= 2:
                results.append((year, nums[-2], nums[-1]))

    return results


def safe_float(x):
    try:
        return float(x)
    except ValueError:
        return float("inf")


all_rows = []

for xi, pe in XI_PE_PAIRS:
    for id_num in range(1, 51):
        if xi == "10000":
            run_out = (
                BASE_DIR
                / f"xi_{xi}"
                / f"pe_{pe}"
                / f"id_{id_num}"
                / "trig_0"
                / "type_unconstrained"
                / "run.out"
            )
        else:
            run_out = (
                BASE_DIR
                / f"xi_{xi}"
                / f"pe_{pe}"
                / f"id_{id_num}"
                / "trig_1"
                / "type_unconstrained"
                / "run.out"
            )

        if not run_out.exists():
            print(f"[WARN] file not found: {run_out}")
            continue

        matches = parse_one_file(run_out)

        if not matches:
            print(f"[WARN] no matching blocks found: {run_out}")
            continue

        for year, last_2nd, last_1st in matches:
            all_rows.append({
                "xi": xi,
                "pe": pe,
                "id": id_num,
                "year_done": year,
                "second_last_param": last_2nd,
                "last_param": last_1st,
                "file": str(run_out),
            })

# 排序：xi, pe, id, year
all_rows.sort(key=lambda r: (
    safe_float(r["xi"]),
    safe_float(r["pe"]),
    r["id"],
    r["year_done"],
))

# # 先打印每个 id 的明细
# print("\n=== Detail results ===")
# for r in all_rows:
#     print(
#         f'xi={r["xi"]:<6} '
#         f'pe={r["pe"]:<6} '
#         f'id={r["id"]:<2} '
#         f'year={r["year_done"]:<2} '
#         f'last_two=({r["second_last_param"]}, {r["last_param"]})'
#     )

# ===== 按 (xi, pe, year_done) 求 50 个 id 的平均 =====
grouped = defaultdict(list)

for r in all_rows:
    key = (r["xi"], r["pe"], r["year_done"])
    grouped[key].append(r)

avg_rows = []

for (xi, pe, year), rows in grouped.items():
    avg_second_last = sum(r["second_last_param"] for r in rows) / len(rows)
    avg_last = sum(r["last_param"] for r in rows) / len(rows)

    avg_rows.append({
        "xi": xi,
        "pe": pe,
        "year_done": year,
        "num_ids_found": len(rows),
        "avg_second_last_param": avg_second_last,
        "avg_last_param": avg_last,
    })

avg_rows.sort(key=lambda r: (
    safe_float(r["xi"]),
    safe_float(r["pe"]),
    r["year_done"],
))

# 打印平均值
print("\n=== Average across ids for each (xi, pe, year_done) ===")
for r in avg_rows:
    print(
        f'xi={r["xi"]:<6} '
        f'pe={r["pe"]:<6} '
        f'year={r["year_done"]:<2} '
        f'n={r["num_ids_found"]:<2} '
        f'avg_last_two=({r["avg_second_last_param"]:.8f}, {r["avg_last_param"]:.8f})'
    )

# 保存明细 CSV
if SAVE_DETAIL_CSV and all_rows:
    with open(DETAIL_CSV_NAME, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "xi",
                "pe",
                "id",
                "year_done",
                "second_last_param",
                "last_param",
                "file",
            ],
        )
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nSaved detail csv to {DETAIL_CSV_NAME}")

# 保存平均值 CSV
if SAVE_AVG_CSV and avg_rows:
    with open(AVG_CSV_NAME, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "xi",
                "pe",
                "year_done",
                "num_ids_found",
                "avg_second_last_param",
                "avg_last_param",
            ],
        )
        writer.writeheader()
        writer.writerows(avg_rows)

    print(f"Saved average csv to {AVG_CSV_NAME}")
