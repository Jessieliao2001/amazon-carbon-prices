import numpy as np
import pandas as pd
from pysrc.services.file_service import get_path
import os
from pysrc.services.data_service import load_site_data
import matplotlib.pyplot as plt


solver="gurobi"
num_sites=78
xi1=10000.0
xi2=1.0
xi3=0.5
pe1=6.9
pe2=6.4
pe3=6.1


(zbar, _, _) = load_site_data(num_sites)

def read_file(result_directory):
    
    Z = np.load(os.path.join(result_directory, "Z.npy"))
    X = np.sum(np.load(os.path.join(result_directory, "X.npy")),axis=1)
    Xdot = np.diff(X, axis=0)
    U = np.load(os.path.join(result_directory, "U.npy"))
    V = np.load(os.path.join(result_directory, "V.npy"))

    return (Z / 1e2, Xdot / 1e2, U / 1e2, V / 1e2)

result_zper1=[]
result_zper2=[]
result_zper3=[]

def weighted_day0_z_path(Z, result_directory, zbar, n_years=50):
    """
    Convert Z into the day-0 expected Z percentage path.

    Z can have shape:
        (T, num_sites, 8)  new MPC format
        (T, 8)             already summed over sites
        (T, num_sites)     old non-MPC-path format

    Returns:
        Z_expected_percent with shape (n_years,)
    """

    Z = np.asarray(Z)

    # Case 1: new format, e.g. (T, sites, 8)
    if Z.ndim == 3:
        # Sum over sites, keep the 8 MPC paths.
        Z_by_path = np.sum(Z, axis=1)

    # Case 2: already summed over sites, e.g. (T, 8)
    elif Z.ndim == 2 and Z.shape[1] == 8:
        Z_by_path = Z

    # Case 3: old format, e.g. (T, sites)
    elif Z.ndim == 2:
        Z_total = np.sum(Z, axis=1)[:n_years]
        return (Z_total / np.sum(zbar)) * 100

    # Case 4: already one aggregate path
    elif Z.ndim == 1:
        Z_total = Z[:n_years]
        return (Z_total / np.sum(zbar)) * 100

    else:
        raise ValueError(f"Unexpected Z shape: {Z.shape}")

    n = min(n_years, Z_by_path.shape[0])
    Z_by_path = Z_by_path[:n, :]

    prob_df = pd.read_csv(
        os.path.join(result_directory, "distorted_worstcase_probability.csv")
    )

    p_C0_1 = float(prob_df.loc[0, "p_C0_1"])

    p_C1_1 = float(prob_df.loc[0, "p_C1_1"])
    p_C1_2 = float(prob_df.loc[0, "p_C1_2"])

    p_C2_1 = float(prob_df.loc[0, "p_C2_1"])
    p_C2_2 = float(prob_df.loc[0, "p_C2_2"])
    p_C2_3 = float(prob_df.loc[0, "p_C2_3"])
    p_C2_4 = float(prob_df.loc[0, "p_C2_4"])

    # Full 8-path probabilities from day 0.
    full_weights = np.array([
        p_C0_1 * p_C1_1 * p_C2_1,
        p_C0_1 * p_C1_1 * (1.0 - p_C2_1),
        p_C0_1 * (1.0 - p_C1_1) * p_C2_2,
        p_C0_1 * (1.0 - p_C1_1) * (1.0 - p_C2_2),
        (1.0 - p_C0_1) * p_C1_2 * p_C2_3,
        (1.0 - p_C0_1) * p_C1_2 * (1.0 - p_C2_3),
        (1.0 - p_C0_1) * (1.0 - p_C1_2) * p_C2_4,
        (1.0 - p_C0_1) * (1.0 - p_C1_2) * (1.0 - p_C2_4),
    ])

    Z_expected = np.zeros(n)

    for t in range(n):

        if t <= 1:
            # Initial/deterministic part.
            # In your printed array, columns are identical here.
            Z_expected[t] = Z_by_path[t, 0]

        elif t == 2:
            # First uncertainty split:
            # low branch representative = path 1, high branch representative = path 5.
            Z_expected[t] = (
                p_C0_1 * Z_by_path[t, 0]
                + (1.0 - p_C0_1) * Z_by_path[t, 4]
            )

        elif t == 3:
            # Second uncertainty split:
            # representatives are paths 1, 3, 5, 7.
            Z_expected[t] = (
                p_C0_1
                * (
                    p_C1_1 * Z_by_path[t, 0]
                    + (1.0 - p_C1_1) * Z_by_path[t, 2]
                )
                + (1.0 - p_C0_1)
                * (
                    p_C1_2 * Z_by_path[t, 4]
                    + (1.0 - p_C1_2) * Z_by_path[t, 6]
                )
            )

        else:
            # After the third split, use all 8 terminal MPC paths.
            Z_expected[t] = Z_by_path[t, :] @ full_weights

    # Convert to percentage of total baseline land Z.
    return Z_expected

for i in range(1):


    result_directory1 = (
        str(get_path("output"))
        + f"/optimization/mpc_day0/{solver}/{num_sites}sites/xi_{xi1}/pa_41.1/"
        + f"pe_{pe1}/mc_{i+1}/unconstrained"
    )
    result_directory2 = (
        str(get_path("output"))
        + f"/optimization/mpc_day0/{solver}/{num_sites}sites/xi_{xi2}/pa_41.1/"
        + f"pe_{pe2}/mc_{i+1}/unconstrained"
    )

    result_directory3 = (
        str(get_path("output"))
        + f"/optimization/mpc_day0/{solver}/{num_sites}sites/xi_{xi3}/pa_41.1/"
        + f"pe_{pe3}/mc_{i+1}/unconstrained"
    )
    # result_directory2 = (
    #     str(get_path("output"))
    #     + f"/optimization/mpc_worstcase/{solver}/{num_sites}sites/xi_{xi2}/pa_41.1/"
    #     + f"pe_{pe2}/mc_{i+1}/unconstrained"
    # )

    # result_directory3 = (
    #     str(get_path("output"))
    #     + f"/optimization/mpc_worstcase/{solver}/{num_sites}sites/xi_{xi3}/pa_41.1/"
    #     + f"pe_{pe3}/mc_{i+1}/unconstrained"
    # )

    (dfz_np1,_,_,_) = read_file(
        result_directory1
    )
    (dfz_np2,_,_,_) = read_file(
        result_directory2
    )

    (dfz_np3,_,_,_) = read_file(
        result_directory3
    )


    dfz_np1 = weighted_day0_z_path(dfz_np1, result_directory1, zbar, n_years=50)
    dfz_np2 = weighted_day0_z_path(dfz_np2, result_directory2, zbar, n_years=50)
    dfz_np3 = weighted_day0_z_path(dfz_np3, result_directory3, zbar, n_years=50)
    print(dfz_np1)

    result_zper1.append((dfz_np1/ np.sum(zbar)) * 100)
    result_zper2.append((dfz_np2/ np.sum(zbar)) * 100)
    result_zper3.append((dfz_np3/ np.sum(zbar)) * 100)



result_zper1=np.mean(np.array(result_zper1),axis=0)
result_zper2=np.mean(np.array(result_zper2),axis=0)
result_zper3=np.mean(np.array(result_zper3),axis=0)


time = np.arange(len(result_zper1))
output_folder = str(get_path("output"))
plt.figure()

plt.plot(time, result_zper1*100,linewidth=4,color = 'red', label=r"$\widehat{\xi}=\infty$")
plt.plot(time, result_zper2*100,linewidth=4,color = 'blue', label=r"$\widehat{\xi}=1$")
plt.plot(time, result_zper3*100,linewidth=4,color = 'green', label=r"$\widehat{\xi}=0.5$")

plt.ylabel("Z(%)")
plt.xlabel("years")
# plt.ylim(19.3,19.7)
plt.xlim(0,50)
plt.legend()
plt.savefig(os.path.join(output_folder, f"figures/mpc_landallocation_b_{0}_adjust"))
plt.show()