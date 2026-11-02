"""Démo rapide : uv run python examples/demo.py"""

import yfdataextract as yfx

res = yfx.TickerExtractor("AAPL").extract(categories=["meta", "prices", "fundamentals"])
print(res.summary)
print(yfx.download(["AAPL", "MSFT"], period="1mo", field="Close").tail())
