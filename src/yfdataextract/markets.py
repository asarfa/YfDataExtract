"""Cross-ticker / market-wide Yahoo Finance data: bulk prices, search, screeners, sectors, calendars."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
import yfinance as yf

from ._utils import to_frame

PREDEFINED_SCREENS: tuple[str, ...] = tuple(yf.PREDEFINED_SCREENER_QUERIES)

LOOKUP_TYPES = ("all", "stock", "etf", "mutualfund", "index", "future", "currency", "cryptocurrency")

SECTORS = (
    "basic-materials", "communication-services", "consumer-cyclical", "consumer-defensive",
    "energy", "financial-services", "healthcare", "industrials", "real-estate",
    "technology", "utilities",
)


def download(
    tickers: str | Sequence[str],
    period: str | None = "1y",
    interval: str = "1d",
    start=None,
    end=None,
    auto_adjust: bool = False,
    field: str | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Prix de plusieurs tickers en une requête.

    ``field`` (ex. "Close", "Adj Close", "Volume") renvoie un tableau dates x tickers.
    """
    if isinstance(tickers, str):
        tickers = tickers.replace(",", " ").split()
    params = dict(interval=interval, auto_adjust=auto_adjust, progress=False, threads=True, **kwargs)
    if start or end:
        df = yf.download(list(tickers), start=start, end=end, **params)
    else:
        df = yf.download(list(tickers), period=period, **params)
    if df is None:
        return pd.DataFrame()
    if field:
        df = df[field]
        if isinstance(df, pd.Series):
            df = df.to_frame(tickers[0])
    return df


def search(query: str, max_results: int = 20, news_count: int = 10) -> dict[str, pd.DataFrame]:
    """Recherche plein texte: renvoie {"quotes", "news", "lists", "research"}."""
    s = yf.Search(query, max_results=max_results, news_count=news_count, include_research=True)
    return {
        "quotes": to_frame(s.quotes),
        "news": to_frame(s.news),
        "lists": to_frame(s.lists),
        "research": to_frame(s.research),
    }


def lookup(query: str, kind: str = "all", count: int = 25) -> pd.DataFrame:
    """Recherche de symboles par type d'actif (stock, etf, mutualfund, index, future, currency, cryptocurrency)."""
    if kind not in LOOKUP_TYPES:
        raise ValueError(f"kind doit être dans {LOOKUP_TYPES}")
    lk = yf.Lookup(query)
    return to_frame(getattr(lk, f"get_{kind}")(count=count))


def screen(query: str | yf.EquityQuery | yf.FundQuery | yf.ETFQuery, size: int = 100, **kwargs) -> pd.DataFrame:
    """Screener Yahoo: nom prédéfini (voir PREDEFINED_SCREENS) ou requête EquityQuery/FundQuery/ETFQuery."""
    if isinstance(query, str):
        if query not in PREDEFINED_SCREENS:
            raise ValueError(f"Screen inconnu: {query!r}. Valides: {PREDEFINED_SCREENS}")
        # les screens prédéfinis acceptent `count` (max 250) et non `size`
        res = yf.screen(query, count=min(size, 250), **kwargs)
    else:
        res = yf.screen(query, size=size, **kwargs)
    return to_frame(res.get("quotes", []) if isinstance(res, dict) else res)


def market(region: str = "US") -> dict[str, pd.DataFrame]:
    """Statut (ouvert/fermé) et résumé (indices principaux) d'une place: US, GB, FR, DE, JP, ..."""
    m = yf.Market(region)
    summary = m.summary
    if isinstance(summary, dict) and summary and all(isinstance(v, dict) for v in summary.values()):
        summary = pd.DataFrame(summary).T
    return {"status": to_frame(m.status), "summary": to_frame(summary)}


def sector(key: str) -> dict[str, pd.DataFrame]:
    """Données d'un secteur Yahoo (clé type 'technology', voir SECTORS)."""
    s = yf.Sector(key)
    return {
        "overview": to_frame(s.overview),
        "top_companies": to_frame(s.top_companies),
        "top_etfs": to_frame(s.top_etfs),
        "top_mutual_funds": to_frame(s.top_mutual_funds),
        "industries": to_frame(s.industries),
        "research_reports": to_frame(s.research_reports),
    }


def industry(key: str) -> dict[str, pd.DataFrame]:
    """Données d'une industrie Yahoo (clé type 'semiconductors', listée dans sector(...)['industries'])."""
    i = yf.Industry(key)
    return {
        "overview": to_frame(i.overview),
        "top_companies": to_frame(i.top_companies),
        "top_growth_companies": to_frame(i.top_growth_companies),
        "top_performing_companies": to_frame(i.top_performing_companies),
        "research_reports": to_frame(i.research_reports),
    }


def calendars(start=None, end=None, limit: int = 100) -> dict[str, pd.DataFrame]:
    """Calendriers de marché: résultats, événements économiques, IPO, splits."""
    c = yf.Calendars(start=start, end=end)
    out: dict[str, pd.DataFrame] = {}
    for name, fn in {
        "earnings": c.get_earnings_calendar,
        "economic_events": c.get_economic_events_calendar,
        "ipo": c.get_ipo_info_calendar,
        "splits": c.get_splits_calendar,
    }.items():
        try:
            out[name] = to_frame(fn(limit=limit))
        except Exception as exc:
            out[name] = pd.DataFrame({"error": [f"{type(exc).__name__}: {exc}"]})
    return out
