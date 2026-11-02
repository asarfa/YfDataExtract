"""Write extracted DataFrames to disk (csv / parquet / json / xlsx)."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pandas as pd

from ._utils import sanitize_for_parquet

FORMATS = ("csv", "parquet", "json", "xlsx")


def save_frame(df: pd.DataFrame, path: str | Path, fmt: str = "csv") -> Path:
    path = Path(path).with_suffix(f".{fmt}")
    path.parent.mkdir(parents=True, exist_ok=True)
    match fmt:
        case "csv":
            df.to_csv(path)
        case "parquet":
            sanitize_for_parquet(df).to_parquet(path)
        case "json":
            df.to_json(path, orient="table", date_format="iso", default_handler=str)
        case "xlsx":
            out = sanitize_for_parquet(df)
            for c in out.select_dtypes(include=["datetimetz"]).columns:
                out[c] = out[c].dt.tz_localize(None)
            if isinstance(out.index, pd.DatetimeIndex) and out.index.tz is not None:
                out.index = out.index.tz_localize(None)
            out.to_excel(path)
        case _:
            raise ValueError(f"Format inconnu {fmt!r}, valides: {FORMATS}")
    return path


def save_frames(frames: Mapping[str, pd.DataFrame], out_dir: str | Path, fmt: str = "csv") -> list[Path]:
    out_dir = Path(out_dir)
    return [save_frame(df, out_dir / name, fmt) for name, df in frames.items()]
