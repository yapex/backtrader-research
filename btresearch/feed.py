"""Create backtrader data feeds from DataFrames.

SRP: Solely responsible for converting DataFrames to backtrader feeds.
"""

from __future__ import annotations

import backtrader as bt
import pandas as pd


def make_feed(df: pd.DataFrame, ticker: str) -> bt.feeds.PandasData:
    """Convert a DataFrame to a backtrader PandasData feed.

    Normalizes column names and ensures required columns exist.
    """
    rename = {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    for c in ("Open", "High", "Low", "Close"):
        if c not in df.columns:
            raise ValueError(f"{ticker} missing column: {c}")

    if "Volume" not in df.columns:
        df["Volume"] = 0

    # backtrader rejects orders on bars with Volume=0;
    # fill with a minimal positive value so trading can proceed.
    df["Volume"] = df["Volume"].replace(0, 1)

    df = df[["Open", "High", "Low", "Close", "Volume"]]
    df_feed = df.reset_index()
    return bt.feeds.PandasData(
        dataname=df_feed,
        datetime=df_feed.columns[0],
        open="Open",
        high="High",
        low="Low",
        close="Close",
        volume="Volume",
    )
