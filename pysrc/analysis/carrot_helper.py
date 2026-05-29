"""
Helper functions for the carrot-policy time-consistency analysis.

The fund balance B_t is compared against cooperative continuation values V_t
and defection values W_t to identify the first year of planner defection.
"""

from __future__ import annotations

from typing import Optional

import numpy as np


def _as_2d(array: np.ndarray) -> np.ndarray:
    """Return a 1D or 2D array as a 2D NumPy array."""
    arr = np.asarray(array, dtype=float)
    if arr.ndim == 1:
        return arr.reshape(-1, 1)
    if arr.ndim != 2:
        raise ValueError(f"Expected a 1D or 2D array, got shape {arr.shape}.")
    return arr


def compute_fund_balance(
    X: np.ndarray,
    Z: np.ndarray,
    bf: float,
    tau_f: int,
    delta: float = 0.02,
    kappa: float = 2.094215255,
) -> list[float]:
    """Compute fund balances B_t for dates t = 0, ..., T.

    Deposits use the carbon change X[t+1] - X[t] and end-of-period land Z[t+1].
    The balance earns interest only before tau_f.
    """
    X_arr = _as_2d(X)
    Z_arr = _as_2d(Z)

    if tau_f < 0:
        raise ValueError(f"tau_f must be non-negative, got {tau_f}.")
    if Z_arr.shape[0] < X_arr.shape[0]:
        raise ValueError("Z must have at least as many time rows as X.")

    n_periods = X_arr.shape[0] - 1
    growth = float(np.exp(delta))

    # Period deposits: bf * sum_i[(X_{t+1,i} - X_{t,i}) - kappa * Z_{t+1,i}].
    carbon_change = np.diff(X_arr, axis=0).sum(axis=1)
    land_penalty = kappa * Z_arr[1 : n_periods + 1].sum(axis=1)
    deposits = bf * (carbon_change - land_penalty)

    B = np.zeros(n_periods + 1, dtype=float)
    for t, deposit in enumerate(deposits):
        interest_adjusted_balance = growth * B[t] if t < tau_f else B[t]
        B[t + 1] = interest_adjusted_balance + deposit

    return B.tolist()


def first_defection_year_given_tau(
    X: np.ndarray,
    Z: np.ndarray,
    V: list[float],
    W: list[float],
    bf: float,
    tau: int,
) -> Optional[int]:
    """Return the first year t where W[t] - B[t] > V[t], or None."""
    B = compute_fund_balance(X=X, Z=Z, bf=bf, tau_f=tau)

    for t, (v_t, w_t, b_t) in enumerate(zip(V, W, B)):
        if w_t - b_t > v_t:
            return t
    return None


def defection_years_by_tau(
    X: np.ndarray,
    Z: np.ndarray,
    V: list[float],
    W: list[float],
    bf: float,
    max_tau: Optional[int] = None,
) -> dict[int, Optional[int]]:
    """Map each tau in [0, max_tau] to its first defection year."""
    if max_tau is None:
        max_tau = len(W) - 1
    if max_tau < 0:
        return {}

    return {
        tau: first_defection_year_given_tau(X=X, Z=Z, V=V, W=W, bf=bf, tau=tau)
        for tau in range(max_tau + 1)
    }
