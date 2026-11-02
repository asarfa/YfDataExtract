"""Conversion helpers: turn whatever yfinance returns into a pandas DataFrame."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pandas as pd


def _is_scalar(x: Any) -> bool:
    return x is None or isinstance(x, (str, int, float, bool, pd.Timestamp)) or pd.api.types.is_scalar(x)


def to_frame(obj: Any) -> pd.DataFrame:
    """Normalise a yfinance return value (DataFrame, Series, dict, list, scalar...) to a DataFrame."""
    if obj is None:
        return pd.DataFrame()
    if isinstance(obj, pd.DataFrame):
        return obj
    if isinstance(obj, pd.Series):
        name = obj.name if obj.name is not None else "value"
        return obj.to_frame(name=str(name))
    # yfinance FastInfo and similar mapping-like objects
    if not isinstance(obj, Mapping) and hasattr(obj, "keys") and hasattr(obj, "__getitem__"):
        out = {}
        for k in obj.keys():
            try:
                out[k] = obj[k]
            except Exception:  # some FastInfo fields raise when unavailable
                out[k] = None
        obj = out
    if isinstance(obj, Mapping):
        if not obj:
            return pd.DataFrame()
        if all(_is_scalar(v) for v in obj.values()):
            return pd.DataFrame({"field": list(obj.keys()), "value": list(obj.values())})
        try:
            return pd.DataFrame(obj)
        except ValueError:
            return pd.DataFrame(
                {"field": list(obj.keys()), "value": [_jsonify(v) for v in obj.values()]}
            )
    if isinstance(obj, (list, tuple)):
        if not obj:
            return pd.DataFrame()
        if all(isinstance(x, Mapping) for x in obj):
            return pd.json_normalize(list(obj))
        return pd.DataFrame({"value": list(obj)})
    return pd.DataFrame({"value": [obj]})


def _jsonify(v: Any) -> Any:
    if _is_scalar(v):
        return v
    try:
        return json.dumps(v, default=str, ensure_ascii=False)
    except TypeError:
        return str(v)


def sanitize_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns, stringify column names and serialise nested objects."""
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ["_".join(str(p) for p in col if str(p)) for col in df.columns]
    else:
        df.columns = [str(c) for c in df.columns]
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].map(_jsonify)
            # mixed int/str columns break pyarrow: force string when types are mixed
            types = {type(v) for v in df[c].dropna()}
            if len(types) > 1:
                df[c] = df[c].map(lambda v: None if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))
    if isinstance(df.index, pd.MultiIndex) or df.index.dtype == object:
        df.index = df.index.map(lambda v: "_".join(map(str, v)) if isinstance(v, tuple) else str(v))
    return df
