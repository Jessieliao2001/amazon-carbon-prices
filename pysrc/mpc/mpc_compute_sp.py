import os
import pickle

import numpy as np
import pandas as pd

from pysrc.services.data_service import load_productivity_params
from pysrc.services.file_service import get_path
from pysrc.services.data_service import load_site_data_1995,load_price_data

def format_float(value):
    return f"{value:.3f}"


def read_theta(num_sites):

    (theta_vals, gamma_vals) = load_productivity_params(num_sites)
    return theta_vals


def read_file(result_directory):
    required_files = ["Z.txt", "X.txt", "U.txt", "V.txt"]
    missing = [
        filename
        for filename in required_files
        if not os.path.exists(os.path.join(result_directory, filename))
    ]
    if missing:
        raise FileNotFoundError(
            f"Missing MPC shadow-price optimization output(s) {missing} in "
            f"{result_directory}. Run `./run.sh --steps mpc-sp-grid --backend local` "
            "locally, or `./run.sh --steps mpc-sp-grid --backend slurm "
            "--slurm-account <account>` on the server, before `mpc-prices`."
        )

    Z = np.loadtxt(os.path.join(result_directory, "Z.txt"), delimiter=",")
    X = np.sum(np.loadtxt(os.path.join(result_directory, "X.txt"), delimiter=","),axis=1)
    Xdot = np.diff(X, axis=0)
    U = np.loadtxt(os.path.join(result_directory, "U.txt"), delimiter=",")
    V = np.loadtxt(os.path.join(result_directory, "V.txt"), delimiter=",")

    return (Z / 1e2, Xdot / 1e2, U / 1e2, V / 1e2)


def mpc_sp(pee=5.9, num_sites=78, solver="gurobi", model="unconstrained", b=0,xi=10000):
    pe = pee + b
    mc_id=999
    
    
    (
        zbar_1995,
        z_1995,
        forest_area_1995,
        z_2008,
        theta,
        gamma,
    ) = load_site_data_1995(num_sites)


        
    result_directory = (
        str(get_path("output"))
        + f"/optimization/mpc_shadow_price/{solver}/{num_sites}sites/xi_{xi}/pa_41.11/"
        + f"pe_{pe}/mc_{mc_id}/"+f"{model}"
    )

    (dfz_np, dfxdot, dfu_np, dfv_np) = read_file(
        result_directory
    )


    Z = dfz_np
    z_2008_agg = np.sum(z_2008) / 1e11
    ratio = (np.sum(Z[13]) - z_2008_agg) / z_2008_agg

    return ratio


def main():
    for xi in (0.5, 1.0, 10000.0):
        for pe in np.linspace(5.0, 7.0, num=21):
            print("xi",xi,"pe",pe,"model unconstrained")
            print("ratio",mpc_sp(pee=pe,num_sites=78,b=0,xi=xi,model="unconstrained"))
            print("------------------------------")

    for xi in (0.5, 1.0, 10000.0):
        for pe in np.linspace(5.0, 7.0, num=21):
            print("xi",xi,"pe",pe,"model constrained")
            print("ratio",mpc_sp(pee=pe,num_sites=78,b=0,xi=xi,model="constrained"))
            print("------------------------------")


if __name__ == "__main__":
    main()
