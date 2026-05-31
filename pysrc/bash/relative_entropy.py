from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import entropy, gaussian_kde
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pysrc.replication.parameters import CarbonPriceKey, carbon_price, normalize_xi
from pysrc.services.file_service import get_path


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


def legacy_neutral_paths(
    *,
    solver: str,
    sites: int,
    pa: float,
    det_pee: float,
) -> list[Path]:
    pe = price_value(det_pee, 15)
    root = get_path("output") / "sampling" / solver / f"{sites}sites" / f"pa_{pa}"
    return [
        root / "xi_10000.0" / f"pe_{pe}" / "results.pcl",
        root / "xi_10000" / f"pe_{pe}" / "results.pcl",
    ]


def load_pickle(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing sampling output: {path}")
    with path.open("rb") as file:
        return pickle.load(file)


def adjusted_samples(results: dict, num_sites: int) -> tuple[np.ndarray, np.ndarray]:
    if "final_sample" not in results:
        raise KeyError("Adjusted sampling output is missing `final_sample`.")
    sample = results["final_sample"][:16000]
    return sample[:, :num_sites], sample[:, num_sites:]


def load_neutral_samples(
    *,
    solver: str,
    sites: int,
    pa: float,
    det_pee: float,
) -> tuple[np.ndarray, np.ndarray]:
    for path in legacy_neutral_paths(solver=solver, sites=sites, pa=pa, det_pee=det_pee):
        if path.exists():
            print(f"Using old xi=10000 sampling output as neutral reference: {path}", flush=True)
            return adjusted_samples(load_pickle(path), sites)

    raise FileNotFoundError(
        "Missing old neutral sampling output. Expected one of "
        f"{legacy_neutral_paths(solver=solver, sites=sites, pa=pa, det_pee=det_pee)}."
    )


def compute_kl(unadjusted: np.ndarray, adjusted: np.ndarray) -> float:
    common_grid = np.linspace(
        min(unadjusted.min(), adjusted.min()),
        max(unadjusted.max(), adjusted.max()),
        100,
    )
    p = gaussian_kde(unadjusted, bw_method="scott")(common_grid) + 1e-20
    q = gaussian_kde(adjusted, bw_method="scott")(common_grid) + 1e-20
    return float(entropy(p, q))


def density_sites_from_kl(kl_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for parameter, transfer, column in [
        ("theta", "b0", "theta_b0"),
        ("theta", "b15", "theta_b15"),
        ("gamma", "b0", "gamma_b0"),
        ("gamma", "b15", "gamma_b15"),
    ]:
        top = kl_df.nlargest(1, column).iloc[0]
        rows.append(
            {
                "parameter": parameter,
                "transfer": transfer,
                "source_column": column,
                "site_id": int(top["id"]),
                "relative_entropy": float(top[column]),
            }
        )
    return pd.DataFrame(rows)


def ordered_site_ids(selected_sites: pd.DataFrame, parameter: str) -> list[int]:
    values = selected_sites.loc[selected_sites["parameter"] == parameter, "site_id"]
    return list(dict.fromkeys(int(value) for value in values))


def build_relative_entropy(
    *,
    solver: str,
    sites: int,
    pa: float,
    xi: float,
    pee: float,
    det_pee: float,
) -> tuple[Path, Path, list[int], list[int]]:
    b0_path = sample_path(solver=solver, sites=sites, pa=pa, xi=xi, pe=pee)
    b15_path = sample_path(
        solver=solver,
        sites=sites,
        pa=pa,
        xi=xi,
        pe=price_value(pee, 15),
    )

    print(f"Loading adjusted b=0 sample: {b0_path}", flush=True)
    theta_adjusted_b0, gamma_adjusted_b0 = adjusted_samples(load_pickle(b0_path), sites)

    print(f"Loading adjusted b=15 sample: {b15_path}", flush=True)
    theta_adjusted_b15, gamma_adjusted_b15 = adjusted_samples(load_pickle(b15_path), sites)

    theta_unadjusted, gamma_unadjusted = load_neutral_samples(
        solver=solver,
        sites=sites,
        pa=pa,
        det_pee=det_pee,
    )

    kl_data: dict[str, object] = {"id": np.arange(1, sites + 1)}

    print("Computing theta KL divergences...", flush=True)
    for label, theta_hmc in [
        ("theta_b0", theta_adjusted_b0),
        ("theta_b15", theta_adjusted_b15),
    ]:
        kl_data[label] = [
            compute_kl(theta_unadjusted[:, i], theta_hmc[:, i])
            for i in tqdm(range(sites), desc=label)
        ]

    print("Computing gamma KL divergences...", flush=True)
    for label, gamma_hmc in [
        ("gamma_b0", gamma_adjusted_b0),
        ("gamma_b15", gamma_adjusted_b15),
    ]:
        kl_data[label] = [
            compute_kl(gamma_unadjusted[:, i], gamma_hmc[:, i])
            for i in tqdm(range(sites), desc=label)
        ]

    kl_df = pd.DataFrame(kl_data)
    output_folder = get_path("output", "figures", "entropy", f"site_{sites}", f"xi{xi}")
    output_folder.mkdir(parents=True, exist_ok=True)
    output_path = output_folder / "kl_divergences_theta_gamma.csv"
    kl_df.to_csv(output_path, index=False)

    selected_sites = density_sites_from_kl(kl_df)
    selected_sites_path = output_folder / "density_sites_from_relative_entropy.csv"
    selected_sites.to_csv(selected_sites_path, index=False)
    gamma_sites = ordered_site_ids(selected_sites, "gamma")
    theta_sites = ordered_site_ids(selected_sites, "theta")

    print(f"Relative entropy CSV saved to {output_path}", flush=True)
    print(f"Density-site selection saved to {selected_sites_path}", flush=True)
    print(f"Gamma density sites selected from KL output: {gamma_sites}", flush=True)
    print(f"Theta density sites selected from KL output: {theta_sites}", flush=True)
    print("Top 2 KL divergences per parameter:", flush=True)
    for column in ["theta_b0", "theta_b15", "gamma_b0", "gamma_b15"]:
        for site, value in kl_df.nlargest(2, column)[["id", column]].values.tolist():
            print(f"{column}: id {int(site)} -> KL = {value:.4f}", flush=True)

    return output_path, selected_sites_path, gamma_sites, theta_sites


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate relative-entropy inputs for HMC map figures."
    )
    parser.add_argument("--pee", type=float, default=None)
    parser.add_argument("--pee-det", type=float, default=None)
    parser.add_argument("--xi", type=float, default=1.0)
    parser.add_argument("--sites", type=int, default=1043)
    parser.add_argument("--solver", default="gurobi")
    parser.add_argument("--pa", type=float, default=41.11)
    parser.add_argument("--skip-density", action="store_true")
    args = parser.parse_args()

    xi_label = normalize_xi(args.xi)
    if xi_label != "1":
        raise ValueError("Relative-entropy maps are currently defined for xi=1 only.")

    pee = args.pee
    if pee is None:
        pee = carbon_price(
            CarbonPriceKey(
                context="parameter_ambiguity",
                model="hmc",
                sites=args.sites,
                xi=args.xi,
            )
        )

    det_pee = args.pee_det
    if det_pee is None:
        det_pee = carbon_price(
            CarbonPriceKey(
                context="parameter_ambiguity",
                model="det",
                sites=args.sites,
                xi="inf",
            )
        )

    output_path, selected_sites_path, gamma_sites, theta_sites = build_relative_entropy(
        solver=args.solver,
        sites=args.sites,
        pa=args.pa,
        xi=args.xi,
        pee=pee,
        det_pee=det_pee,
    )

    if not args.skip_density:
        from pysrc.analysis.figures import density

        print("Generating density plots for the same sample.", flush=True)
        density(
            num_sites=args.sites,
            pee=pee,
            xi=args.xi,
            solver=args.solver,
            gamma_sites_to_plot=gamma_sites,
            theta_sites_to_plot=theta_sites,
        )

    print(f"Relative entropy step done: {output_path}", flush=True)
    print(f"Density-site selection done: {selected_sites_path}", flush=True)


if __name__ == "__main__":
    main()
