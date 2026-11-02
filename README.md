# YfDataExtract

Extraire **toutes les données accessibles via Yahoo Finance** (bibliothèque [`yfinance`](https://github.com/ranaroussi/yfinance)) sous forme de `pandas.DataFrame`, et les exporter en CSV / Parquet / JSON / Excel.

Python **3.12+**, géré avec [`uv`](https://docs.astral.sh/uv/).

## Installation

```bash
git clone https://github.com/asarfa/YfDataExtract.git
cd YfDataExtract
uv sync                      # crée .venv en Python 3.12 et installe les dépendances
uv sync --extra xlsx         # optionnel : export Excel
```

## Ce qu'on peut extraire

**Par ticker** (`TickerExtractor`, 50 datasets, `yfdx datasets` pour la liste complète) :

| Catégorie | Datasets |
|---|---|
| `meta` | info, fast_info, isin, history_metadata |
| `prices` | history (max, OHLCV + Adj Close), dividends, splits, actions, capital_gains, shares_full |
| `fundamentals` | income_stmt / balance_sheet / cash_flow (annuel, trimestriel, TTM), valuation_measures |
| `analysts` | earnings_dates, earnings_history, earnings/revenue estimate, eps_trend, eps_revisions, growth_estimates, analyst_price_targets, recommendations, upgrades_downgrades |
| `holders` | major / institutional / mutualfund holders, insider transactions / purchases / roster |
| `events` | calendar, sec_filings, news, sustainability (ESG) |
| `options` | toutes les chaînes (calls + puts, toutes échéances) |
| `funds` | ETF / OPCVM : top holdings, poids sectoriels, classes d'actifs, stats actions/obligations, notations, frais |

**Marché** (`yfdataextract.markets`) : `download` (multi-tickers), `search`, `lookup` (par type d'actif), `screen` (19 screeners prédéfinis ou requêtes `EquityQuery`/`FundQuery`/`ETFQuery`), `market` (statut et indices d'une place), `sector`, `industry`, `calendars` (résultats, événements éco, IPO, splits).

Selon le type d'actif, certains datasets n'existent pas (ex. pas d'options sur une action européenne, pas de `funds` sur une action) : l'extraction **continue** et les erreurs sont listées dans `result.errors` / `_summary.csv`.

## Python

```python
import yfdataextract as yfx

tx = yfx.TickerExtractor("MC.PA")
tx.get("income_stmt")
tx.history(period="5y", interval="1wk")

res = tx.extract(categories=["prices", "fundamentals", "analysts"])
res.summary                      # statut par dataset
yfx.save_frames(res.data, "data/MC.PA", fmt="parquet")

closes = yfx.download(["AAPL", "MSFT", "^FCHI"], period="10y", field="Close")
yfx.screen("day_gainers", size=50)
yfx.sector("technology")["top_companies"]
yfx.lookup("amundi", kind="etf")
```

Requête de screener personnalisée :

```python
from yfinance import EquityQuery
q = EquityQuery("and", [EquityQuery("eq", ["region", "fr"]), EquityQuery("gt", ["intradaymarketcap", 10e9])])
yfx.screen(q, size=100)
```

## Ligne de commande

```bash
uv run yfdx datasets
uv run yfdx ticker AAPL MC.PA -o data -f parquet          # tout, un dossier par ticker
uv run yfdx ticker AAPL -c fundamentals analysts -o data
uv run yfdx download AAPL MSFT ^FCHI --period 10y --field Close -o data
uv run yfdx history SPY --interval 1h --period 1mo
uv run yfdx options SPY --max-expirations 3 -o data
uv run yfdx screen                    # liste des screeners
uv run yfdx screen most_actives
uv run yfdx search "LVMH"
uv run yfdx lookup amundi --kind etf
uv run yfdx market FR
uv run yfdx sector technology -o data
uv run yfdx calendar --start 2026-11-01 --end 2026-11-30
```

## Tests

```bash
uv run pytest        # hors ligne : yfinance est simulé
```

## Limites

- Yahoo Finance n'a pas d'API officielle : les données peuvent changer de forme, être limitées en débit ou temporairement indisponibles. Usage personnel / recherche ; respecter les conditions d'utilisation de Yahoo.
- L'intraday est limité par Yahoo (1m : 7 derniers jours ; < 1d : 60 jours ; 1h : 730 jours).
