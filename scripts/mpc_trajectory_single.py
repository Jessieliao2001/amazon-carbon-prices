import numpy as np
from pysrc.services.file_service import get_path
import os
from pysrc.services.data_service import load_site_data
import matplotlib.pyplot as plt

solver = "gurobi"
num_sites = 78
xi1 = 10000.0
xi2 = 1.0
xi3 = 0.5
pe1 = 6.9
pe2 = 6.9
pe3 = 6.9

target_i = 1     
site_idx = 34     

(zbar, _, _) = load_site_data(num_sites)

def read_file(result_directory):
    Z = np.loadtxt(os.path.join(result_directory, "Z.txt"), delimiter=",")
    X = np.sum(np.loadtxt(os.path.join(result_directory, "X.txt"), delimiter=","), axis=1)
    Xdot = np.diff(X, axis=0)
    U = np.loadtxt(os.path.join(result_directory, "U.txt"), delimiter=",")
    V = np.loadtxt(os.path.join(result_directory, "V.txt"), delimiter=",")

    return (Z / 1e2, Xdot / 1e2, U / 1e2, V / 1e2)

result_directory1 = (
    str(get_path("output"))
    + f"/optimization/mpc/{solver}/{num_sites}sites/xi_{xi1}/pa_41.1/"
    + f"pe_{pe1}/mc_{target_i}/unconstrained"
)

result_directory2 = (
    str(get_path("output"))
    + f"/optimization/mpc_worstcase/{solver}/{num_sites}sites/xi_{xi2}/pa_41.1/"
    + f"pe_{pe2}/mc_{target_i}/unconstrained"
)

result_directory3 = (
    str(get_path("output"))
    + f"/optimization/mpc_worstcase/{solver}/{num_sites}sites/xi_{xi3}/pa_41.1/"
    + f"pe_{pe3}/mc_{target_i}/unconstrained"
)

(dfz_np1, _, _, _) = read_file(result_directory1)
(dfz_np2, _, _, _) = read_file(result_directory2)
(dfz_np3, _, _, _) = read_file(result_directory3)

# 不再对78个site求和，只取单个site
dfz_np1 = dfz_np1[:50, site_idx]
dfz_np2 = dfz_np2[:50, site_idx]
dfz_np3 = dfz_np3[:50, site_idx]

result_zper1 = (dfz_np1 / zbar[site_idx]) * 100
result_zper2 = (dfz_np2 / zbar[site_idx]) * 100
result_zper3 = (dfz_np3 / zbar[site_idx]) * 100

time = list(range(len(dfz_np1)))
output_folder = str(get_path("output"))

plt.figure()
plt.plot(time, result_zper1, linewidth=4, color='red', label=r"$\widehat{\xi}=\infty$")
plt.plot(time, result_zper2, linewidth=4, color='green', label=r"$\widehat{\xi}=1$")
plt.plot(time, result_zper3, linewidth=4, color='blue', label=r"$\widehat{\xi}=0.5$")

plt.ylabel("Z(%)")
plt.xlabel("years")
# plt.ylim(0.25, 0.5)
plt.xlim(0, 50)
plt.legend()
plt.savefig(os.path.join(output_folder, f"figures/mpc_landallocation_mc_{target_i}_site_{site_idx+1}"))
plt.show()