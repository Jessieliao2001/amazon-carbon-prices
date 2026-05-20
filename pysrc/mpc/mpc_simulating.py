import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd
from pysrc.replication.parameters import CarbonPriceKey, carbon_price, normalize_xi
from pysrc.services.file_service import get_path
import argparse
parser = argparse.ArgumentParser(description="mpc simulation")
parser.add_argument("--type",type=str,default="baseline")
args = parser.parse_args()
type = args.type






def mc_samples(location,p_low,p_high,price_low=35.76,price_high=44.32):
    np.random.seed(123)


    num_simulations = 50 #200

    states = {"low": price_low, "high":  price_high }
    initial_state = "high"

    probability_matrix = {
        "low": {"low": p_low, "high": 1-p_low},
        "high": {"low": 1-p_high, "high": p_high},
    }

    # Number of observations
    num_observations = 200

    for i in range(1, num_simulations + 1):
        # Generating the Markov chain for each simulation
        current_state = initial_state
        markov_chain = [states[current_state]]

        for _ in range(num_observations - 1):
            next_state = np.random.choice(
                list(probability_matrix[current_state].keys()),
                p=list(probability_matrix[current_state].values()),
            )
            markov_chain.append(states[next_state])
            current_state = next_state

        transformed_markov_chain = [
            1 if price == price_low else 2 for price in markov_chain
        ]

        # Creating an index from 1 to 200
        index = range(1, num_observations + 1)

        # Combine index and transformed Markov chain into a DataFrame
        markov_chain_df = pd.DataFrame(
            {"Index": index, "scenario": transformed_markov_chain}
        )

        # Specify the filename (e.g., mc_1.csv,..., mc_100.csv)
        csv_filename = f"/mc_{i}.csv"
        output = location
        # Output to CSV file
        markov_chain_df.to_csv(output + csv_filename, index=False)

    return "mc sampling is done"


def _mpc_pee(model, xi):
    price_model = "common_variance" if model == "constrained" else "distinct_variance"
    return carbon_price(
        CarbonPriceKey(
            context="price_stochasticity",
            model=model,
            sites=78,
            xi=xi,
            price_model=price_model,
        )
    )


def _load_converge_probabilities(model):
    path = get_path("replication", "derived", "mpc_transition_probabilities.csv")
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run `python pysrc/replication/derive_mpc_transition_probabilities.py` "
            "after generating MPC day-0 probability outputs."
        )
    df = pd.read_csv(path)
    if df.empty:
        raise RuntimeError(
            f"{path} has no transition-probability rows. Generate MPC day-0 "
            "probability outputs before running converge simulations."
        )
    df = df[df["model"] == model].copy()
    if df.empty:
        raise RuntimeError(f"{path} has no rows for model `{model}`.")

    df["xi"] = df["xi"].map(normalize_xi)
    df = df.dropna(subset=["b"])
    grouped = (
        df.groupby(["xi", "b"], as_index=False)[
            ["prob_from_low_to_low", "prob_from_high_to_high"]
        ]
        .mean()
        .sort_values(["xi", "b"])
    )

    probabilities = {}
    for _, row in grouped.iterrows():
        xi_key = float(row["xi"])
        b_key = f"b{int(round(float(row['b'])))}"
        probabilities.setdefault(xi_key, {})[b_key] = {
            "prob_ll": float(row["prob_from_low_to_low"]),
            "prob_hh": float(row["prob_from_high_to_high"]),
        }
    return probabilities






if type =="baseline":
    
    location = os.path.join(
        str(get_path("output")),
        "simulation",
        "mpc_path",
        "baseline",
        "unconstrained",
    )

    # Create the directory if it doesn't exist
    os.makedirs(location, exist_ok=True)

    # Run the simulation
    mc_samples(location=location, p_low=0.707, p_high=0.826)

    print("Mpc simulation done for baseline")




if type =="constrained":
    
    location = os.path.join(
        str(get_path("output")),
        "simulation",
        "mpc_path",
        "baseline",
        "constrained",
    )

    # Create the directory if it doesn't exist
    os.makedirs(location, exist_ok=True)

    # Run the simulation
    mc_samples(location=location, p_low=0.762, p_high=0.959,price_low=32.49,price_high=42.85)

    print("Mpc simulation done for constrained,baseline")




if type == "shadow_price":
    location1 = os.path.join(
        str(get_path("output")),
        "simulation",
        "mpc_path",
        "baseline",
        "unconstrained",
    )
    location2 = os.path.join(
        str(get_path("output")),
        "simulation",
        "mpc_path",
        "baseline",
        "constrained",
    )

    os.makedirs(location1, exist_ok=True)
    os.makedirs(location2, exist_ok=True)
    
    num_observations = 200
    index = range(1, num_observations + 1)
    
    predefined_states = [
        2, 2, 2, 2, 2, 2, 2, 2, 1, 1,
        1, 1, 1, 2, 1, 1, 2, 1, 1, 2
    ]

    transformed_markov_chain = predefined_states + [1] * (num_observations - 20)
    
    markov_chain_df = pd.DataFrame(
        {"Index": index, "scenario": transformed_markov_chain}
    )

    markov_chain_df.to_csv(location1 +  f"/mc_999.csv", index=False)
    
    
    predefined_states = [
        2, 2, 2, 2, 2, 2, 2, 2, 2, 1,
        1, 1, 1, 2, 2, 2, 2, 2, 2, 2
    ]

    transformed_markov_chain = predefined_states + [1] * (num_observations - 20)
    
    markov_chain_df = pd.DataFrame(
        {"Index": index, "scenario": transformed_markov_chain}
    )
    
    markov_chain_df.to_csv(location2 +  f"/mc_999.csv", index=False)



    transformed_markov_chain = [1] * num_observations  # All 200 years set to state 1
    markov_chain_df = pd.DataFrame( {"Index": index, "scenario": transformed_markov_chain})
    markov_chain_df.to_csv(location1 + f"/mc_997.csv", index=False)
    markov_chain_df.to_csv(location2 + f"/mc_997.csv", index=False)
    
    transformed_markov_chain = [2] * num_observations  # All 200 years set to state 1
    markov_chain_df = pd.DataFrame( {"Index": index, "scenario": transformed_markov_chain})
    markov_chain_df.to_csv(location1 + f"/mc_998.csv", index=False)
    markov_chain_df.to_csv(location2 + f"/mc_998.csv", index=False)
    
    print("MPC simulation done for shadow_price")










if type =="converge_uncon":


    xi_values = [1.0,0.5]
    b_values = [0, 10, 15, 20, 25]


    prob_dict = _load_converge_probabilities("unconstrained")


    for xi in xi_values:
        for b in b_values:
            pee = _mpc_pee("unconstrained", xi)
            pe = pee +b
            # Get the probability values for the current b value
            p_low = prob_dict[xi][f"b{b}"]["prob_ll"]
            p_high = prob_dict[xi][f"b{b}"]["prob_hh"]

            print("xi",xi,"b",b,"p_low",p_low,"p_high",p_high)

            # Define the output location
            location = os.path.join(
                str(get_path("output")),
                "simulation",
                "mpc_path",
                "unconstrained",
                f"xi_{xi}",
                f"pe_{pe}",
            )

            # Create the directory if it doesn't exist
            os.makedirs(location, exist_ok=True)

            # Run the simulation
            mc_samples(location=location, p_low=p_low, p_high=p_high)

    print("Monte Carlo simulations completed for all xi and b values. unconstrained")
    
    
    
    
    
    
    
if type =="converge_con":


    xi_values = [0.5,1.0]
    b_values = [0, 10, 15, 20, 25]


    prob_dict = _load_converge_probabilities("constrained")


    for xi in xi_values:
        for b in b_values:
            pee = _mpc_pee("constrained", xi)
            pe = pee +b
            # Get the probability values for the current b value
            p_low = prob_dict[xi][f"b{b}"]["prob_ll"]
            p_high = prob_dict[xi][f"b{b}"]["prob_hh"]

            print("xi",xi,"b",b,"p_low",p_low,"p_high",p_high)

            # Define the output location
            location = os.path.join(
                str(get_path("output")),
                "simulation",
                "mpc_path",
                "constrained",
                f"xi_{xi}",
                f"pe_{pe}",
            )

            # Create the directory if it doesn't exist
            os.makedirs(location, exist_ok=True)

            # Run the simulation
            mc_samples(location=location, p_low=p_low, p_high=p_high)

    print("Monte Carlo simulations completed for all xi and b values. constrained")
