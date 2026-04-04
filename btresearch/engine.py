"""Core backtest engine — orchestrates caching, data loading, and evaluation.

SRP: This module orchestrates the backtest pipeline. It delegates to:
  - CacheManager for caching (DIP)
  - DataLoader for data fetching (DIP)
  - Evaluator for metrics computation (DIP)
  - Tracker for portfolio tracking
  - Strategy for trading logic

All heavy lifting is in focused modules. This file just wires them together.
"""

from __future__ import annotations

import backtrader as bt
import pandas as pd

from .cache import CacheManager, get_cache_manager
from .commission import StockCommission
from .config import (
    deep_merge,
    extract_deposits,
    get_commission,
    get_default_benchmark,
)
from .data_provider import DataLoader, get_data_loader
from .feed import make_feed
from .metrics import AnnualReturn, Evaluator, MaxDrawdown
from .strategy import Strategy
from .tracker import Tracker


# ======================================================================
# Internal strategies
# ======================================================================

class _BuyAll(bt.Strategy):
    """Benchmark buy-and-hold: invest 98% into first data feed."""

    def __init__(self):
        self._bought = False

    def next(self):
        if not self._bought:
            self.order_target_percent(self.datas[0], 0.98)
            self._bought = True


# ======================================================================
# Backtest execution (internal)
# ======================================================================

def _run(
    data: dict,
    strategy_config: dict,
    cash: float,
    commission: float,
) -> tuple[dict, list]:
    """Execute a strategy backtest via backtrader.

    Returns (tracker_data, trade_log).
    """
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(cash)
    cerebro.broker.set_checksubmit(False)
    cerebro.broker.addcommissioninfo(StockCommission(commission=commission))
    for ticker, df in data.items():
        cerebro.adddata(make_feed(df, ticker), name=ticker)
    Strategy._config = strategy_config
    cerebro.addanalyzer(Tracker, _name="tracker")
    cerebro.addstrategy(Strategy)
    results = cerebro.run()
    return results[0].analyzers.tracker.get_analysis(), results[0].trade_log


def _run_buyhold(data: dict, cash: float, commission: float) -> pd.Series:
    """Execute buy-and-hold benchmark via backtrader.

    Returns daily NAV series.
    """
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(cash)
    cerebro.broker.set_checksubmit(False)
    cerebro.broker.addcommissioninfo(StockCommission(commission=commission))
    for ticker, df in data.items():
        cerebro.adddata(make_feed(df, ticker), name=ticker)
    cerebro.addanalyzer(Tracker, _name="tracker")
    cerebro.addstrategy(_BuyAll)
    results = cerebro.run()
    return results[0].analyzers.tracker.get_analysis()["value"]


# ======================================================================
# Data loading with caching (Layer 1)
# ======================================================================

def load_data(
    tickers: list[str],
    start: str,
    end: str,
    cache: CacheManager | None = None,
    loader: DataLoader | None = None,
) -> dict[str, pd.DataFrame]:
    """Load ticker data with Layer 1 caching.

    DIP: Uses injectable DataLoader and CacheManager.
    """
    if cache is None:
        cache = get_cache_manager()
    if loader is None:
        loader = get_data_loader()

    data = {}
    for ticker in tickers:
        cache_key = f"{ticker}:{start}:{end}"
        cached = cache.get_data(cache_key)
        if cached is not None:
            data[ticker] = cached
            print(f"  [data:cache] {ticker}: {len(data[ticker])} rows")
        else:
            print(f"  [data:load]  {ticker}...")
            df = loader.download(ticker, start, end)
            cache.set_data(cache_key, df)
            data[ticker] = df
            print(f"  [data:done]  {ticker}: {len(df)} rows")
    return data


# ======================================================================
# Cached execution getters (Layer 2 & 3)
# ======================================================================

def get_strategy_result(
    effective_config: dict,
    cache: CacheManager | None = None,
    loader: DataLoader | None = None,
) -> dict:
    """Get cached or compute strategy portfolio data.

    Cache key: strategy_hash : config_hash
    Invalidated by: strategy.py changes OR config changes
    Survives: metrics changes, evaluate() changes
    """
    if cache is None:
        cache = get_cache_manager()
    if loader is None:
        loader = get_data_loader()

    cache_key = cache.strategy_cache_key(effective_config)

    cached = cache.get_strategy(cache_key)
    if cached is not None:
        print(f"  [strat:hit]  {cache_key}")
        return cached

    print(f"  [strat:miss] {cache_key}")

    assets = effective_config["assets"]
    tickers = [a["ticker"] for a in assets]
    weights = {a["ticker"]: a["weight"] for a in assets}
    deposits_cfg = extract_deposits(effective_config)
    period = effective_config["period"]
    currency = effective_config.get("currency", "USD").upper()
    commission = effective_config.get("commission", get_commission(currency))

    if deposits_cfg["active"]:
        cash = max(deposits_cfg["initial"], 1.0)
    else:
        cash = effective_config.get("cash", 100000)

    bench_ticker = effective_config.get("benchmark", get_default_benchmark(currency))
    # Only load strategy tickers for execution; benchmark is run separately
    # via _run_buyhold. Mixing feeds with misaligned trading days causes
    # backtrader to skip bars and break order execution.
    data = load_data(tickers, period["start"], period["end"], cache, loader)

    strategy_config = {
        "tickers": tickers,
        "weights": weights,
        "deposits": deposits_cfg,
        "params": effective_config.get("params", {}),
    }

    tracker_data, _ = _run(data, strategy_config, cash, commission)

    result = {
        "portfolio": tracker_data["value"],
        "total_deposited": tracker_data["total_deposited"],
        "deposit_dates": tracker_data["deposit_dates"],
        "deposit_amounts": tracker_data["deposit_amounts"],
    }
    cache.set_strategy(cache_key, result)
    return result


def get_benchmark(
    ticker: str,
    period: dict,
    cash: float,
    commission: float,
    cache: CacheManager | None = None,
    loader: DataLoader | None = None,
) -> pd.Series:
    """Get cached or compute buy-hold benchmark.

    Cache key: ticker:period:cash:commission
    Survives: strategy changes, metrics changes
    """
    if cache is None:
        cache = get_cache_manager()
    if loader is None:
        loader = get_data_loader()

    cache_key = f"{ticker}:{period['start']}:{period['end']}:{cash}:{commission}"

    cached = cache.get_benchmark(cache_key)
    if cached is not None:
        print(f"  [bench:hit]  {ticker}")
        return cached

    print(f"  [bench:miss] {ticker}")
    data = load_data([ticker], period["start"], period["end"], cache, loader)
    result = _run_buyhold({ticker: data[ticker]}, cash, commission)
    cache.set_benchmark(cache_key, result)
    return result


# ======================================================================
# Public API
# ======================================================================

def run_backtest(
    config: dict,
    profile: dict | None = None,
    cache: CacheManager | None = None,
    loader: DataLoader | None = None,
    evaluator: Evaluator | None = None,
) -> dict:
    """Run backtest with 3-layer caching. Returns metrics dict.

    DIP: All dependencies are injectable for testing.
    """
    effective = deep_merge(config, profile) if profile else config
    deposits_cfg = extract_deposits(effective)
    currency = effective.get("currency", "USD").upper()
    commission = effective.get("commission", get_commission(currency))
    period = effective["period"]
    bench_ticker = effective.get("benchmark", get_default_benchmark(currency))

    # Layer 3: strategy result (cached)
    strat = get_strategy_result(effective, cache, loader)

    # Layer 2: benchmark (cached)
    if deposits_cfg["active"]:
        bench_cash = deposits_cfg["total_capital"]
    else:
        bench_cash = effective.get("cash", 100000)

    benchmark = None
    if bench_ticker:
        benchmark = get_benchmark(
            bench_ticker, period, bench_cash, commission, cache, loader
        )

    # Pure computation (instant, no caching needed)
    tracker_data = {
        "value": strat["portfolio"],
        "total_deposited": strat["total_deposited"],
        "deposit_dates": strat["deposit_dates"],
        "deposit_amounts": strat["deposit_amounts"],
    }

    if evaluator is None:
        evaluator = Evaluator()
    return evaluator.evaluate(
        strat["portfolio"],
        benchmark,
        tracker_data,
        currency=currency,
        risk_free_rate=effective.get("risk_free_rate"),
    )


def clear_cache(layer: str | None = None) -> None:
    """Clear execution caches. layer: 'data'|'strategy'|'benchmark'|None (all)."""
    get_cache_manager().clear(layer)
