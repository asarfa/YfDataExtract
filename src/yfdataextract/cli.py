"""Command line interface: ``yfdx <commande> ...`` (voir ``yfdx -h``)."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from . import markets as mk
from .export import FORMATS, save_frame, save_frames
from .ticker import CATEGORIES, TickerExtractor, list_datasets


def _emit(frames: dict[str, pd.DataFrame], out: str | None, fmt: str, prefix: str = "") -> None:
    if out:
        for p in save_frames({f"{prefix}{k}": v for k, v in frames.items()}, out, fmt):
            print(p)
        return
    with pd.option_context("display.max_rows", 40, "display.max_columns", 20, "display.width", 200):
        for name, df in frames.items():
            print(f"\n=== {prefix}{name} ({len(df)} lignes) ===")
            print(df)


def cmd_datasets(a):
    print(list_datasets(a.category).to_string(index=False))


def cmd_ticker(a):
    for sym in a.symbols:
        res = TickerExtractor(sym).extract(datasets=a.datasets, categories=a.categories)
        out = str(Path(a.out) / res.symbol) if a.out else None
        _emit(res.data, out, a.format)
        print(f"\n--- {res.symbol}: {len(res.data)} datasets OK, {len(res.errors)} en erreur", file=sys.stderr)
        if res.errors and a.verbose:
            for k, e in res.errors.items():
                print(f"  {k}: {e}", file=sys.stderr)
        if a.out:
            save_frame(res.summary, Path(a.out) / res.symbol / "_summary", "csv")


def cmd_history(a):
    frames = {
        s: TickerExtractor(s).history(period=a.period, interval=a.interval, start=a.start, end=a.end)
        for s in a.symbols
    }
    _emit(frames, a.out, a.format, prefix="history_")


def cmd_download(a):
    df = mk.download(a.symbols, period=a.period, interval=a.interval, start=a.start, end=a.end, field=a.field)
    _emit({"download": df}, a.out, a.format)


def cmd_options(a):
    for s in a.symbols:
        _emit({f"{s}_options": TickerExtractor(s).options(a.max_expirations)}, a.out, a.format)


def cmd_search(a):
    _emit(mk.search(a.query, max_results=a.max_results), a.out, a.format, prefix="search_")


def cmd_lookup(a):
    _emit({f"lookup_{a.kind}": mk.lookup(a.query, a.kind, a.count)}, a.out, a.format)


def cmd_screen(a):
    if a.name is None:
        print("\n".join(mk.PREDEFINED_SCREENS))
        return
    _emit({f"screen_{a.name}": mk.screen(a.name, size=a.size)}, a.out, a.format)


def cmd_market(a):
    _emit(mk.market(a.region), a.out, a.format, prefix=f"market_{a.region}_")


def cmd_sector(a):
    _emit(mk.sector(a.key), a.out, a.format, prefix=f"sector_{a.key}_")


def cmd_industry(a):
    _emit(mk.industry(a.key), a.out, a.format, prefix=f"industry_{a.key}_")


def cmd_calendar(a):
    _emit(mk.calendars(a.start, a.end, a.limit), a.out, a.format, prefix="calendar_")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="yfdx", description="Extraction de données Yahoo Finance")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("-o", "--out", help="Dossier de sortie (sinon affichage console)")
        sp.add_argument("-f", "--format", choices=FORMATS, default="csv")
        sp.set_defaults(func=fn)
        return sp

    def dates(sp):
        sp.add_argument("--period", default="1y", help="1d 5d 1mo 3mo 6mo 1y 2y 5y 10y ytd max")
        sp.add_argument("--interval", default="1d", help="1m 2m 5m 15m 30m 60m 90m 1h 1d 5d 1wk 1mo 3mo")
        sp.add_argument("--start")
        sp.add_argument("--end")

    sp = add("datasets", cmd_datasets, "Liste les datasets disponibles par ticker")
    sp.add_argument("--category", choices=CATEGORIES)

    sp = add("ticker", cmd_ticker, "Extrait tous (ou certains) datasets d'un ou plusieurs tickers")
    sp.add_argument("symbols", nargs="+")
    sp.add_argument("-d", "--datasets", nargs="+", help="Noms de datasets (voir `yfdx datasets`)")
    sp.add_argument("-c", "--categories", nargs="+", choices=CATEGORIES)

    sp = add("history", cmd_history, "Historique de prix par ticker")
    sp.add_argument("symbols", nargs="+")
    dates(sp)

    sp = add("download", cmd_download, "Prix de plusieurs tickers en un tableau")
    sp.add_argument("symbols", nargs="+")
    sp.add_argument("--field", help="Close, Adj Close, Open, High, Low, Volume")
    dates(sp)

    sp = add("options", cmd_options, "Chaînes d'options complètes")
    sp.add_argument("symbols", nargs="+")
    sp.add_argument("--max-expirations", type=int)

    sp = add("search", cmd_search, "Recherche plein texte (symboles, news, listes)")
    sp.add_argument("query")
    sp.add_argument("--max-results", type=int, default=20)

    sp = add("lookup", cmd_lookup, "Recherche de symboles par type d'actif")
    sp.add_argument("query")
    sp.add_argument("--kind", choices=mk.LOOKUP_TYPES, default="all")
    sp.add_argument("--count", type=int, default=25)

    sp = add("screen", cmd_screen, "Screeners prédéfinis Yahoo (sans nom: liste)")
    sp.add_argument("name", nargs="?", choices=mk.PREDEFINED_SCREENS)
    sp.add_argument("--size", type=int, default=100)

    sp = add("market", cmd_market, "Statut et résumé d'une place de marché")
    sp.add_argument("region", nargs="?", default="US")

    sp = add("sector", cmd_sector, "Vue secteur")
    sp.add_argument("key", choices=mk.SECTORS)

    sp = add("industry", cmd_industry, "Vue industrie")
    sp.add_argument("key")

    sp = add("calendar", cmd_calendar, "Calendriers: résultats, éco, IPO, splits")
    sp.add_argument("--start")
    sp.add_argument("--end")
    sp.add_argument("--limit", type=int, default=100)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
