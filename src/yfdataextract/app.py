"""Streamlit interface for YfDataExtract.

Lancement : ``uv run yfdx-app`` (ou ``uv run streamlit run src/yfdataextract/app.py``).
"""

from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from yfdataextract import markets as mk
from yfdataextract.analytics import drawdown, perf_stats, rebase
from yfdataextract.export import FORMATS, save_frames
from yfdataextract.ticker import CATEGORIES, DATASETS, TickerExtractor, list_datasets

# Categorical palette, fixed order (colour follows the series' position in the user's list).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
UP, DOWN = "#1baf7a", "#eb6834"
MAX_SERIES = len(SERIES)
TTL = 900  # secondes de cache pour les appels Yahoo

CATEGORY_LABELS = {
    "meta": "Profil", "prices": "Prix & opérations", "fundamentals": "Fondamentaux",
    "analysts": "Analystes", "holders": "Détenteurs", "events": "Événements",
    "options": "Options", "funds": "Fonds / ETF",
}
PERIODS = ["1mo", "3mo", "6mo", "ytd", "1y", "2y", "5y", "10y", "max"]
INTERVALS = ["1d", "1wk", "1mo", "1h", "30m", "15m", "5m", "1m"]

st.set_page_config(page_title="YfDataExtract", page_icon="📈", layout="wide")


# ---------------------------------------------------------------- helpers
def _layout(fig: go.Figure, height: int = 420, yfmt: str | None = None) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=32, b=8), hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridwidth=1, zeroline=False, tickformat=yfmt)
    return fig


def _csv_button(df: pd.DataFrame, name: str, key: str) -> None:
    st.download_button("⬇ CSV", df.to_csv().encode(), f"{name}.csv", "text/csv", key=key)


def _show(df: pd.DataFrame, name: str, key: str) -> None:
    st.caption(f"{len(df)} lignes × {df.shape[1]} colonnes")
    st.dataframe(df, width="stretch")
    _csv_button(df, name, key)


def _zip(frames: dict[str, pd.DataFrame], fmt: str) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        paths = save_frames(frames, tmp, fmt)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for p in paths:
                z.write(p, Path(p).name)
    return buf.getvalue()


def _tickers(text: str) -> list[str]:
    return list(dict.fromkeys(t.strip().upper() for t in text.replace(",", " ").split() if t.strip()))


def _error(exc: Exception) -> None:
    st.error(f"Yahoo Finance n'a pas répondu correctement : {type(exc).__name__}: {exc}")


# ---------------------------------------------------------------- cached Yahoo calls
@st.cache_data(ttl=TTL, show_spinner=False)
def c_extract(symbol: str, names: tuple[str, ...]):
    res = TickerExtractor(symbol).extract(datasets=list(names))
    return res.data, res.errors, res.summary


@st.cache_data(ttl=TTL, show_spinner=False)
def c_history(symbol: str, period: str, interval: str) -> pd.DataFrame:
    return TickerExtractor(symbol).history(period=period, interval=interval, auto_adjust=False)


@st.cache_data(ttl=TTL, show_spinner=False)
def c_download(tickers: tuple[str, ...], period, interval, start, end, field) -> pd.DataFrame:
    return mk.download(list(tickers), period=period, interval=interval, start=start, end=end, field=field)


@st.cache_data(ttl=TTL, show_spinner=False)
def c_expirations(symbol: str) -> list[str]:
    return list(TickerExtractor(symbol).ticker.options or [])


@st.cache_data(ttl=TTL, show_spinner=False)
def c_chain(symbol: str, expiration: str):
    ch = TickerExtractor(symbol).ticker.option_chain(expiration)
    return ch.calls, ch.puts


c_search = st.cache_data(ttl=TTL, show_spinner=False)(mk.search)
c_lookup = st.cache_data(ttl=TTL, show_spinner=False)(mk.lookup)
c_screen = st.cache_data(ttl=TTL, show_spinner=False)(mk.screen)
c_market = st.cache_data(ttl=TTL, show_spinner=False)(mk.market)
c_sector = st.cache_data(ttl=TTL, show_spinner=False)(mk.sector)
c_industry = st.cache_data(ttl=TTL, show_spinner=False)(mk.industry)
c_calendars = st.cache_data(ttl=TTL, show_spinner=False)(mk.calendars)


# ---------------------------------------------------------------- pages
def page_ticker() -> None:
    st.header("Fiche ticker")
    c1, c2 = st.columns([1, 3])
    symbol = c1.text_input("Ticker Yahoo", "AAPL", help="Ex. AAPL, MC.PA, ^FCHI, EURUSD=X, BTC-USD, IWDA.AS").strip().upper()
    cats = c2.multiselect(
        "Catégories", CATEGORIES, default=[c for c in CATEGORIES if c != "options"],
        format_func=lambda c: CATEGORY_LABELS.get(c, c),
        help="Les options sont lourdes à extraire : voir la page Options.",
    )
    if not symbol:
        return

    # price chart (independent of the bulk extraction)
    p1, p2, _ = st.columns([1, 1, 4])
    period = p1.selectbox("Période", PERIODS, index=PERIODS.index("1y"))
    interval = p2.selectbox("Intervalle", INTERVALS)
    try:
        hist = c_history(symbol, period, interval)
    except Exception as exc:
        _error(exc)
        hist = pd.DataFrame()
    if hist.empty:
        st.warning(f"Pas d'historique pour {symbol} sur cette période / cet intervalle.")
    else:
        last, first = hist["Close"].iloc[-1], hist["Close"].iloc[0]
        m1, m2, m3 = st.columns(3)
        m1.metric("Dernier cours", f"{last:,.2f}", f"{last / first - 1:+.2%} sur la période")
        m2.metric("Plus haut période", f"{hist['High'].max():,.2f}")
        m3.metric("Plus bas période", f"{hist['Low'].min():,.2f}")
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.75, 0.25], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(
            x=hist.index, open=hist["Open"], high=hist["High"], low=hist["Low"], close=hist["Close"], name=symbol,
            increasing=dict(line=dict(color=UP, width=1), fillcolor=UP),
            decreasing=dict(line=dict(color=DOWN, width=1), fillcolor=DOWN),
        ), row=1, col=1)
        fig.add_trace(go.Bar(x=hist.index, y=hist["Volume"], name="Volume", marker_color=SERIES[0]), row=2, col=1)
        fig.update_layout(xaxis_rangeslider_visible=False, showlegend=False)
        if interval == "1d":
            fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
        st.plotly_chart(_layout(fig, 520), width="stretch")

    st.divider()
    if st.button(f"Extraire toutes les données de {symbol}", type="primary"):
        names = tuple(d.name for d in DATASETS.values() if d.category in cats)
        with st.spinner(f"Extraction de {len(names)} datasets..."):
            st.session_state["extract"] = (symbol, *c_extract(symbol, names))

    if "extract" not in st.session_state or st.session_state["extract"][0] != symbol:
        st.info("Choisis les catégories puis lance l'extraction.")
        return
    _, data, errors, summary = st.session_state["extract"]
    st.success(f"{len(data)} datasets récupérés, {len(errors)} indisponibles pour ce ticker.")

    e1, e2 = st.columns([1, 4])
    fmt = e1.selectbox("Format", FORMATS, key="zipfmt")
    e2.download_button(
        f"⬇ Tout télécharger ({fmt}, zip)", _zip({**data, "_summary": summary}, fmt),
        f"{symbol}_{fmt}.zip", "application/zip",
    )

    present = [c for c in cats if any(DATASETS[n].category == c for n in data)]
    if present:
        for tab, cat in zip(st.tabs([CATEGORY_LABELS.get(c, c) for c in present]), present):
            with tab:
                for name, df in data.items():
                    if DATASETS[name].category != cat:
                        continue
                    with st.expander(f"**{name}** — {DATASETS[name].description}", expanded=False):
                        _show(df, f"{symbol}_{name}", key=f"dl_{name}")
    with st.expander("Récapitulatif et erreurs"):
        st.dataframe(summary, width="stretch")


def page_prices() -> None:
    st.header("Comparer des prix")
    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
    tickers = _tickers(c1.text_input("Tickers (séparés par des espaces ou virgules)", "AAPL MSFT ^GSPC ^FCHI"))
    period = c2.selectbox("Période", PERIODS, index=PERIODS.index("5y"))
    interval = c3.selectbox("Intervalle", ["1d", "1wk", "1mo"])
    field = c4.selectbox("Champ", ["Adj Close", "Close", "Open", "High", "Low", "Volume"])
    o1, o2, o3 = st.columns(3)
    view = o1.radio("Affichage", ["Base 100", "Prix", "Drawdown"], horizontal=True)
    log = o2.toggle("Échelle log", value=False, disabled=view == "Drawdown")
    if not tickers:
        return
    if len(tickers) > MAX_SERIES:
        st.warning(f"Graphique limité aux {MAX_SERIES} premiers tickers (le tableau contient tout).")
    try:
        with st.spinner("Téléchargement..."):
            px = c_download(tuple(tickers), period, interval, None, None, field)
    except Exception as exc:
        _error(exc)
        return
    if px.empty:
        st.warning("Aucune donnée renvoyée.")
        return
    px = px[[t for t in tickers if t in px.columns]]
    missing = [t for t in tickers if t not in px.columns or px[t].isna().all()]
    if missing:
        st.warning(f"Sans données : {', '.join(missing)}")

    if field == "Volume":
        plot, yfmt = px, None
    elif view == "Base 100":
        plot, yfmt = rebase(px), None
    elif view == "Drawdown":
        plot, yfmt = drawdown(px), ".0%"
    else:
        plot, yfmt = px, None
    fig = go.Figure()
    for i, t in enumerate(plot.columns[:MAX_SERIES]):
        s = plot[t].dropna()
        fig.add_trace(go.Scatter(x=s.index, y=s, name=t, mode="lines", line=dict(color=SERIES[i], width=2)))
    if log and view != "Drawdown":
        fig.update_yaxes(type="log")
    st.plotly_chart(_layout(fig, 480, yfmt), width="stretch")

    if field != "Volume":
        st.subheader("Statistiques")
        stats = perf_stats(px, interval)
        pct = [c for c in stats.columns if c not in ("Début", "Fin", "Sharpe (rf=0)")]
        st.dataframe(
            stats.style.format({**{c: "{:.2%}" for c in pct}, "Sharpe (rf=0)": "{:.2f}",
                                "Début": "{:%Y-%m-%d}", "Fin": "{:%Y-%m-%d}"}, na_rep="–"),
            width="stretch",
        )
    with st.expander("Données"):
        _show(px, f"prix_{field}", "dl_prices")


def page_options() -> None:
    st.header("Options")
    symbol = st.text_input("Sous-jacent", "SPY").strip().upper()
    if not symbol:
        return
    try:
        exps = c_expirations(symbol)
    except Exception as exc:
        _error(exc)
        return
    if not exps:
        st.warning(f"Pas d'options listées sur Yahoo pour {symbol}.")
        return
    exp = st.selectbox("Échéance", exps)
    calls, puts = c_chain(symbol, exp)
    fig = go.Figure()
    for i, (name, df) in enumerate((("Calls", calls), ("Puts", puts))):
        d = df[df["impliedVolatility"] > 0.001]
        fig.add_trace(go.Scatter(x=d["strike"], y=d["impliedVolatility"], name=name, mode="lines+markers",
                                 line=dict(color=SERIES[i], width=2), marker=dict(size=8)))
    st.subheader(f"Smile de volatilité implicite — {symbol} {exp}")
    fig.update_layout(xaxis_title="Strike")
    st.plotly_chart(_layout(fig, 420, ".0%"), width="stretch")
    t1, t2 = st.tabs(["Calls", "Puts"])
    with t1:
        _show(calls, f"{symbol}_{exp}_calls", "dl_calls")
    with t2:
        _show(puts, f"{symbol}_{exp}_puts", "dl_puts")


def page_search() -> None:
    st.header("Recherche de symboles")
    c1, c2 = st.columns([3, 1])
    q = c1.text_input("Nom, ISIN ou mot-clé", "LVMH")
    kind = c2.selectbox("Type d'actif", mk.LOOKUP_TYPES)
    if not q:
        return
    try:
        res = c_search(q, max_results=25)
        lk = c_lookup(q, kind, 50)
    except Exception as exc:
        _error(exc)
        return
    tabs = st.tabs(["Résultats", f"Lookup ({kind})", "Actualités", "Listes", "Recherche"])
    for tab, (name, df) in zip(tabs, [("quotes", res["quotes"]), ("lookup", lk), ("news", res["news"]),
                                     ("lists", res["lists"]), ("research", res["research"])]):
        with tab:
            if df.empty:
                st.info("Aucun résultat.")
            else:
                _show(df, f"search_{name}", f"dl_s_{name}")


def page_screens() -> None:
    st.header("Screeners Yahoo")
    c1, c2 = st.columns([3, 1])
    name = c1.selectbox("Screener prédéfini", mk.PREDEFINED_SCREENS)
    size = c2.number_input("Nombre de résultats", 10, 250, 100, step=10)
    try:
        df = c_screen(name, size=int(size))
    except Exception as exc:
        _error(exc)
        return
    preferred = ["symbol", "shortName", "regularMarketPrice", "regularMarketChangePercent",
                 "marketCap", "trailingPE", "fullExchangeName", "currency"]
    cols = [c for c in preferred if c in df.columns]
    if cols and st.toggle("Colonnes principales uniquement", value=True):
        df = df[cols]
    _show(df, f"screen_{name}", "dl_screen")


def page_markets() -> None:
    st.header("Marchés, secteurs, industries")
    t1, t2 = st.tabs(["Place de marché", "Secteurs & industries"])
    with t1:
        region = st.selectbox("Région", ["US", "FR", "GB", "DE", "IT", "ES", "NL", "CH", "JP", "HK", "CA", "AU", "IN"])
        try:
            res = c_market(region)
        except Exception as exc:
            _error(exc)
        else:
            st.subheader("Statut")
            st.dataframe(res["status"], width="stretch")
            st.subheader("Résumé")
            _show(res["summary"], f"market_{region}", "dl_mkt")
    with t2:
        key = st.selectbox("Secteur", mk.SECTORS, index=mk.SECTORS.index("technology"))
        try:
            sec = c_sector(key)
        except Exception as exc:
            _error(exc)
            return
        tabs = st.tabs(list(sec))
        for tab, (name, df) in zip(tabs, sec.items()):
            with tab:
                _show(df, f"sector_{key}_{name}", f"dl_sec_{name}")
        inds = sec["industries"]
        if not inds.empty:
            st.subheader("Industrie")
            ind_key = st.selectbox("Industrie", [str(i) for i in inds.index])
            try:
                ind = c_industry(ind_key)
            except Exception as exc:
                _error(exc)
                return
            for tab, (name, df) in zip(st.tabs(list(ind)), ind.items()):
                with tab:
                    _show(df, f"industry_{ind_key}_{name}", f"dl_ind_{name}")


def page_calendars() -> None:
    st.header("Calendriers")
    today = pd.Timestamp.today().normalize()
    c1, c2, c3 = st.columns(3)
    start = c1.date_input("Du", today)
    end = c2.date_input("Au", today + pd.Timedelta(days=7))
    limit = c3.number_input("Lignes max", 10, 500, 100, step=10)
    try:
        cal = c_calendars(str(start), str(end), int(limit))
    except Exception as exc:
        _error(exc)
        return
    labels = {"earnings": "Résultats", "economic_events": "Événements éco", "ipo": "IPO", "splits": "Splits"}
    for tab, (name, df) in zip(st.tabs([labels[k] for k in cal]), cal.items()):
        with tab:
            _show(df, f"calendar_{name}", f"dl_cal_{name}")


def page_catalog() -> None:
    st.header("Catalogue des datasets par ticker")
    df = list_datasets()
    df["category"] = df["category"].map(CATEGORY_LABELS)
    st.dataframe(df, width="stretch", hide_index=True, height=700)


PAGES = {
    "Fiche ticker": page_ticker,
    "Comparer des prix": page_prices,
    "Options": page_options,
    "Recherche": page_search,
    "Screeners": page_screens,
    "Marchés & secteurs": page_markets,
    "Calendriers": page_calendars,
    "Catalogue": page_catalog,
}


def main() -> None:
    st.sidebar.title("📈 YfDataExtract")
    page = st.sidebar.radio("Navigation", list(PAGES), label_visibility="collapsed")
    st.sidebar.caption("Données Yahoo Finance via yfinance — mises en cache 15 min.")
    if st.sidebar.button("Vider le cache"):
        st.cache_data.clear()
        st.session_state.pop("extract", None)
    PAGES[page]()


main()
