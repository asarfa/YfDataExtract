"""Light analytics on price tables (dates x tickers)."""

from __future__ import annotations

import numpy as np
import pandas as pd

PERIODS_PER_YEAR = {"1d": 252, "5d": 52, "1wk": 52, "1mo": 12, "3mo": 4}


def rebase(prices: pd.DataFrame, base: float = 100.0) -> pd.DataFrame:
    """Rebase every column to `base` at its first valid value."""
    return prices.apply(lambda s: s / s.dropna().iloc[0] * base if s.notna().any() else s)


def drawdown(prices: pd.DataFrame) -> pd.DataFrame:
    return prices / prices.cummax() - 1


def perf_stats(prices: pd.DataFrame, interval: str = "1d") -> pd.DataFrame:
    """Total return, CAGR, annualised vol, Sharpe (rf=0), max drawdown per column."""
    ppy = PERIODS_PER_YEAR.get(interval)
    rows = {}
    for col in prices.columns:
        s = prices[col].dropna()
        if len(s) < 2:
            continue
        rets = s.pct_change().dropna()
        total = s.iloc[-1] / s.iloc[0] - 1
        row = {"Début": s.index[0], "Fin": s.index[-1], "Perf totale": total}
        if ppy:
            years = len(rets) / ppy
            vol = rets.std() * np.sqrt(ppy)
            cagr = (1 + total) ** (1 / years) - 1 if years > 0 else np.nan
            row |= {"Perf annualisée": cagr, "Vol annualisée": vol, "Sharpe (rf=0)": cagr / vol if vol else np.nan}
        row["Max drawdown"] = (s / s.cummax() - 1).min()
        rows[col] = row
    return pd.DataFrame(rows).T
