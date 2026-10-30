"""Daily adjusted-close loader with on-disk caching and several sources.

Sources (tried in order for --source auto):
  csv      : a directory of <TICKER>.csv files with Date + (Adj Close|Close) columns
  yfinance : Yahoo Finance via the yfinance package
  stooq    : stooq.com daily CSV endpoint (no key needed)
"""

from __future__ import annotations

import io
import os
from datetime import date, timedelta

import pandas as pd

STOOQ_URL = "https://stooq.com/q/d/l/?s={sym}&i=d"


def _read_price_csv(src) -> pd.Series:
    df = pd.read_csv(src)
    cols = {c.lower().replace("_", " "): c for c in df.columns}
    dcol = cols.get("date") or df.columns[0]
    pcol = cols.get("adj close") or cols.get("close")
    if pcol is None:
        raise ValueError(f"no Close/Adj Close column in {src}")
    s = pd.Series(df[pcol].values, index=pd.to_datetime(df[dcol]), dtype=float)
    return s.sort_index().dropna()


def from_csv_dir(ticker: str, folder: str) -> pd.Series:
    for name in (ticker, ticker.replace("-", "."), ticker.lower()):
        path = os.path.join(folder, f"{name}.csv")
        if os.path.exists(path):
            return _read_price_csv(path)
    raise FileNotFoundError(f"{ticker}.csv not in {folder}")


def from_yfinance(ticker: str, start: date) -> pd.Series:
    import yfinance as yf

    df = yf.download(ticker, start=start.isoformat(), auto_adjust=True, progress=False,
                     threads=False)
    if df is None or df.empty:
        raise RuntimeError(f"yfinance returned no data for {ticker}")
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    return close.dropna().astype(float)


def from_stooq(ticker: str, start: date) -> pd.Series:
    import requests

    sym = ticker.lower().replace("-", ".") + ".us"
    resp = requests.get(STOOQ_URL.format(sym=sym), timeout=30)
    resp.raise_for_status()
    if not resp.text.lower().startswith("date"):
        raise RuntimeError(f"stooq returned no data for {ticker}")
    s = _read_price_csv(io.StringIO(resp.text))
    return s[s.index >= pd.Timestamp(start)]


def load_prices(tickers, years: float = 3.0, source: str = "auto", csv_dir: str | None = None,
                cache_dir: str = "data/cache", refresh: bool = False, log=print) -> dict[str, pd.Series]:
    start = date.today() - timedelta(days=int(years * 365.25) + 10)
    os.makedirs(cache_dir, exist_ok=True)
    order = {"auto": ["csv", "yfinance", "stooq"]}.get(source, [source])
    out, errors = {}, {}
    for tk in tickers:
        cache = os.path.join(cache_dir, f"{tk}.csv")
        if not refresh and os.path.exists(cache) and source != "csv":
            s = _read_price_csv(cache)
            if len(s) and s.index[-1].date() >= date.today() - timedelta(days=4):
                out[tk] = s[s.index >= pd.Timestamp(start)]
                continue
        errs = []
        for src in order:
            try:
                if src == "csv":
                    if not csv_dir:
                        continue
                    s = from_csv_dir(tk, csv_dir)
                    s = s[s.index >= pd.Timestamp(start)]
                elif src == "yfinance":
                    s = from_yfinance(tk, start)
                elif src == "stooq":
                    s = from_stooq(tk, start)
                else:
                    raise ValueError(f"unknown source {src}")
                out[tk] = s
                if src != "csv":
                    s.rename("Close").to_frame().to_csv(cache, index_label="Date")
                break
            except Exception as e:  # noqa: BLE001 - try the next source
                errs.append(f"{src}: {type(e).__name__}: {str(e)[:120]}")
        else:
            errors[tk] = errs
            log(f"  [skip] {tk}: " + " | ".join(errs) if errs else f"  [skip] {tk}: no source")
    return out, errors
