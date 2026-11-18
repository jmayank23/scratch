"""Rolling-origin backtest folds with a purge gap.

A training row at month t has a label that is known only at month t + 12 + 1
(12-month horizon plus the 1-month Zillow release lag). So for a test year that starts
at month T, the last training row is T - 13 months. Rows closer to T are purged.
"""
from __future__ import annotations

import pandas as pd

from . import config as C


def rolling_folds(test_years: list[int] | None = None,
                  horizon: int = C.HORIZON_MONTHS,
                  release_lag: int = C.ZILLOW_RELEASE_LAG_MONTHS) -> list[dict]:
    folds = []
    for y in test_years or C.TEST_YEARS:
        test_start = pd.Timestamp(f"{y}-01-01")
        train_end = (test_start.to_period("M") - (horizon + release_lag)).to_timestamp()
        folds.append({"test_year": y, "train_end": train_end, "test_start": test_start,
                      "test_end": pd.Timestamp(f"{y}-12-01")})
    return folds


def split_frame(df: pd.DataFrame, fold: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (train, test). Rows need `month` and a non-null `label_g12_dm`."""
    df = df[df["label_g12_dm"].notna()]
    train = df[df["month"] <= fold["train_end"]]
    test = df[(df["month"] >= fold["test_start"]) & (df["month"] <= fold["test_end"])]
    return train, test
