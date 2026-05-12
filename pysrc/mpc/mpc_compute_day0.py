import os
import numpy as np
import pandas as pd
import sys
from pathlib import Path
from pysrc.services.data_service import load_productivity_params
from pysrc.services.file_service import get_path

def format_float(value):
    return f"{value:.2f}"


def read_theta(num_sites):

    (theta_vals, gamma_vals) = load_productivity_params(num_sites)
    return theta_vals


def read_file(result_directory):
    
    Z = np.loadtxt(os.path.join(result_directory, "Z.txt"), delimiter=",")
    X = np.sum(np.loadtxt(os.path.join(result_directory, "X.txt"), delimiter=","),axis=1)
    Xdot = np.diff(X, axis=0)
    U = np.loadtxt(os.path.join(result_directory, "U.txt"), delimiter=",")
    V = np.loadtxt(os.path.join(result_directory, "V.txt"), delimiter=",")

    return (Z / 1e2, Xdot / 1e2, U / 1e2, V / 1e2)


# def value_decom_mpc(pee=5.9, num_sites=78, solver="gurobi", model="unconstrained", b=0,xi=10000,mode=None,price_low=35.76,price_high = 44.25):
#     pe = pee + b
#     kappa = 2.094215255
#     zeta_u = 1.66e-4 * 1e11
#     zeta_v = 1.00e-4 * 1e11

    
#     dft_np = read_theta(num_sites)

#     output_folder = str(get_path("output")) + "/mpc/"
#     if not os.path.exists(output_folder):
#         os.makedirs(output_folder)

#     results = []
#     for j in range(0):
        
        
#         if mode =="converge":
#             if price_low == 32.49:
#                 pa_file_path = (
#                     get_path("output", "simulation", "mpc_path","constrained",f"xi_{xi}",f"pe_{pe}") / f"mc_{j+1}.csv"
#                 ) 
#             else:
#                 pa_file_path = (
#                     get_path("output", "simulation", "mpc_path","unconstrained",f"xi_{xi}",f"pe_{pe}") / f"mc_{j+1}.csv"
#                 ) 
#         else:
#             pa_file_path = (
#                 get_path("output", "simulation", "mpc_path","baseline",f"{model}") / f"mc_{j+1}.csv"
#             ) 

#         p_a_values = np.array(pd.read_csv(pa_file_path))[:,1]
#         p_a_values = np.where(p_a_values == 2, price_high, price_low)
        
#         if mode =="converge":
#             result_directory = (
#                 str(get_path("output"))
#                 + f"/optimization/mpc_worstcase/{solver}/{num_sites}sites/xi_{xi}/pa_41.1/"
#                 + f"pe_{pe}/mc_{j+1}/{model}"
#             )            
            
#         else:
#             result_directory = (
#                 str(get_path("output"))
#                 + f"/optimization/mpc/{solver}/{num_sites}sites/xi_{xi}/pa_41.1/"
#                 + f"pe_{pe}/mc_{j+1}/{model}"
#             )

#         (dfz_np, dfxdot, dfu_np, dfv_np) = read_file(
#             result_directory
#         )


#         results_AO = []
#         for i in range(200):
#             result_AO = p_a_values[i] * np.dot(dfz_np[i + 1], dft_np) / ((1 + 0.02) ** (i))
#             results_AO.append(result_AO)
#         total_AO = np.sum(results_AO)

#         results_NT = []
#         for i in range(200):
#             result_NT = (
#                 -b
#                 * (kappa * np.sum(dfz_np[i + 1]) - dfxdot[i])
#                 / ((1 + 0.02) ** (i))
#             )
#             results_NT.append(result_NT)
#         total_NT = np.sum(results_NT)

#         results_CS = []
#         for i in range(200):
#             result_CS = (
#                 -pee * (kappa * np.sum(dfz_np[i + 1]) - dfxdot[i]) / ((1 + 0.02) ** (i))
#             )
#             results_CS.append(result_CS)
#         total_CS = np.sum(results_CS)

#         results_AC = []
#         for i in range(200):
#             result_AC = (
#                 ((zeta_u / 2)
#                 * (np.sum(dfu_np[i]) ) ** 2
#                 +
#                 (zeta_v / 2)
#                 * (np.sum(dfv_np[i]) ) ** 2
#                 )
#                 / ((1 + 0.02) ** (i))
#             )
#             results_AC.append(result_AC)
#         total_AC = np.sum(results_AC)

#         total_PV = total_AO + total_NT + total_CS - total_AC

#         iteration_results = {
#             "j": j + 1,
#             "b": b,
#             "total_AO": total_AO,
#             "total_NT": total_NT,
#             "total_CS": total_CS,
#             "total_AC": total_AC,
#             "total_PV": total_PV,
#         }

#         results.append(iteration_results)

#     results_df = pd.DataFrame(results)

#     mean = results_df.mean()
#     sd = results_df.std()
#     sd / mean

#     summary_table_df = pd.DataFrame(
#         {
#             "  ":  f"b = {b}",
#             "agricultural output value": [format_float(mean["total_AO"])],
#             "net transfers": [format_float(mean["total_NT"])],
#             "forest services": [format_float(mean["total_CS"])],
#             "adjustment costs": [format_float(mean["total_AC"])],
#             "planner value": [format_float(mean["total_PV"])],
#         }
#     )


#     if mode =="converge":
#         with open(output_folder + f"converge_present_value_mpc_b{b}_sites{num_sites}_xi_{xi}_pee_{pee}_{model}.tex", "w") as file:
#             file.write(summary_table_df.to_latex(index=False))
#     else:
#         with open(output_folder + f"present_value_mpc_b{b}_sites{num_sites}_xi_{xi}_pee_{pee}_{model}.tex", "w") as file:
#             file.write(summary_table_df.to_latex(index=False))

#     return print("done")


def value_decom_mpc(pee=5.9, num_sites=78, solver="gurobi", model="unconstrained", b=0,xi=10000,mode=None,price_low=35.76,price_high = 44.25):
    pe = pee + b
    kappa = 2.094215255
    zeta_u = 1.66e-4 * 1e9
    zeta_v = 1.00e-4 * 1e9

    
    dft_np = read_theta(num_sites)

    output_folder = str(get_path("output")) + "/mpc/"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    def reconstruct_objective_Ct0(
        Z,
        X,
        U,
        V,
        pa,
        theta,
        prob_df,
        pee,
        b,
        kappa,
        zeta_u,
        zeta_v,
        delta=0.02,
        dt=1.0,
    ):
        """
        Reconstructs object_value_C_t0 and decomposes it into:

            agri       = pa[t,j] * sum_s theta[s] * z[t+1,s,j]
            forest     = -pe * sum_s (kappa*z[t+1,s,j] - xdot[t,s,j])
            adjustment = -(zeta_u/2)*w1[t,j]^2 - (zeta_v/2)*w2[t,j]^2

        where:
            w1[t,j] = sum_s U[t,s,j]
            w2[t,j] = sum_s V[t,s,j]
        """

        Z = np.asarray(Z)
        X = np.asarray(X)
        U = np.asarray(U)
        V = np.asarray(V)
        pa = np.asarray(pa)
        theta = np.asarray(theta).reshape(-1)

        print("Z shape:", Z.shape)
        print("X shape:", X.shape)
        print("U shape:", U.shape)
        print("V shape:", V.shape)
        print("pa shape:", pa.shape)
        print("theta shape:", theta.shape)

        # distorted probabilities
        p_C0_1 = float(prob_df.loc[0, "p_C0_1"])

        p_C1_1 = float(prob_df.loc[0, "p_C1_1"])
        p_C1_2 = float(prob_df.loc[0, "p_C1_2"])

        p_C2_1 = float(prob_df.loc[0, "p_C2_1"])
        p_C2_2 = float(prob_df.loc[0, "p_C2_2"])
        p_C2_3 = float(prob_df.loc[0, "p_C2_3"])
        p_C2_4 = float(prob_df.loc[0, "p_C2_4"])

        exp_delta = np.exp(-delta)

        component_names = ["agri", "forest", "net_transfer", "adjustment"]

        def zero_components():
            return {name: 0.0 for name in component_names}

        def add_components(a, b):
            return {name: a[name] + b[name] for name in component_names}

        def scale_components(weight, comp):
            return {name: weight * comp[name] for name in component_names}

        def weighted_sum_components(weight_comp_pairs):
            out = zero_components()
            for weight, comp in weight_comp_pairs:
                for name in component_names:
                    out[name] += weight * comp[name]
            return out

        def total_from_components(comp):
            return sum(comp[name] for name in component_names)

        def compute_flow_components_np(t, j):
            """
            t and j are Pyomo-style 1-based indices.
            """

            t_idx = t - 1
            tp1_idx = t      # t+1 in Pyomo maps to index t in NumPy
            j_idx = j - 1

            z_tp1 = Z[tp1_idx, :, j_idx]
            x_t = X[t_idx, :, j_idx]
            x_tp1 = X[tp1_idx, :, j_idx]

            xdot = (x_tp1 - x_t) / dt

            w1_tj = np.sum(U[t_idx, :, j_idx])
            w2_tj = np.sum(V[t_idx, :, j_idx])

            nt_term = np.sum(kappa * z_tp1 - xdot)
            ao_term = np.sum(theta * z_tp1)

            agri = pa[t_idx, j_idx] * ao_term

            forest = -pee * nt_term

            net_transfer = -b * nt_term

            adjustment = (
                - (zeta_u / 2.0) * (w1_tj ** 2)
                - (zeta_v / 2.0) * (w2_tj ** 2)
            )

            # Optional diagnostic check:
            # This should match the original combined term: -pe * nt_term
            combined_forest_nt = forest + net_transfer
            original_combined_term = -pe * nt_term

            if abs(combined_forest_nt - original_combined_term) > 1e-6:
                print("Warning: forest + net_transfer does not equal -pe * nt_term")
                print("t:", t, "j:", j)
                print("forest + net_transfer:", combined_forest_nt)
                print("-pe * nt_term:", original_combined_term)
                print("difference:", combined_forest_nt - original_combined_term)

            return {
                "agri": agri,
                "forest": forest,
                "net_transfer": net_transfer,
                "adjustment": adjustment,
            }

        # ============================================================
        # C_t3 component values
        # Pyomo: t in model.T if t < max(model.T) and t > 3
        # With model.T = 1,...,201, this means t = 4,...,200
        # ============================================================

        object_value_C_t3_components = {}

        for j in range(1, 9):
            acc = zero_components()

            for t in range(4, 201):
                discount = np.exp(-delta * (t * dt - 4 * dt))
                flow_comp = compute_flow_components_np(t, j)

                for name in component_names:
                    acc[name] += discount * flow_comp[name] * dt

            object_value_C_t3_components[j] = scale_components(
                1.0 - exp_delta,
                acc,
            )

        # ============================================================
        # C_t2 component values
        # ============================================================

        state_C2_C3_mapping = {
            1: [1, 2],
            2: [1, 2],
            3: [3, 4],
            4: [3, 4],
            5: [5, 6],
            6: [5, 6],
            7: [7, 8],
            8: [7, 8],
        }

        state_C2_C3_prob = {
            1: p_C2_1,
            2: 1.0 - p_C2_1,
            3: p_C2_2,
            4: 1.0 - p_C2_2,
            5: p_C2_3,
            6: 1.0 - p_C2_3,
            7: p_C2_4,
            8: 1.0 - p_C2_4,
        }

        object_value_C_t2_components = {}

        for j in range(1, 9):
            current_flow_comp = compute_flow_components_np(3, j)

            continuation_comp = weighted_sum_components(
                [
                    (
                        state_C2_C3_prob[mapping],
                        object_value_C_t3_components[mapping],
                    )
                    for mapping in state_C2_C3_mapping[j]
                ]
            )

            object_value_C_t2_components[j] = add_components(
                scale_components(1.0 - exp_delta, current_flow_comp),
                scale_components(exp_delta, continuation_comp),
            )

        # ============================================================
        # C_t1 component values
        # ============================================================

        state_C1_C2_prob = {
            1: p_C1_1,
            2: p_C1_1,
            3: 1.0 - p_C1_1,
            4: 1.0 - p_C1_1,
            5: p_C1_2,
            6: p_C1_2,
            7: 1.0 - p_C1_2,
            8: 1.0 - p_C1_2,
        }

        object_value_C_t1_unique_components = {}

        # Low branch at C_t1
        current_flow_comp_0 = compute_flow_components_np(2, 1)

        continuation_comp_0 = weighted_sum_components(
            [
                (state_C1_C2_prob[j], object_value_C_t2_components[j])
                for j in [1, 3]
            ]
        )

        object_value_C_t1_unique_components[0] = add_components(
            scale_components(1.0 - exp_delta, current_flow_comp_0),
            scale_components(exp_delta, continuation_comp_0),
        )

        # High branch at C_t1
        current_flow_comp_1 = compute_flow_components_np(2, 5)

        continuation_comp_1 = weighted_sum_components(
            [
                (state_C1_C2_prob[j], object_value_C_t2_components[j])
                for j in [5, 7]
            ]
        )

        object_value_C_t1_unique_components[1] = add_components(
            scale_components(1.0 - exp_delta, current_flow_comp_1),
            scale_components(exp_delta, continuation_comp_1),
        )

        # ============================================================
        # C_t0 component value
        # ============================================================

        current_flow_comp_t0 = compute_flow_components_np(1, 1)

        continuation_comp_t0 = weighted_sum_components(
            [
                (p_C0_1, object_value_C_t1_unique_components[0]),
                (1.0 - p_C0_1, object_value_C_t1_unique_components[1]),
            ]
        )

        object_value_C_t0_components = add_components(
            scale_components(1.0 - exp_delta, current_flow_comp_t0),
            scale_components(exp_delta, continuation_comp_t0),
        )

        object_value_C_t0 = total_from_components(object_value_C_t0_components)

        # Check decomposition
        decomposition_sum = (
            object_value_C_t0_components["agri"]
            + object_value_C_t0_components["forest"]
            + object_value_C_t0_components["net_transfer"]
            + object_value_C_t0_components["adjustment"]
        )

        decomposition_error = decomposition_sum - object_value_C_t0

        return object_value_C_t0, object_value_C_t0_components, {
            "object_value_C_t3_components": object_value_C_t3_components,
            "object_value_C_t2_components": object_value_C_t2_components,
            "object_value_C_t1_unique_components": object_value_C_t1_unique_components,
            "decomposition_sum": decomposition_sum,
            "decomposition_error": decomposition_error,
        }



    def reconstruct_pa_array(
        time_horizon,
        price_low=35.71,
        price_high=44.25,
        pa_current=2,   # 1 = low, 2 = high
    ):
        J = 8
        T = time_horizon + 1   # because model.T = RangeSet(time_horizon + 1)

        pa = np.zeros((T, J))

        for t in range(1, T + 1):      # Pyomo t: 1,...,T
            for j in range(1, J + 1):  # Pyomo j: 1,...,8

                if t == 1:
                    pa_value = price_low if pa_current == 1 else price_high

                elif t == 2:
                    if j in [1, 2, 3, 4]:
                        pa_value = price_low
                    else:
                        pa_value = price_high

                elif t == 3:
                    if j in [1, 2] or j in [5, 6]:
                        pa_value = price_low
                    else:
                        pa_value = price_high

                elif t == 4:
                    if j in [1, 3, 5, 7]:
                        pa_value = price_low
                    else:
                        pa_value = price_high

                else:
                    if j in [1, 3, 5, 7]:
                        pa_value = price_low
                    else:
                        pa_value = price_high

                pa[t - 1, j - 1] = pa_value

        return pa

    pa = reconstruct_pa_array(
        time_horizon=200,
        price_low=price_low,
        price_high=price_high,
        pa_current=2,   # initial high
    )
        
    result_directory = (
        str(get_path("output"))
        + f"/optimization/mpc_day0/{solver}/{num_sites}sites/xi_{xi}/pa_41.1/"
        + f"pe_{pe}/mc_{1}/{model}"
    )
    result_directory = Path(result_directory)

    Z = np.load(result_directory / "Z.npy")
    X = np.load(result_directory / "X.npy")
    U = np.load(result_directory / "U.npy")
    V = np.load(result_directory / "V.npy")

    prob_df = pd.read_csv( os.path.join(result_directory, "distorted_worstcase_probability.csv"))

    Ct0, Ct0_decomp, details = reconstruct_objective_Ct0(
        Z=Z,
        X=X,
        U=U,
        V=V,
        pa=pa,
        theta=dft_np,
        prob_df=prob_df,
        pee=pee,
        b=b,
        kappa=kappa,
        zeta_u=zeta_u,
        zeta_v=zeta_v,
        delta=0.02,
        dt=1.0,
    )

    check_sum = (
        Ct0_decomp["agri"]
        + Ct0_decomp["forest"]
        + Ct0_decomp["net_transfer"]
        + Ct0_decomp["adjustment"]
    )

    scale = 1 - np.exp(-0.02)

    print("========================================")
    print(f"xi={xi},b={b},model={model}")
    print("Reconstructed Ct0:", Ct0)
    print("Check sum:", check_sum)
    print("Difference:", check_sum - Ct0)

    print("Reconstructed Ct0 exp:", Ct0 / scale)
    print("Agri exp:", Ct0_decomp["agri"] / scale)
    print("Net transfer exp:", Ct0_decomp["net_transfer"] / scale)
    print("Forest exp:", Ct0_decomp["forest"] / scale)
    print("Adjustment exp:", Ct0_decomp["adjustment"] / scale)

    return 

for b in [0,15,10,25]:    
    value_decom_mpc(pee=6.7,num_sites=78,b=b,xi=10000.0)
    # value_decom_mpc(pee=6.9,num_sites=78,b=b,xi=10000.0)
    # value_decom_mpc(pee=6.4,num_sites=78,b=b,xi=1.0)
    # value_decom_mpc(pee=6.1,num_sites=78,b=b,xi=0.5)


# for b in [0]:
#     value_decom_mpc(pee=6.9,num_sites=78,b=b,xi=10000.0)
#     value_decom_mpc(pee=6.9,num_sites=78,b=b,xi=1.0)
#     value_decom_mpc(pee=6.9,num_sites=78,b=b,xi=0.5)
# for b in [0]:
#     value_decom_mpc(pee=6.9,num_sites=78,b=b,xi=10000.0)
#     value_decom_mpc(pee=6.4,num_sites=78,b=b,xi=1.0)
#     value_decom_mpc(pee=6.1,num_sites=78,b=b,xi=0.5)
# for b in [0]:
#     value_decom_mpc(pee=6.9,num_sites=78,b=b,xi=10000.0)
#     value_decom_mpc(pee=6.9,num_sites=78,b=b,xi=1.0,mode="converge")
#     value_decom_mpc(pee=6.9,num_sites=78,b=b,xi=0.5,mode="converge")
# for b in [0,10,15,25]:
#     value_decom_mpc(pee=6.9,num_sites=78,b=b,xi=10000.0)
#     value_decom_mpc(pee=6.4,num_sites=78,b=b,xi=1.0,mode="converge")
#     value_decom_mpc(pee=6.1,num_sites=78,b=b,xi=0.5,mode="converge")



# # ####### Appendix tables

# for b in [0,10,15,20,25]:
#     value_decom_mpc(pee=6.6,num_sites=78,b=b,xi=10000.0,model="constrained",price_low=32.49,price_high = 42.85)
#     value_decom_mpc(pee=6.2,num_sites=78,b=b,xi=1.0,mode="converge",model="constrained",price_low=32.49,price_high = 42.85)
#     value_decom_mpc(pee=5.6,num_sites=78,b=b,xi=0.5,mode="converge",model="constrained",price_low=32.49,price_high = 42.85)
    
# for b in [0,10,15,20,25]:
#     value_decom_mpc(pee=6.6,num_sites=78,b=b,xi=10000.0,model="constrained",price_low=32.49,price_high = 42.85)
#     value_decom_mpc(pee=6.2,num_sites=78,b=b,xi=1.0,model="constrained",price_low=32.49,price_high = 42.85)
#     value_decom_mpc(pee=5.6,num_sites=78,b=b,xi=0.5,model="constrained",price_low=32.49,price_high = 42.85)
    

    
    
    
    
    
    
    
# def transfer_cost_mpc(pee=5.9, y=30,num_sites=78, solver="gurobi", model="unconstrained", b=0,xi=10000,mode=None,price_low=35.76,price_high = 44.25):
#     kappa = 2.094215255
#     pe = pee + b

#     output_folder = str(get_path("output")) + "/mpc/"
#     if not os.path.exists(output_folder):
#         os.makedirs(output_folder)

#     results = []
#     for j in range(49):
        
#         if mode =="converge":
#             result_directory = (
#                 str(get_path("output"))
#                 + f"/optimization/mpc_worstcase/{solver}/{num_sites}sites/xi_{xi}/pa_41.1/"
#                 + f"pe_{pe}/mc_{j+1}/{model}"
#             )            
#             baseline_folder = (
#                 str(get_path("output"))
#                 + f"/optimization/mpc_worstcase/{solver}/{num_sites}sites/xi_{xi}/pa_41.1/"
#                 + f"pe_{pee}/mc_{j+1}/{model}"
#             )            
#         else:
#             result_directory = (
#                 str(get_path("output"))
#                 + f"/optimization/mpc/{solver}/{num_sites}sites/xi_{xi}/pa_41.1/"
#                 + f"pe_{pe}/mc_{j+1}/{model}"
#             )
#             baseline_folder = (
#                 str(get_path("output"))
#                 + f"/optimization/mpc/{solver}/{num_sites}sites/xi_{xi}/pa_41.1/"
#                 + f"pe_{pee}/mc_{j+1}/{model}"
#             )

#         (dfz_np, dfxdot, dfu_np, dfv_np) = read_file(baseline_folder)

#         results_NCE_base = []
#         for i in range(y):
#             result_NCE_base = -kappa * np.sum(dfz_np[i + 1]) + dfxdot[i]
#             results_NCE_base.append(result_NCE_base)
#         total_NCE_base = np.sum(results_NCE_base) * 100

#         (dfz_np, dfxdot, dfu_np, dfv_np) = read_file(
#             result_directory
#         )
    

#         results_NCE = []
#         for i in range(y):
#             result_NCE = -kappa * np.sum(dfz_np[i + 1]) + dfxdot[i]
#             results_NCE.append(result_NCE)
#         total_NCE = np.sum(results_NCE) * 100

#         results_NT2 = []
#         for i in range(y):
#             result_NT2 = (
#                 -b
#                 * (kappa * np.sum(dfz_np[i + 1]) - dfxdot[i])
#                 / ((1 + 0.02) ** (i))
#             )

#             results_NT2.append(result_NT2)
#         total_NT2 = np.sum(results_NT2)

#         total_EC = total_NT2 / (total_NCE - total_NCE_base) * 100

#         iteration_results = {
#             "j": j + 1,
#             "b": b,
#             "NCE": total_NCE,
#             "NT2": total_NT2,
#             "EC": total_EC,
#         }

#         results.append(iteration_results)

#     results_df = pd.DataFrame(results)

#     mean = results_df.mean()
#     sd = results_df.std()
#     sd / mean

#     summary_table_df = pd.DataFrame(
#         {
#             "  ":  f"b = {b}",
#             "net captured emissions": [format_float(mean["NCE"])],
#             "discounted net transfers": [format_float(mean["NT2"])],
#             "discounted effective costs": [format_float(mean["EC"])],
#         }
#     )


#     if mode =="converge":
#         with open(output_folder + f"converge_transfer_mpc_b{b}_sites{num_sites}_xi_{xi}_pee_{pee}_{model}.tex", "w") as file:
#             file.write(summary_table_df.to_latex(index=False))
#     else:
#         with open(output_folder + f"transfer_mpc_b{b}_sites{num_sites}_xi_{xi}_pee_{pee}_{model}.tex", "w") as file:
#             file.write(summary_table_df.to_latex(index=False))

#     return print("done")


# for b in [0,10,15,25]:
#     transfer_cost_mpc(pee=6.3,num_sites=78,b=b,xi=10000.0)
    
# for b in [0,10,15,25]:
#     transfer_cost_mpc(pee=5.7,num_sites=78,b=b,xi=1.0,mode="converge")
    
# for b in [0,10,15,25]:
#     transfer_cost_mpc(pee=5.5,num_sites=78,b=b,xi=0.2,mode="converge")










