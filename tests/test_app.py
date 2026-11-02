"""Smoke test of every Streamlit page with yfinance mocked (offline)."""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from tests.test_offline import FakeTicker

APP = str(Path(__file__).parents[1] / "src" / "yfdataextract" / "app.py")


class FakeTickerFull(FakeTicker):
    def __init__(self, symbol, session=None):
        super().__init__(symbol)
        idx = pd.date_range("2024-01-01", periods=300, freq="B", tz="America/New_York")
        c = 100 * np.exp(np.cumsum(np.random.default_rng(0).normal(0, 0.01, len(idx))))
        self._hist = pd.DataFrame({"Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c, "Adj Close": c, "Volume": 1e6}, index=idx)

    def option_chain(self, exp):
        df = pd.DataFrame({"strike": [90.0, 100, 110], "impliedVolatility": [0.3, 0.2, 0.25], "lastPrice": [11.0, 3, 1]})
        return SimpleNamespace(calls=df, puts=df.copy())


def fake_download(tickers, **kw):
    idx = pd.date_range("2020-01-01", periods=500, freq="B")
    rng = np.random.default_rng(1)
    cols = pd.MultiIndex.from_product([["Adj Close", "Close", "Volume"], tickers])
    return pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0, 0.01, (len(idx), len(cols))), axis=0)), index=idx, columns=cols)


@pytest.fixture
def at(monkeypatch):
    import yfinance as yf
    monkeypatch.setattr(yf, "Ticker", FakeTickerFull)
    monkeypatch.setattr(yf, "download", fake_download)
    frame = pd.DataFrame({"symbol": ["A", "B"], "shortName": ["a", "b"]})
    monkeypatch.setattr(yf, "screen", lambda *a, **k: {"quotes": frame.to_dict("records")})
    monkeypatch.setattr(yf, "Search", lambda *a, **k: SimpleNamespace(quotes=[{"symbol": "MC.PA"}], news=[], lists=[], research=[]))
    monkeypatch.setattr(yf, "Lookup", lambda *a, **k: SimpleNamespace(**{f"get_{t}": (lambda count=25: frame) for t in
                        ("all", "stock", "etf", "mutualfund", "index", "future", "currency", "cryptocurrency")}))
    monkeypatch.setattr(yf, "Market", lambda r: SimpleNamespace(status={"status": "open"}, summary={"^GSPC": {"price": 1}}))
    monkeypatch.setattr(yf, "Sector", lambda k: SimpleNamespace(overview={"a": 1}, top_companies=frame, top_etfs={"X": "x"},
                        top_mutual_funds={}, industries=pd.DataFrame({"name": ["Semis"]}, index=["semiconductors"]), research_reports=[]))
    monkeypatch.setattr(yf, "Industry", lambda k: SimpleNamespace(overview={"a": 1}, top_companies=frame, top_growth_companies=frame,
                        top_performing_companies=frame, research_reports=[]))
    cal = SimpleNamespace(**{f"get_{n}": (lambda limit=12: frame) for n in
                          ("earnings_calendar", "economic_events_calendar", "ipo_info_calendar", "splits_calendar")})
    monkeypatch.setattr(yf, "Calendars", lambda **k: cal)
    a = AppTest.from_file(APP, default_timeout=30)
    a.run()
    return a


def test_all_pages_render(at):
    pages = at.sidebar.radio[0].options
    for page in pages:
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception, (page, at.exception)


def test_ticker_extraction(at):
    at.button[0].click().run()  # "Extraire ..." (first main-area button)
    assert not at.exception
    assert any("datasets récupérés" in s.value for s in at.success)
