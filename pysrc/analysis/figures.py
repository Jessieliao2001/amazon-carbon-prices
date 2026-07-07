import os
import pickle

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from pysrc.services.data_service import load_site_data
from pysrc.services.file_service import get_path


def land_allocation(pee=7.6, num_sites=1043, solver="gurobi", pa=41.11, model="det", xi=1):
    # Set transfer levels
    b = [0, 10, 15, 20, 25]

    # Set corresponding emissions prices
    pe = [pee + bi for bi in b]

    # Get z_bar data
    output_folder = get_path("output") / "figures"
    os.makedirs(output_folder, exist_ok=True)
    
    # Load site data
    (zbar, _, _) = load_site_data(num_sites)

    variable_dict = {}
    for j in range(5):
        order = j
        results_dir = (
            get_path("output")
            / "optimization"
            / model
            / solver
            / f"{num_sites}sites"
            / f"pa_{pa}"
            / f"pe_{pe[order]}"
        )

        dfz = np.loadtxt(results_dir / "Z.txt", delimiter=",")
        dfx = np.sum(np.loadtxt(results_dir / "X.txt", delimiter=","), axis=1)

        if model == "det":
            result_folder = os.path.join(
                str(get_path("output")),
                "optimization",
                model,
                solver,
                f"{num_sites}sites",
                f"pa_{pa}",
                f"pe_{pe[order]}",
            )
        elif model == "hmc":
            result_folder = os.path.join(
                str(get_path("output")),
                "optimization",
                model,
                solver,
                f"{num_sites}sites",
                f"xi_{xi}",
                f"pa_{pa}",
                f"pe_{pe[order]}",
            )
        dfz = np.loadtxt(os.path.join(result_folder, "Z.txt"), delimiter=",")
        dfx = np.sum(
            np.loadtxt(os.path.join(result_folder, "X.txt"), delimiter=","), axis=1
        )

        variable_dict[f"results_zper{j}"] = []
        variable_dict[f"results_xagg{j}"] = dfx[:51]
        for i in range(51):
            result_zper = (np.sum(dfz[i]) / np.sum(zbar)) * 100
            variable_dict[f"results_zper{j}"].append(result_zper)

    time = list(range(len(variable_dict[f"results_zper{0}"])))
    plt.figure(figsize=(10, 6))
    custom_labels = [
        "$p^{{ee}}$={0}       $b$".format(pee),
        "0",
        "10",
        "15",
        "20",
        "25",
    ]

    plt.plot([], [], " ", label=custom_labels[0])
    for i in range(5):
        if i in [0, 2, 4]:
            if i == 0:
                color = "red"
            elif i == 2:
                color = "green"
            elif i == 4:
                color = "blue"
            plt.plot(
                time,
                variable_dict[f"results_zper{i}"],
                label=custom_labels[i + 1],
                linewidth=4,
                color=color,
            )

    plt.xlabel("years", fontsize=16)
    plt.ylabel("Z(%)", fontsize=16)
    plt.xlim(0, max(time) + 2)
    plt.yticks([0, 5, 10, 15, 20], ["0", "5", "10", "15", "20"])
    plt.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.15),
        ncol=5,
        frameon=False,
        fontsize=16,
    )
    plt.savefig(
        output_folder / f"pred_zshare_{num_sites}_sites_det.png",
        format="png",
        bbox_inches="tight",
    )
    plt.close()

    plt.figure(figsize=(10, 6))
    ax = plt.gca()
    plt.plot([], [], " ", label=custom_labels[0])
    for i in range(5):
        if i in [0, 2, 4]:
            if i == 0:
                color = "red"
            elif i == 2:
                color = "green"
            elif i == 4:
                color = "blue"
            plt.plot(
                time,
                variable_dict[f"results_xagg{i}"]-variable_dict[f"results_xagg{i}"][0],
                label=custom_labels[i + 1],
                linewidth=4,
                color=color,
            )
    # move x-axis to y = 0
    ax.spines["bottom"].set_position(("data", 0))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.xaxis.set_ticks_position("bottom")
    ax.yaxis.set_ticks_position("left")
    plt.xlabel("years", fontsize=18)
    # plt.ylabel("X(billions CO2e)", fontsize=18)
    plt.ylabel("Capture (billions CO2e)", fontsize=18)
    plt.xlim(0, max(time) + 2)
    # remove the x-axis tick at 0 to avoid duplicate 0 at the origin
    xticks = ax.get_xticks()
    ax.set_xticks([10, 20, 30, 40, 50])
    plt.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.15),
        ncol=5,
        frameon=False,
        fontsize=18,
    )
    plt.savefig(
        str(output_folder) + f"/plot_pred_x_{num_sites}_sites_det.png",
        format="png",
        bbox_inches="tight",
    )
    plt.close()
    return


def _site_indices_from_ids(site_ids, num_sites):
    indices = []
    for site_id in site_ids:
        site_id = int(site_id)
        if site_id < 1 or site_id > num_sites:
            raise ValueError(f"Site id {site_id} is outside 1..{num_sites}.")
        index = site_id - 1
        if index not in indices:
            indices.append(index)
    return indices


def _density_site_ids_from_relative_entropy(num_sites, xi):
    entropy_folder = (
        get_path("output") / "figures" / "entropy" / f"site_{num_sites}" / f"xi{xi}"
    )
    selected_path = entropy_folder / "density_sites_from_relative_entropy.csv"
    if selected_path.exists():
        selected = pd.read_csv(selected_path)
        gamma_sites = selected.loc[selected["parameter"] == "gamma", "site_id"].tolist()
        theta_sites = selected.loc[selected["parameter"] == "theta", "site_id"].tolist()
        return gamma_sites, theta_sites

    kl_path = entropy_folder / "kl_divergences_theta_gamma.csv"
    if not kl_path.exists():
        return None

    kl_df = pd.read_csv(kl_path)
    gamma_sites = [
        int(kl_df.nlargest(1, "gamma_b0").iloc[0]["id"]),
        int(kl_df.nlargest(1, "gamma_b15").iloc[0]["id"]),
    ]
    theta_sites = [
        int(kl_df.nlargest(1, "theta_b0").iloc[0]["id"]),
        int(kl_df.nlargest(1, "theta_b15").iloc[0]["id"]),
    ]
    return gamma_sites, theta_sites


def density(
    pee=7.6,
    num_sites=78,
    solver="gurobi",
    pa=41.11,
    xi=1,
    pee_det=6.6,
    model="det",
    gamma_sites_to_plot=None,
    theta_sites_to_plot=None,
):
    output_folder = (
        str(get_path("output")) + f"/figures/density/site_{num_sites}/xi{xi}/"
    )
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    result_folder = os.path.join(
        str(get_path("output")),
        "sampling",
        solver,
        f"{num_sites}sites",
        f"pa_{pa}",
        f"xi_{xi}",
    )
    prior_folder = os.path.join(
        str(get_path("output")),
        "sampling",
        solver,
        f"{num_sites}sites",
        f"pa_{pa}",
        "xi_10000",
    )
    if not os.path.exists(prior_folder):
        prior_folder = os.path.join(
            str(get_path("output")),
            "sampling",
            solver,
            f"{num_sites}sites",
            "baseline",
            # f"pa_{pa}",
            # "xi_10000.0",
        )
    
    with open(result_folder + f"/pe_{pee}/results.pcl", "rb") as f:
        b0 = pickle.load(f)

    with open(result_folder + f"/pe_{pee+15}/results.pcl", "rb") as f:
        b15 = pickle.load(f)

    with open(prior_folder + f"/results.pcl", "rb") as f:
        results_unadjusted = pickle.load(f)

    # theta_unadjusted = results_unadjusted["final_sample"][:16000, :num_sites]
    # gamma_unadjusted = results_unadjusted["final_sample"][:16000, num_sites:]
    theta_unadjusted = results_unadjusted["theta"]
    gamma_unadjusted = results_unadjusted["gamma"]
    theta_adjusted_b0 = b0["final_sample"][:16000, :num_sites]
    gamma_adjusted_b0 = b0["final_sample"][:16000, num_sites:]
    theta_adjusted_b15 = b15["final_sample"][:16000, :num_sites]
    gamma_adjusted_b15 = b15["final_sample"][:16000, num_sites:]


    entropy_sites = _density_site_ids_from_relative_entropy(num_sites, xi)
    if entropy_sites is not None:
        entropy_gamma_sites, entropy_theta_sites = entropy_sites
    else:
        entropy_gamma_sites, entropy_theta_sites = None, None

    if gamma_sites_to_plot is None:
        gamma_sites_to_plot = entropy_gamma_sites or [938, 929]
    if theta_sites_to_plot is None:
        theta_sites_to_plot = entropy_theta_sites or [985, 1028]

    gamma_sites_to_plot = _site_indices_from_ids(gamma_sites_to_plot, num_sites)
    theta_sites_to_plot = _site_indices_from_ids(theta_sites_to_plot, num_sites)

    print("gamma density sites:", [idx + 1 for idx in gamma_sites_to_plot])
    print("theta density sites:", [idx + 1 for idx in theta_sites_to_plot])

    for idx in gamma_sites_to_plot:
        fig, axes = plt.subplots(1, 1, figsize=(8, 6))
        
        sns.kdeplot(
            gamma_unadjusted[:, idx],
            label="baseline",
            color="black",
            fill=False,
            alpha=0.6,
            linewidth=4,
        )  # Bright blue
        sns.kdeplot(
            gamma_adjusted_b0[:, idx],
            label="b=0",
            color="blue",
            fill=True,
            alpha=0.6,
            linewidth=4,
        )  # Bright red
        plt.title(rf"Probability density for $\gamma$ and site {idx+1}", fontsize=16)
        plt.xlabel("parameter value", fontsize=16)
        plt.ylabel("density", fontsize=16)
        plt.legend(fontsize=16)
        plt.xlim(450,650)
        file_name = os.path.join(output_folder, f"gamma_distribution_{idx+1}_b0_xi_{xi}.png")
        fig.savefig(file_name, format="png")
        plt.close()
        
        
        
        
        fig, axes = plt.subplots(1, 1, figsize=(8, 6))
        
        sns.kdeplot(
            gamma_unadjusted[:, idx],
            label="baseline",
            color="black",
            fill=False,
            alpha=0.6,
            linewidth=4,
        )  # Bright blue
        sns.kdeplot(
            gamma_adjusted_b15[:, idx],
            label="b=15",
            color="blue",
            fill=True,
            alpha=0.6,
            linewidth=4,
        )  # Bright red

        plt.title(rf"Probability density for $\gamma$ and site {idx+1}", fontsize=16)
        plt.xlabel("parameter value", fontsize=16)
        plt.ylabel("density", fontsize=16)
        plt.legend(fontsize=16)
        plt.xlim(350,550)
        file_name = os.path.join(output_folder, f"gamma_distribution_{idx+1}_b15_xi_{xi}.png")
        fig.savefig(file_name, format="png")
        plt.close()

    for idx in theta_sites_to_plot:
        print("site",idx + 1)
        fig, axes = plt.subplots(1, 1, figsize=(8, 6))

        sns.kdeplot(
            theta_unadjusted[:, idx],
            label="baseline",
            color="black",
            fill=False,
            alpha=0.6,
            linewidth=4,
        )  # Bright blue
        sns.kdeplot(
            theta_adjusted_b0[:, idx],
            label="b=0",
            color="red",
            fill=True,
            alpha=0.6,
            linewidth=4,
        )  # Bright red
        
        plt.title(rf"Probability density for $\Theta$ and site {idx+1}", fontsize=16)
        plt.xlabel("parameter value", fontsize=16)
        plt.ylabel("density", fontsize=16)
        plt.legend(fontsize=16)
        plt.xlim(0,10)
        file_name = os.path.join(output_folder, f"theta_distribution_{idx+1}_b0_xi_{xi}.png")
        fig.savefig(file_name, format="png")
        plt.close()
        
        
        
        fig, axes = plt.subplots(1, 1, figsize=(8, 6))

        sns.kdeplot(
            theta_unadjusted[:, idx],
            label="baseline",
            color="black",
            fill=False,
            alpha=0.6,
            linewidth=4,
        )  # Bright blue
        sns.kdeplot(
            theta_adjusted_b15[:, idx],
            label="b=15",
            color="red",
            fill=True,
            alpha=0.6,
            linewidth=4,
        )  # Bright red

        plt.title(rf"Probability density for $\Theta$ and site {idx+1}", fontsize=16)
        plt.xlabel("parameter value", fontsize=16)
        plt.ylabel("density", fontsize=16)
        plt.legend(fontsize=16)
        plt.xlim(1,8)
        file_name = os.path.join(output_folder, f"theta_distribution_{idx+1}_b15_xi_{xi}.png")
        fig.savefig(file_name, format="png")
        plt.close()
    return



def trajectory_diff(
    num_sites=78, pe_hmc=7.1, pe_det=5.3, b=0, solver="gams", pa=41.11, xi=1
):
    pe_hmc += b
    pe_det += b

    result_folder = os.path.join(str(get_path("output")), "optimization")
    output_folder = str(get_path("output")) + "/figures"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    df_ori = pd.read_csv(
        str(get_path("data")) + f"/calibration/calibration_{num_sites}_sites.csv"
    )
    dfz_bar = df_ori["zbar_2017"]
    dfz_bar_np = dfz_bar.to_numpy()

    dfz_hmc = np.loadtxt(
        os.path.join(
            result_folder
            + "/hmc/"
            + solver
            + f"/{num_sites}sites/xi_{xi}/pa_{pa}/pe_{pe_hmc}/",
            "Z.txt",
        ),
        delimiter=",",
    )

    dfz_zeronp_hmc = dfz_hmc
    result_zper_hmc = np.zeros((51, 1))
    result_zper_hmc = result_zper_hmc[:, 0]
    for i in range(51):
        result_zper_hmc[i] = (
            np.sum(dfz_zeronp_hmc[i]) / (np.sum(dfz_bar_np) / 1e9)
        ) * 100

    dfz_det = np.loadtxt(
        os.path.join(
            result_folder
            + "/det/"
            + solver
            + f"/{num_sites}sites/pa_{pa}/pe_{pe_det}/",
            "Z.txt",
        ),
        delimiter=",",
    )

    dfz_zeronp_det = dfz_det
    result_zper_det = np.zeros((51, 1))
    result_zper_det = result_zper_det[:, 0]
    for i in range(51):
        result_zper_det[i] = (
            np.sum(dfz_zeronp_det[i]) / (np.sum(dfz_bar_np) / 1e9)
        ) * 100

    time = list(range(0, len(result_zper_hmc)))
    plt.figure(figsize=(10, 6))

    plt.plot(time, result_zper_hmc, label=rf"$\xi$={xi}", linewidth=4, color="blue")
    plt.plot(time, result_zper_det, label=r"$\xi=\infty$", linewidth=4, color="red")
    plt.xlabel("years", fontsize=16)
    plt.ylabel("Z(%)", fontsize=16)
    plt.xlim(0, max(time) + 2)
    # if b==0:
    #     plt.ylim(12,24)
    #     if xi==0.5:
    #         plt.ylim(10, 26)
    plt.ylim(0,24)
    plt.legend(loc="upper left", ncol=5, frameon=False, fontsize=16)
    output_path = (
        output_folder
        + f"/aggregate_percentage_Z_b{b}_pehmc_{pe_hmc}_pedet_{pe_det}_xi_{xi}.png"
    )
    plt.savefig(output_path)
    plt.savefig(output_path.replace(".png", "_same_ylim.png"))
    plt.show()

    return


def plot_transfers(num_sites=1043, pee=6.6, pa=41.11, solver="gams", kappa=2.094215255):
    output_folder = get_path("output") / "figures"
    os.makedirs(output_folder, exist_ok=True)

    plt.figure(figsize=(6.4, 4.8))
    for b in [15, 25]:
        
        if b==15:
            color = "blue"
        elif b==25:
            color = "red"
        
        pe = pee + b
        result_folder = (
            get_path("output")
            / "optimization"
            / "det"
            / solver
            / f"{num_sites}sites"
            / f"pa_{pa}"
            / f"pe_{pe:g}"
        )
        missing = [
            name
            for name in ["Z.txt", "X.txt"]
            if not (result_folder / name).exists()
        ]
        if missing:
            raise FileNotFoundError(
                f"Missing deterministic optimization files {missing} in {result_folder}. "
                "Run deterministic optimization before plotting net transfers."
            )
        Z = np.loadtxt(result_folder / "Z.txt", delimiter=",")
        X = np.loadtxt(result_folder / "X.txt", delimiter=",")

        # Compute X_dot
        X_dot = np.diff(X, axis=0)

        # Compute transfers
        transfers = -b * (kappa * Z[1:] - X_dot).sum(axis=1)

        # Plotting transfers
        plt.plot(transfers[:50], label=f"b=${b}",linewidth=4,color=color)

    # Adding legend
    plt.legend()

    # Adding labels and title
    plt.xlabel("years")
    plt.ylabel("Net Transfers ($ billion)")

    # Save figure
    plt.savefig(output_folder / "net_transfers.png")
    plt.close()
