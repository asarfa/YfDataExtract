"""YfDataExtract — extraire toutes les données accessibles via Yahoo Finance (yfinance)."""

from .export import save_frame, save_frames
from .markets import calendars, download, industry, lookup, market, screen, search, sector
from .ticker import CATEGORIES, DATASETS, ExtractionResult, TickerExtractor, list_datasets

__all__ = [
    "CATEGORIES", "DATASETS", "ExtractionResult", "TickerExtractor", "list_datasets",
    "download", "search", "lookup", "screen", "market", "sector", "industry", "calendars",
    "save_frame", "save_frames",
]
__version__ = "0.1.0"
