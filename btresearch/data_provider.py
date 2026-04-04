"""Data provider abstraction — extensible without modifying existing code.

OCP: Register new data providers without changing existing providers or DataLoader.
DIP: Engine depends on DataProvider protocol, not concrete implementations.

Usage — adding a new data source::

    class MyProvider:
        def can_handle(self, ticker: str) -> bool: ...
        def download(self, ticker: str, start: str, end: str) -> pd.DataFrame: ...

    loader = get_data_loader()
    loader.register(MyProvider())
"""

from __future__ import annotations

from typing import Protocol

import pandas as pd


# ======================================================================
# Protocol (DIP: depend on abstraction)
# ======================================================================

class DataProvider(Protocol):
    """Protocol for market data providers."""

    def can_handle(self, ticker: str) -> bool: ...
    def download(self, ticker: str, start: str, end: str) -> pd.DataFrame: ...


# ======================================================================
# Concrete providers
# ======================================================================

class YahooProvider:
    """Default provider for international tickers via yfinance.

    Also serves as the fallback provider for any unrecognized ticker.
    """

    def can_handle(self, ticker: str) -> bool:
        return True  # fallback — must be last in registry

    def download(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        import yfinance as yf

        df = yf.download(ticker, start=start, end=end, progress=False)
        if df.empty:
            raise ValueError(f"Cannot download {ticker}")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.capitalize() for c in df.columns]
        return df


class CNIndexProvider:
    """Provider for Chinese A-share indices via akshare (Sina Finance).

    Handles: 000300.SS, 000905.SS, etc. (6-digit codes, not 51/15/13/50).
    """

    def can_handle(self, ticker: str) -> bool:
        tl = ticker.lower()
        return (
            tl.endswith((".ss", ".sz", ".sh"))
            and not tl.startswith(("51", "15", "13", "50"))
        )

    def download(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        import akshare as ak

        code, suffix = ticker.split(".")[0], ticker.split(".")[-1].upper()
        prefix = "sh" if suffix in ("SS", "SH") else "sz"
        df = ak.stock_zh_index_daily(symbol=f"{prefix}{code}")
        if df is None or df.empty:
            raise ValueError(f"Cannot download {ticker}")
        df = df.rename(
            columns={
                "date": "Date",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume",
            }
        )
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date").sort_index()
        return df.loc[
            (df.index >= pd.to_datetime(start))
            & (df.index <= pd.to_datetime(end))
        ]


class CNEtfProvider:
    """Provider for Chinese ETFs via yfinance (dividend-adjusted prices).

    Handles: 510300.SS, 511010.SS, 518880.SS, etc. (51/15/13/50 codes).
    Uses yfinance because it provides dividend-adjusted prices, which
    akshare/sina don't account for.
    """

    def can_handle(self, ticker: str) -> bool:
        tl = ticker.lower()
        return tl.endswith((".sh", ".sz", ".ss")) and tl.startswith(
            ("51", "15", "13", "50")
        )

    def download(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        return YahooProvider().download(ticker, start, end)


# ======================================================================
# Registry (OCP: add providers without modifying existing code)
# ======================================================================

class DataLoader:
    """Registry of data providers. Selects provider by ticker automatically.

    OCP: New providers are registered via register() without touching
    existing provider code.
    """

    def __init__(self, providers: list[DataProvider] | None = None):
        self._providers: list[DataProvider] = providers or [
            CNIndexProvider(),
            CNEtfProvider(),
            YahooProvider(),  # fallback, must be last
        ]

    def register(self, provider: DataProvider) -> None:
        """Register a new data provider.

        Inserts before the fallback provider (last one that handles everything).
        """
        if len(self._providers) > 1:
            # Insert before the last provider (assumed fallback)
            self._providers.insert(-1, provider)
        else:
            self._providers.append(provider)

    def get_provider(self, ticker: str) -> DataProvider:
        """Find the first provider that can handle the given ticker."""
        for provider in self._providers:
            if provider.can_handle(ticker):
                return provider
        raise ValueError(f"No data provider for ticker: {ticker}")

    def download(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        """Download data using the appropriate provider."""
        provider = self.get_provider(ticker)
        return provider.download(ticker, start, end)


# ------------------------------------------------------------------
# Module-level singleton
# ------------------------------------------------------------------

_data_loader: DataLoader | None = None


def get_data_loader() -> DataLoader:
    """Get the global DataLoader instance."""
    global _data_loader
    if _data_loader is None:
        _data_loader = DataLoader()
    return _data_loader
