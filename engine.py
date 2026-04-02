"""
Autonomous Trading Strategy Research Engine (DO NOT MODIFY)

Reads research.yaml config, runs Strategy from strategy.py, outputs results.

Usage::

    uv run engine.py
"""

from __future__ import annotations

import inspect
import sys
import textwrap
from pathlib import Path

import backtrader as bt
import numpy as np
import pandas as pd
import yaml
import yfinance as yf


# ======================================================================
# Config
# ======================================================================

def load_config() -> dict:
    config_path = Path("research.yaml")
    if not config_path.exists():
        print("[ERROR] research.yaml not found")
        sys.exit(1)
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ======================================================================
# Patch backtrader margin check
# ======================================================================

def _patch_backtrader():
    from backtrader.brokers.bbroker import BackBroker
    src = inspect.getsource(BackBroker._execute)
    if "if cash < 0.0:" not in src:
        return
    patched = textwrap.dedent(src).replace(
        "if cash < 0.0:",
        "if cash < -999999.0:  # btresearch patch: allow commission overflow",
    )
    ns = {}
    exec(compile(patched, "<patch>", "exec"), ns)
    BackBroker._execute = ns["_execute"]

_patch_backtrader()


# ======================================================================
# Commission
# ======================================================================

COMMISSION = 0.0003  # 0.03%, i.e. 3 bps (wan fen zhi san)


class _StockCommission(bt.comminfo.CommInfoBase):
    params = (
        ("commission", COMMISSION),
        ("stocklike", True),
        ("commtype", bt.comminfo.CommInfoBase.COMM_PERC),
        ("percabs", True),
    )


# ======================================================================
# FX rate
# ======================================================================

USD_CNY = 7.30  # approximate USD/CNY rate (2024-2026)


def normalize_cash(base_currency: str, cash: float) -> float:
    """Convert cash to USD if needed (engine internally uses USD)."""
    if base_currency.upper() == "CNY":
        return cash / USD_CNY
    return cash


# ======================================================================
# Data loading
# ======================================================================

CACHE_DIR = Path.home() / ".cache" / "btresearch"


def load_data(tickers: list[str], start: str, end: str) -> dict[str, pd.DataFrame]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    data: dict[str, pd.DataFrame] = {}

    for ticker in tickers:
        cache_file = CACHE_DIR / f"{ticker}.pkl"
        if cache_file.exists():
            data[ticker] = pd.read_pickle(cache_file)
            print(f"[cache] {ticker}: {len(data[ticker])} rows")
        else:
            print(f"[download] {ticker}...")
            df = yf.download(ticker, start=start, end=end, progress=False)
            if df.empty:
                raise ValueError(f"Cannot download {ticker}")
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns = [c.capitalize() for c in df.columns]
            df.to_pickle(cache_file)
            data[ticker] = df
            print(f"[done] {ticker}: {len(df)} rows")

    return data


def _make_feed(df: pd.DataFrame, ticker: str) -> bt.feeds.PandasData:
    rename = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    for c in ("Open", "High", "Low", "Close"):
        if c not in df.columns:
            raise ValueError(f"{ticker} missing column: {c}")
    if "Volume" not in df.columns:
        df["Volume"] = 0
    df = df[["Open", "High", "Low", "Close", "Volume"]]
    df_feed = df.reset_index()
    return bt.feeds.PandasData(
        dataname=df_feed,
        datetime=df_feed.columns[0],
        open="Open", high="High", low="Low", close="Close", volume="Volume",
    )


# ======================================================================
# Portfolio tracker
# ======================================================================

class _Tracker(bt.Analyzer):
    def __init__(self):
        self.values: list[float] = []
        self.dates: list = []

    def next(self):
        self.values.append(self.strategy.broker.getvalue())
        self.dates.append(self.strategy.datas[0].datetime.date(0))

    def get_analysis(self):
        return pd.Series(self.values, index=self.dates)


# ======================================================================
# Metrics
# ======================================================================

RISK_FREE_RATE = 0.04


def _annual_return(values: pd.Series) -> float:
    if len(values) < 2:
        return 0.0
    total = values.iloc[-1] / values.iloc[0] - 1
    years = len(values) / 252
    if years <= 0:
        return 0.0
    return float((1 + total) ** (1 / years) - 1)


def _sharpe(values: pd.Series) -> float:
    if len(values) < 10:
        return 0.0
    returns = values.pct_change().dropna()
    ann_ret = _annual_return(values)
    ann_vol = returns.std() * np.sqrt(252)
    if ann_vol == 0:
        return 0.0
    return float((ann_ret - RISK_FREE_RATE) / ann_vol)


def _max_drawdown(values: pd.Series) -> float:
    if len(values) < 2:
        return 0.0
    cummax = values.cummax()
    dd = (values - cummax) / cummax
    return float(dd.min())


def _calmar(values: pd.Series) -> float:
    ann_ret = _annual_return(values)
    mdd = abs(_max_drawdown(values))
    if mdd == 0:
        return 0.0
    return float(ann_ret / mdd)


def evaluate(portfolio: pd.Series, benchmark: pd.Series | None = None) -> dict:
    ann_ret = _annual_return(portfolio)
    sharpe = _sharpe(portfolio)
    max_dd = _max_drawdown(portfolio)
    calmar = _calmar(portfolio)

    beat = None
    excess = None
    bench_ret = None
    bench_dd = None
    if benchmark is not None:
        bench_ret = _annual_return(benchmark)
        bench_dd = _max_drawdown(benchmark)
        beat = ann_ret > bench_ret
        excess = ann_ret - bench_ret

    # Score: sharpe base, drawdown penalty, excess bonus
    score = sharpe
    if max_dd < -0.30:
        score -= 0.1
    if max_dd < -0.40:
        score -= 0.3
    if beat:
        score += 0.05
    if excess and excess > 0.01:
        score += 0.05

    return {
        "score": score,
        "sharpe": sharpe,
        "annual_return": ann_ret,
        "max_drawdown": max_dd,
        "calmar": calmar,
        "beat_benchmark": beat,
        "excess_return": excess,
        "benchmark_return": bench_ret,
        "benchmark_drawdown": bench_dd,
    }


# ======================================================================
# Buy-and-hold benchmark
# ======================================================================

class _BuyHold(bt.Strategy):
    def __init__(self):
        self._done = False

    def next(self):
        if self._done:
            return
        self.order_target_percent(self.datas[0], 1.0)
        self._done = True


# ======================================================================
# Backtest execution
# ======================================================================

def _run(strategy_cls, data: dict[str, pd.DataFrame], cash: float) -> pd.Series:
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(cash)
    cerebro.broker.set_checksubmit(False)
    cerebro.broker.addcommissioninfo(_StockCommission())

    for ticker, df in data.items():
        cerebro.adddata(_make_feed(df, ticker), name=ticker)

    cerebro.addanalyzer(_Tracker, _name="tracker")
    cerebro.addstrategy(strategy_cls)
    results = cerebro.run()
    return results[0].analyzers.tracker.get_analysis()


def run_backtest(config: dict, strategy_cls) -> dict:
    """Run full backtest with benchmark comparison."""
    assets = config["assets"]
    tickers = [a["ticker"] for a in assets]
    weights = {a["ticker"]: a["weight"] for a in assets}
    roles = {a["ticker"]: a.get("role", "custom") for a in assets}
    period = config["period"]
    base_currency = config.get("currency", "USD").upper()
    cash_cny = config.get("cash", 100000)
    bench_ticker = config.get("benchmark", tickers[0])

    # Convert cash to USD for internal calculations
    cash = normalize_cash(base_currency, cash_cny)

    data = load_data(tickers, period["start"], period["end"])

    # Inject config into strategy
    strategy_cls._config = {
        "tickers": tickers,
        "weights": weights,
        "roles": roles,
    }

    portfolio = _run(strategy_cls, data, cash)

    bench_data = {bench_ticker: data[bench_ticker]}
    benchmark = _run(_BuyHold, bench_data, cash)

    return evaluate(portfolio, benchmark)


# ======================================================================
# Standardized output
# ======================================================================

def print_results(m: dict):
    print()
    print("---")
    print(f"score:             {m['score']:.6f}")
    print(f"sharpe:            {m['sharpe']:.6f}")
    print(f"annual_return:     {m['annual_return']:.6f}")
    print(f"max_drawdown:      {m['max_drawdown']:.6f}")
    print(f"calmar:            {m['calmar']:.6f}")
    print(f"beat_benchmark:    {m['beat_benchmark']}")
    print(f"excess_return:     {m['excess_return']:.6f}")
    print(f"benchmark_return:  {m['benchmark_return']:.6f}")
    print(f"benchmark_drawdown:{m['benchmark_drawdown']:.6f}")
    print("---")


# ======================================================================
# Main
# ======================================================================

if __name__ == "__main__":
    try:
        from strategy import Strategy
    except ImportError as e:
        print(f"[ERROR] Cannot import strategy.py: {e}")
        sys.exit(1)

    try:
        config = load_config()
        assets = config["assets"]
        tickers = [a["ticker"] for a in assets]
        period = config["period"]
        currency = config.get("currency", "USD")
        cash = config.get("cash", 100000)

        print(f"[config] tickers:   {', '.join(tickers)}")
        print(f"[config] benchmark: {config.get('benchmark', 'N/A')}")
        print(f"[config] period:    {period['start']} ~ {period['end']}")
        print(f"[config] currency:  {currency}, cash: {cash:,}")
        print(f"[config] commission: {COMMISSION*10000:.0f} bps ({COMMISSION*100:.2f}%)")
        print(f"[config] USD/CNY:   {USD_CNY}")
        print()

        metrics = run_backtest(config, Strategy)
        print_results(metrics)
    except Exception as e:
        print(f"\n[CRASH] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
