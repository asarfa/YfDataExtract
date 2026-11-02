"""Per-ticker extraction: every dataset yfinance exposes for one symbol, behind one interface."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

import pandas as pd
import yfinance as yf

from ._utils import to_frame

log = logging.getLogger(__name__)

Getter = Callable[[yf.Ticker], object]


@dataclass(frozen=True)
class Dataset:
    name: str
    category: str
    getter: Getter
    description: str


def _fund(attr: str) -> Getter:
    return lambda t: getattr(t.funds_data, attr)


def _options(t: yf.Ticker, max_expirations: int | None = None) -> pd.DataFrame:
    expirations = list(t.options or [])
    if max_expirations is not None:
        expirations = expirations[:max_expirations]
    frames = []
    for exp in expirations:
        chain = t.option_chain(exp)
        for kind, df in (("call", chain.calls), ("put", chain.puts)):
            if df is not None and not df.empty:
                frames.append(df.assign(expiration=exp, option_type=kind))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


_D = Dataset
DATASETS: dict[str, Dataset] = {
    d.name: d
    for d in [
        # --- meta
        _D("info", "meta", lambda t: t.info, "Profil complet (secteur, ratios, description, chiffres clés)"),
        _D("fast_info", "meta", lambda t: t.fast_info, "Sous-ensemble rapide: dernier prix, market cap, devise..."),
        _D("isin", "meta", lambda t: t.isin, "Code ISIN"),
        _D("history_metadata", "meta", lambda t: (t.history(period="5d"), t.history_metadata)[1], "Métadonnées de cotation (place, fuseau, devise)"),
        # --- prices & corporate actions
        _D("history", "prices", lambda t: t.history(period="max", auto_adjust=False, actions=True), "Historique OHLCV quotidien complet (non ajusté + Adj Close)"),
        _D("dividends", "prices", lambda t: t.dividends, "Dividendes versés"),
        _D("splits", "prices", lambda t: t.splits, "Divisions d'actions"),
        _D("actions", "prices", lambda t: t.actions, "Dividendes + splits"),
        _D("capital_gains", "prices", lambda t: t.capital_gains, "Distributions de plus-values (fonds)"),
        _D("shares_full", "prices", lambda t: t.get_shares_full(start="1990-01-01"), "Historique du nombre d'actions"),
        # --- fundamentals
        _D("income_stmt", "fundamentals", lambda t: t.income_stmt, "Compte de résultat annuel"),
        _D("quarterly_income_stmt", "fundamentals", lambda t: t.quarterly_income_stmt, "Compte de résultat trimestriel"),
        _D("ttm_income_stmt", "fundamentals", lambda t: t.ttm_income_stmt, "Compte de résultat 12 mois glissants"),
        _D("balance_sheet", "fundamentals", lambda t: t.balance_sheet, "Bilan annuel"),
        _D("quarterly_balance_sheet", "fundamentals", lambda t: t.quarterly_balance_sheet, "Bilan trimestriel"),
        _D("cash_flow", "fundamentals", lambda t: t.cash_flow, "Flux de trésorerie annuels"),
        _D("quarterly_cash_flow", "fundamentals", lambda t: t.quarterly_cash_flow, "Flux de trésorerie trimestriels"),
        _D("ttm_cash_flow", "fundamentals", lambda t: t.ttm_cash_flow, "Flux de trésorerie 12 mois glissants"),
        _D("valuation_measures", "fundamentals", lambda t: t.get_valuation_measures(), "Multiples de valorisation historiques"),
        # --- analysts
        _D("earnings_dates", "analysts", lambda t: t.get_earnings_dates(limit=100), "Dates de résultats passées/futures, BPA estimé vs publié"),
        _D("earnings_history", "analysts", lambda t: t.earnings_history, "Historique des surprises de BPA"),
        _D("earnings_estimate", "analysts", lambda t: t.earnings_estimate, "Consensus BPA"),
        _D("revenue_estimate", "analysts", lambda t: t.revenue_estimate, "Consensus chiffre d'affaires"),
        _D("eps_trend", "analysts", lambda t: t.eps_trend, "Évolution du consensus BPA"),
        _D("eps_revisions", "analysts", lambda t: t.eps_revisions, "Révisions de BPA à la hausse/baisse"),
        _D("growth_estimates", "analysts", lambda t: t.growth_estimates, "Estimations de croissance"),
        _D("analyst_price_targets", "analysts", lambda t: t.analyst_price_targets, "Objectifs de cours (bas/moyen/haut)"),
        _D("recommendations", "analysts", lambda t: t.recommendations, "Répartition des recommandations par mois"),
        _D("recommendations_summary", "analysts", lambda t: t.recommendations_summary, "Synthèse des recommandations"),
        _D("upgrades_downgrades", "analysts", lambda t: t.upgrades_downgrades, "Historique relèvements / abaissements"),
        # --- holders
        _D("major_holders", "holders", lambda t: t.major_holders, "Répartition insiders / institutionnels"),
        _D("institutional_holders", "holders", lambda t: t.institutional_holders, "Principaux détenteurs institutionnels"),
        _D("mutualfund_holders", "holders", lambda t: t.mutualfund_holders, "Principaux fonds détenteurs"),
        _D("insider_transactions", "holders", lambda t: t.insider_transactions, "Transactions des dirigeants"),
        _D("insider_purchases", "holders", lambda t: t.insider_purchases, "Synthèse achats/ventes des dirigeants"),
        _D("insider_roster_holders", "holders", lambda t: t.insider_roster_holders, "Liste des dirigeants détenteurs"),
        # --- events & misc
        _D("calendar", "events", lambda t: t.calendar, "Prochains événements (résultats, dividende)"),
        _D("sec_filings", "events", lambda t: t.sec_filings, "Dépôts SEC (US)"),
        _D("news", "events", lambda t: t.get_news(count=50), "Dernières actualités"),
        _D("sustainability", "events", lambda t: t.sustainability, "Scores ESG"),
        # --- options
        _D("options", "options", _options, "Toutes les chaînes d'options (calls + puts, toutes échéances)"),
        # --- funds / ETF
        _D("fund_description", "funds", _fund("description"), "Description du fonds"),
        _D("fund_overview", "funds", _fund("fund_overview"), "Catégorie, famille, style"),
        _D("fund_operations", "funds", _fund("fund_operations"), "Frais, encours, rotation"),
        _D("fund_top_holdings", "funds", _fund("top_holdings"), "Principales lignes"),
        _D("fund_sector_weightings", "funds", _fund("sector_weightings"), "Poids sectoriels"),
        _D("fund_asset_classes", "funds", _fund("asset_classes"), "Allocation par classe d'actifs"),
        _D("fund_equity_holdings", "funds", _fund("equity_holdings"), "Statistiques de la poche actions (PER, P/B...)"),
        _D("fund_bond_holdings", "funds", _fund("bond_holdings"), "Statistiques de la poche obligataire (duration, maturité)"),
        _D("fund_bond_ratings", "funds", _fund("bond_ratings"), "Répartition par notation"),
    ]
}

CATEGORIES: tuple[str, ...] = tuple(dict.fromkeys(d.category for d in DATASETS.values()))


@dataclass
class ExtractionResult:
    symbol: str
    data: dict[str, pd.DataFrame] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def summary(self) -> pd.DataFrame:
        rows = [{"dataset": k, "status": "ok", "rows": len(v), "cols": v.shape[1]} for k, v in self.data.items()]
        rows += [{"dataset": k, "status": "error", "error": e} for k, e in self.errors.items()]
        return pd.DataFrame(rows)


def list_datasets(category: str | None = None) -> pd.DataFrame:
    rows = [
        {"name": d.name, "category": d.category, "description": d.description}
        for d in DATASETS.values()
        if category is None or d.category == category
    ]
    return pd.DataFrame(rows)


class TickerExtractor:
    """Wraps ``yf.Ticker`` and returns every dataset as a DataFrame.

    >>> tx = TickerExtractor("AAPL")
    >>> tx.get("income_stmt")
    >>> res = tx.extract(categories=["prices", "fundamentals"])
    """

    def __init__(self, symbol: str, session=None):
        self.symbol = symbol.upper()
        self.ticker = yf.Ticker(self.symbol, session=session) if session else yf.Ticker(self.symbol)

    def get(self, name: str, **kwargs) -> pd.DataFrame:
        if name not in DATASETS:
            raise KeyError(f"Dataset inconnu: {name!r}. Voir list_datasets().")
        return to_frame(DATASETS[name].getter(self.ticker, **kwargs))

    def history(self, period: str = "1y", interval: str = "1d", start=None, end=None, **kwargs) -> pd.DataFrame:
        """Historique de prix paramétrable (intervalles 1m..3mo, périodes 1d..max)."""
        if start or end:
            return self.ticker.history(start=start, end=end, interval=interval, **kwargs)
        return self.ticker.history(period=period, interval=interval, **kwargs)

    def options(self, max_expirations: int | None = None) -> pd.DataFrame:
        return _options(self.ticker, max_expirations)

    def extract(
        self,
        datasets: Iterable[str] | None = None,
        categories: Iterable[str] | None = None,
        skip_empty: bool = True,
    ) -> ExtractionResult:
        """Extrait plusieurs datasets; une erreur sur l'un n'interrompt pas les autres."""
        names = self._select(datasets, categories)
        res = ExtractionResult(self.symbol)
        for name in names:
            try:
                df = self.get(name)
            except Exception as exc:  # Yahoo renvoie souvent 404 / champs absents selon le type d'actif
                log.info("%s/%s: %s", self.symbol, name, exc)
                res.errors[name] = f"{type(exc).__name__}: {exc}"
                continue
            if skip_empty and df.empty:
                continue
            res.data[name] = df
        return res

    @staticmethod
    def _select(datasets: Iterable[str] | None, categories: Iterable[str] | None) -> list[str]:
        if datasets:
            names = list(datasets)
            unknown = [n for n in names if n not in DATASETS]
            if unknown:
                raise KeyError(f"Datasets inconnus: {unknown}")
            return names
        cats = set(categories) if categories else set(CATEGORIES)
        unknown = cats - set(CATEGORIES)
        if unknown:
            raise KeyError(f"Catégories inconnues: {sorted(unknown)}. Valides: {CATEGORIES}")
        return [d.name for d in DATASETS.values() if d.category in cats]
