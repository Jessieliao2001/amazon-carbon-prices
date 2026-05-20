from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from pysrc.services.file_service import get_path


INFINITY_XI = "inf"
CARBON_PRICE_FILE = get_path("replication", "derived", "carbon_prices.csv")


def normalize_xi(value: object) -> str:
    """Normalize xi labels without confusing the infinity case with the number 8."""
    text = str(value).strip().lower()
    if text in {"inf", "infty", "infinite", "infinity", r"\infty", "∞"}:
        return INFINITY_XI
    try:
        number = float(text)
    except ValueError:
        return text
    if number >= 9999:
        return INFINITY_XI
    if number.is_integer():
        return str(int(number))
    return f"{number:g}"


def xi_for_filename(value: object) -> str:
    normalized = normalize_xi(value)
    return "10000.0" if normalized == INFINITY_XI else f"{float(normalized):.1f}"


def xi_for_label(value: object) -> str:
    normalized = normalize_xi(value)
    return r"\infty" if normalized == INFINITY_XI else normalized


def load_carbon_prices(path: Path | str | None = None) -> pd.DataFrame:
    price_path = Path(path) if path else CARBON_PRICE_FILE
    if not price_path.exists():
        raise FileNotFoundError(
            f"Missing {price_path}. Run `python pysrc/replication/derive_carbon_prices.py` "
            "after the shadow-price/MPC shadow-price jobs have produced logs."
        )
    df = pd.read_csv(price_path)
    if "xi" not in df.columns or "pee" not in df.columns:
        raise ValueError(f"{price_path} must contain at least columns `xi` and `pee`.")
    df = df.copy()
    df["xi"] = df["xi"].map(normalize_xi)
    return df


@dataclass(frozen=True)
class CarbonPriceKey:
    context: str
    model: str
    sites: int | None = None
    xi: object = INFINITY_XI
    price_model: str | None = None


def carbon_price(key: CarbonPriceKey, path: Path | str | None = None) -> float:
    df = load_carbon_prices(path)
    mask = (df["context"] == key.context) & (df["model"] == key.model)
    if key.sites is not None and "sites" in df.columns:
        mask &= df["sites"].fillna(-1).astype(int) == int(key.sites)
    if "xi" in df.columns:
        mask &= df["xi"] == normalize_xi(key.xi)
    if key.price_model is not None and "price_model" in df.columns:
        mask &= df["price_model"].fillna("") == key.price_model

    matches = df.loc[mask]
    if matches.empty:
        available = df[
            [c for c in ["context", "model", "sites", "xi", "price_model", "pee"] if c in df]
        ].to_dict("records")
        raise KeyError(f"No carbon price for {key}. Available keys: {available}")
    if len(matches) > 1:
        matches = matches.sort_values(["abs_metric", "pee"], na_position="last")
    return float(matches.iloc[0]["pee"])


def carbon_prices_for_xis(
    context: str,
    model: str,
    xis: Iterable[object],
    sites: int | None = None,
    price_model: str | None = None,
    path: Path | str | None = None,
) -> dict[str, float]:
    prices: dict[str, float] = {}
    for xi in xis:
        prices[normalize_xi(xi)] = carbon_price(
            CarbonPriceKey(
                context=context,
                model=model,
                sites=sites,
                xi=xi,
                price_model=price_model,
            ),
            path=path,
        )
    return prices

