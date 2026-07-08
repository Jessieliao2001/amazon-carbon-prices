import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pysrc.services.file_service import get_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report the in-text correlation between fitted gamma and theta."
    )
    parser.add_argument("--sites", type=int, default=1043)
    args = parser.parse_args()

    project_root = get_path()
    data_path = (
        project_root
        / "data"
        / "calibration"
        / f"productivity_params_{args.sites}.csv"
    )
    df = pd.read_csv(data_path)
    required = {"gamma_fit", "theta_fit"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in {data_path}: {sorted(missing)}")

    correlation = df["gamma_fit"].corr(df["theta_fit"])
    print("In-text check: productivity parameter correlation")
    print(f"Source file: {data_path.relative_to(project_root)}")
    print(
        "Pearson correlation between gamma_fit and theta_fit "
        f"= {correlation:.16f}"
    )
    print(f"Rounded manuscript value = {correlation:.2f}")


if __name__ == "__main__":
    main()
