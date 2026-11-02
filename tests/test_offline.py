"""Offline tests: yfinance is mocked, no network needed."""

from types import SimpleNamespace

import pandas as pd
import pytest

import yfdataextract as yfx
from yfdataextract import cli
from yfdataextract._utils import sanitize_for_parquet, to_frame
from yfdataextract.ticker import DATASETS


class FakeTicker:
    def __init__(self, symbol, session=None):
        self.symbol = symbol
        idx = pd.date_range("2024-01-01", periods=3, tz="America/New_York")
        self._hist = pd.DataFrame({"Open": [1.0, 2, 3], "Close": [1.5, 2.5, 3.5], "Volume": [10, 20, 30]}, index=idx)
        self.info = {"symbol": symbol, "sector": "Technology", "companyOfficers": [{"name": "X"}]}
        self.dividends = pd.Series([0.2, 0.3], index=idx[:2], name="Dividends")
        self.income_stmt = pd.DataFrame({"2023": [100, 20]}, index=["TotalRevenue", "NetIncome"])
        self.options = ("2025-01-17", "2025-02-21")
        self.news = [{"title": "a", "content": {"x": 1}}]

    def history(self, **kwargs):
        return self._hist

    def option_chain(self, exp):
        df = pd.DataFrame({"strike": [100.0], "lastPrice": [1.0]})
        return SimpleNamespace(calls=df, puts=df.copy())

    def get_news(self, count=10):
        return self.news

    @property
    def sustainability(self):
        raise RuntimeError("404 Not Found")


@pytest.fixture(autouse=True)
def fake_yf(monkeypatch):
    monkeypatch.setattr("yfdataextract.ticker.yf.Ticker", FakeTicker)


def test_to_frame_variants():
    assert to_frame(None).empty
    assert list(to_frame({"a": 1, "b": "x"}).columns) == ["field", "value"]
    assert len(to_frame([{"a": 1}, {"a": 2}])) == 2
    assert to_frame("FR0000000000").iloc[0, 0] == "FR0000000000"
    assert to_frame(pd.Series([1, 2], name="s")).columns.tolist() == ["s"]
    nested = to_frame({"a": 1, "b": [1, 2, 3]})
    assert nested.shape[0] >= 2


def test_extract_isolates_errors():
    res = yfx.TickerExtractor("aapl").extract(
        datasets=["history", "info", "dividends", "income_stmt", "options", "news", "sustainability"]
    )
    assert res.symbol == "AAPL"
    assert {"history", "info", "dividends", "income_stmt", "options", "news"} <= set(res.data)
    assert "sustainability" in res.errors
    assert len(res.data["options"]) == 4  # 2 expirations x calls/puts
    assert set(res.data["options"]["option_type"]) == {"call", "put"}
    assert set(res.summary["status"]) == {"ok", "error"}


def test_categories_and_unknown():
    assert set(yfx.CATEGORIES) == {d.category for d in DATASETS.values()}
    with pytest.raises(KeyError):
        yfx.TickerExtractor("X").extract(datasets=["nope"])
    with pytest.raises(KeyError):
        yfx.TickerExtractor("X").extract(categories=["nope"])
    assert not yfx.list_datasets("funds").empty


@pytest.mark.parametrize("fmt", ["csv", "parquet", "json"])
def test_export_formats(tmp_path, fmt):
    res = yfx.TickerExtractor("AAPL").extract(datasets=["history", "info", "news", "options"])
    paths = yfx.save_frames(res.data, tmp_path, fmt)
    assert all(p.exists() and p.stat().st_size > 0 for p in paths)


def test_parquet_sanitize_multiindex():
    cols = pd.MultiIndex.from_product([["Close"], ["AAPL", "MSFT"]])
    df = pd.DataFrame([[1, 2]], columns=cols)
    assert sanitize_for_parquet(df).columns.tolist() == ["Close_AAPL", "Close_MSFT"]


def test_download_field(monkeypatch):
    cols = pd.MultiIndex.from_product([["Close", "Volume"], ["AAPL", "MSFT"]])
    fake = pd.DataFrame([[1, 2, 3, 4]], columns=cols)
    monkeypatch.setattr("yfdataextract.markets.yf.download", lambda *a, **k: fake)
    out = yfx.download("AAPL,MSFT", field="Close")
    assert out.columns.tolist() == ["AAPL", "MSFT"]


def test_screen_validation():
    with pytest.raises(ValueError):
        yfx.screen("not_a_screen")
    with pytest.raises(ValueError):
        yfx.lookup("x", kind="bad")


def test_cli_ticker(tmp_path, capsys):
    assert cli.main(["ticker", "AAPL", "-d", "history", "info", "-o", str(tmp_path)]) == 0
    assert (tmp_path / "AAPL" / "history.csv").exists()
    assert (tmp_path / "AAPL" / "_summary.csv").exists()
    assert cli.main(["datasets"]) == 0
    assert "income_stmt" in capsys.readouterr().out
