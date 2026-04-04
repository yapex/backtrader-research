"""
Unified backtest engine with 3-layer caching.

Cache hierarchy:
  1. Data cache     — ticker 日线 (7d TTL, diskcache)
  2. Benchmark cache — buy-hold 每日净值 (90d TTL)
  3. Strategy cache  — 每日净值 + 投入记录 (90d TTL)

Key design: evaluate() is pure computation on cached value series.
Changing metrics (sortino → sharpe, scoring) → recompute only, no backtrader.

Usage::

    uv run engine.py                              # first profile in research.yaml
    uv run engine.py --profile <name>             # specific profile
    uv run engine.py --config examples/cn_dca.yaml
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import backtrader as bt
import diskcache
import numpy as np
import pandas as pd
import pickle
import yaml
import yfinance as yf

from strategy import Strategy

# ======================================================================
# Cache: Layer 1 — Raw data (7 day TTL)
# ======================================================================

_data_cache = diskcache.Cache("~/.cache/btresearch/data")
_DATA_TTL = 7 * 24 * 60 * 60

# ======================================================================
# Cache: Layer 2 & 3 — Execution results (90 day TTL)
# ======================================================================

_strat_cache = diskcache.Cache("~/.cache/btresearch/strategy")
_bench_cache = diskcache.Cache("~/.cache/btresearch/benchmark")
_EXEC_TTL = 90 * 24 * 60 * 60

_strategy_hash_value: str | None = None


def _get_strategy_hash() -> str:
    """MD5[:10] of strategy.py — changes invalidate ALL strategy caches."""
    global _strategy_hash_value
    if _strategy_hash_value is None:
        p = Path(__file__).parent / "strategy.py"
        _strategy_hash_value = hashlib.md5(p.read_bytes()).hexdigest()[:10]
    return _strategy_hash_value


def _execution_config_hash(config: dict) -> str:
    """MD5[:10] of config fields that affect backtest execution (NOT metrics)."""
    key_fields = {
        "assets": config.get("assets"),
        "period": config.get("period"),
        "currency": config.get("currency"),
        "commission": config.get("commission"),
        "deposits": config.get("deposits"),
        "params": config.get("params"),
        "cash": config.get("cash"),
    }
    return hashlib.md5(
        json.dumps(key_fields, sort_keys=True, default=str).encode()
    ).hexdigest()[:10]


# ======================================================================
# Market defaults
# ======================================================================

BENCHMARK_DEFAULT: dict[str, str] = {"CNY": "000300.SS", "USD": "^GSPC"}
RISK_FREE_RATE: dict[str, float] = {"CNY": 0.025, "USD": 0.040}
COMMISSION_TABLE: dict[str, float] = {"USD": 0.0000, "CNY": 0.0010}
COMMISSION_DEFAULT = 0.0003


def get_commission(currency: str) -> float:
    return COMMISSION_TABLE.get(currency.upper(), COMMISSION_DEFAULT)


def get_risk_free_rate(currency: str) -> float:
    return RISK_FREE_RATE.get(currency.upper(), 0.03)


def get_default_benchmark(currency: str) -> str:
    return BENCHMARK_DEFAULT.get(currency.upper(), "^GSPC")


class _StockCommission(bt.comminfo.CommInfoBase):
    params = (
        ("commission", COMMISSION_DEFAULT),
        ("stocklike", True),
        ("commtype", bt.comminfo.CommInfoBase.COMM_PERC),
        ("percabs", True),
    )


# ======================================================================
# Data loading (Layer 1 cache)
# ======================================================================

def _is_cn_ticker(t: str) -> bool:
    return t.lower().endswith(('.sh', '.sz', '.ss'))


def _is_cn_index(t: str) -> bool:
    tl = t.lower()
    return tl.endswith(('.ss', '.sz', '.sh')) and not tl.startswith(('51', '15', '13', '50'))


def _download_yahoo(ticker, start, end):
    df = yf.download(ticker, start=start, end=end, progress=False)
    if df.empty:
        raise ValueError(f"Cannot download {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.capitalize() for c in df.columns]
    return df


def _download_cn_index(ticker, start, end):
    import akshare as ak
    code, suffix = ticker.split('.')[0], ticker.split('.')[-1].upper()
    prefix = 'sh' if suffix in ('SS', 'SH') else 'sz'
    df = ak.stock_zh_index_daily(symbol=f"{prefix}{code}")
    if df is None or df.empty:
        raise ValueError(f"Cannot download {ticker}")
    df = df.rename(columns={'date': 'Date', 'open': 'Open', 'high': 'High',
                            'low': 'Low', 'close': 'Close', 'volume': 'Volume'})
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.set_index('Date').sort_index()
    return df.loc[(df.index >= pd.to_datetime(start)) & (df.index <= pd.to_datetime(end))]


def _download_cn_etf(ticker, start, end):
    """A-stock ETF: use yfinance auto-adjusted prices.

    yfinance Close is dividend-adjusted by default (no separate Adj Close
    column in newer versions). Raw prices from akshare/sina don't account
    for dividends, which underestimates returns significantly.
    """
    df = _download_yahoo(ticker, start, end)
    return df


def load_data(tickers, start, end):
    data = {}
    for ticker in tickers:
        cache_key = f"{ticker}:{start}:{end}"
        cached = _data_cache.get(cache_key)
        if cached is not None:
            data[ticker] = pickle.loads(cached)
            print(f"  [data:cache] {ticker}: {len(data[ticker])} rows")
        else:
            print(f"  [data:load]  {ticker}...")
            if _is_cn_index(ticker):
                df = _download_cn_index(ticker, start, end)
            elif _is_cn_ticker(ticker):
                df = _download_cn_etf(ticker, start, end)
            else:
                df = _download_yahoo(ticker, start, end)
            _data_cache.set(cache_key, pickle.dumps(df), expire=_DATA_TTL)
            data[ticker] = df
            print(f"  [data:done]  {ticker}: {len(df)} rows")
    return data


def _make_feed(df, ticker):
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
        dataname=df_feed, datetime=df_feed.columns[0],
        open="Open", high="High", low="Low", close="Close", volume="Volume",
    )


# ======================================================================
# Portfolio tracker
# ======================================================================

class _Tracker(bt.Analyzer):
    def __init__(self):
        self.values: list[float] = []
        self.dates: list = []
        self.total_deposited: float = 0.0
        self.deposit_dates: list = []
        self.deposit_amounts: list = []
        self._last_count: int = 0

    def next(self):
        self.values.append(self.strategy.broker.getvalue())
        self.dates.append(self.strategy.datas[0].datetime.date(0))
        trade_log = getattr(self.strategy, 'trade_log', [])
        new = trade_log[self._last_count:]
        for t in new:
            if t["type"] == "deposit":
                self.total_deposited += t["amount"]
                self.deposit_dates.append(t["date"])
                self.deposit_amounts.append(t["amount"])
        self._last_count = len(trade_log)

    def get_analysis(self):
        return {
            "value": pd.Series(self.values, index=self.dates),
            "total_deposited": self.total_deposited,
            "deposit_dates": self.deposit_dates,
            "deposit_amounts": self.deposit_amounts,
        }


# ======================================================================
# Config
# ======================================================================

def load_config(config_path=None):
    if config_path is None:
        config_path = "research.yaml"
    path = Path(config_path)
    if not path.exists():
        print(f"[ERROR] {config_path} not found")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def select_profile(config, profile_name=None):
    profiles = config.get("profiles", {})
    if not profiles:
        return ("default", config)
    if profile_name is None:
        profile_name = next(iter(profiles))
        print(f"[config] no --profile specified, using: {profile_name}")
    if profile_name not in profiles:
        print(f"[ERROR] profile '{profile_name}' not found. Available: {', '.join(profiles)}")
        sys.exit(1)
    return profile_name, profiles[profile_name]


def _deep_merge(base, override):
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _extract_deposits(config):
    dep = config.get("deposits", {})
    if not dep:
        return {"initial": 0, "amount": 0, "active": False}
    total = dep.get("total_capital", 0)
    initial = dep.get("initial", 0)
    amount = dep.get("amount", 0)
    freq = dep.get("freq", "monthly")
    day = dep.get("day", 1)
    day_mode = dep.get("day_mode", "exact")
    active = total > 0

    amount_auto = False
    if active and amount <= 0:
        amount_auto = True
        remaining = total - initial
        if remaining > 0:
            period = config.get("period", {})
            s = pd.to_datetime(period.get("start", "2020-01-01"))
            e = pd.to_datetime(period.get("end", "2025-12-31"))
            n = max(1, (e - s).days // 7) if freq == "weekly" else max(1, (e.year - s.year) * 12 + (e.month - s.month))
            amount = remaining / n
    return {"initial": initial, "amount": amount, "freq": freq, "day": day,
            "day_mode": day_mode, "total_capital": total, "active": active,
            "amount_auto": amount_auto}


# ======================================================================
# Metrics (pure computation — no I/O, no caching needed)
# ======================================================================

TRADING_DAYS_PER_YEAR = 252
SHARPE_MIN_DATA_POINTS = 10


def _annual_return(values: pd.Series) -> float:
    if len(values) < 2:
        return 0.0
    total = values.iloc[-1] / values.iloc[0] - 1
    years = len(values) / TRADING_DAYS_PER_YEAR
    return float((1 + total) ** (1 / years) - 1) if years > 0 else 0.0


def _sharpe(values: pd.Series, rf: float) -> float:
    if len(values) < SHARPE_MIN_DATA_POINTS:
        return 0.0
    returns = values.pct_change().dropna()
    ann_ret = _annual_return(values)
    ann_vol = returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
    return float((ann_ret - rf) / ann_vol) if ann_vol > 0 else 0.0


def _sortino(values: pd.Series, rf: float, threshold: float = 0.0) -> float:
    if len(values) < SHARPE_MIN_DATA_POINTS:
        return 0.0
    returns = values.pct_change().dropna()
    ann_ret = _annual_return(values)
    downside = returns[returns < threshold]
    if len(downside) == 0:
        return float('inf') if ann_ret > rf else 0.0
    dd = downside.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
    return float((ann_ret - rf) / dd) if dd > 0 else 0.0


def _max_drawdown(values: pd.Series) -> float:
    if len(values) < 2:
        return 0.0
    return float(((values - values.cummax()) / values.cummax()).min())


def _calmar(values: pd.Series) -> float:
    mdd = abs(_max_drawdown(values))
    return float(_annual_return(values) / mdd) if mdd > 0 else 0.0


def _compute_irr(portfolio: pd.Series, deposit_dates: list,
                deposit_amounts: list) -> float:
    """Compute annualized IRR from cashflow series using bisection.

    Uses sparse cashflow events (typically ~120 points) with bisection
    search — O(k * log(1/eps)) where k = number of events.
    This is ~40000x faster than the old polynomial-root approach which
    expanded to degree ~2430 and called np.roots() (O(n^3)).
    """
    if not deposit_dates:
        return 0.0

    # Build sparse cashflow events: (day_index, amount)
    date_to_idx = {d: i for i, d in enumerate(portfolio.index)}
    events = []
    for dt, amt in zip(deposit_dates, deposit_amounts):
        if dt in date_to_idx:
            events.append((date_to_idx[dt], -amt))
    events.append((len(portfolio) - 1, portfolio.iloc[-1]))

    # Sort by day, merge same-day
    events.sort()
    condensed = []
    prev_day = None
    for day, amt in events:
        if day == prev_day:
            condensed[-1] = (day, condensed[-1][1] + amt)
        else:
            condensed.append((day, amt))
            prev_day = day

    # Remove leading zeros
    while condensed and condensed[0][1] == 0:
        condensed.pop(0)
    if len(condensed) < 2 or condensed[-1][1] <= 0:
        return 0.0

    # Convert to numpy arrays for fast NPV evaluation
    days = np.array([e[0] for e in condensed], dtype=np.float64)
    amts = np.array([e[1] for e in condensed], dtype=np.float64)

    def npv(rate):
        return float(np.sum(amts / (1.0 + rate) ** days))

    # Find bracket for bisection
    lo, hi = -0.01, 0.01
    f_lo, f_hi = npv(lo), npv(hi)
    if f_lo * f_hi > 0:
        lo, hi = -0.5, 0.5
        f_lo, f_hi = npv(lo), npv(hi)
    if f_lo * f_hi > 0:
        # Scan for valid bracket
        for r_test in [0.001, 0.0001, 0.01, 0.05, -0.001, -0.05, -0.1]:
            f_test = npv(r_test)
            if f_lo != 0.0 and f_test * f_lo < 0:
                hi, f_hi = r_test, f_test
                break
            elif f_hi != 0.0 and f_test * f_hi < 0:
                lo, f_lo = r_test, f_test
                break
        else:
            return 0.0

    # Bisection
    for _ in range(200):
        mid = (lo + hi) / 2.0
        f_mid = npv(mid)
        if abs(f_mid) < 1e-10 or (hi - lo) < 1e-14:
            break
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid

    daily = (lo + hi) / 2.0
    if abs(daily) >= 1.0:
        return 0.0
    return float((1 + daily) ** TRADING_DAYS_PER_YEAR - 1)


def evaluate(portfolio: pd.Series, benchmark: pd.Series | None,
             tracker_data: dict, currency: str = "USD",
             risk_free_rate: float | None = None) -> dict:
    """Pure computation on cached value series. No I/O."""
    rf = risk_free_rate or get_risk_free_rate(currency)

    deposit_dates = tracker_data.get("deposit_dates", [])
    deposit_amounts = tracker_data.get("deposit_amounts", [])
    total_deposited = tracker_data.get("total_deposited", 0)
    deposit_count = len(deposit_dates)
    final_value = portfolio.iloc[-1]
    max_dd = _max_drawdown(portfolio)

    # Determine meaningful start point for return metrics
    if deposit_dates and deposit_dates[0] in portfolio.index:
        sub = portfolio.iloc[portfolio.index.get_loc(deposit_dates[0]):]
    else:
        sub = portfolio

    ann_ret = _annual_return(sub)
    sharpe = _sharpe(sub, rf)
    sortino = _sortino(sub, rf)
    calmar = _calmar(sub)

    # IRR & total return (meaningful when deposits exist)
    irr = _compute_irr(portfolio, deposit_dates, deposit_amounts)
    total_return = (final_value - total_deposited) / total_deposited if total_deposited > 0 else 0.0

    # Total return on capital (annualized over FULL period)
    # This is the correct metric for "I have X capital from day 1, how to invest?"
    # Unlike IRR, it accounts for idle cash sitting on the sidelines.
    if total_deposited > 0:
        full_years = len(portfolio) / TRADING_DAYS_PER_YEAR
        capital_return_annualized = float(
            (1 + total_return) ** (1 / full_years) - 1
        ) if full_years > 0 else 0.0
    else:
        capital_return_annualized = ann_ret

    # Benchmark (always buy-and-hold)
    bench_ret = _annual_return(benchmark) if benchmark is not None else None
    bench_dd = _max_drawdown(benchmark) if benchmark is not None else None

    # Use total return on capital for DCA, ann_ret for allocation
    strategy_return = capital_return_annualized if deposit_count > 0 else ann_ret
    beat = strategy_return > bench_ret if bench_ret is not None else None
    excess = strategy_return - bench_ret if bench_ret is not None else None
    passed = beat if beat is not None else False

    return {
        "sortino": sortino,
        "sharpe": sharpe,
        "calmar": calmar,
        "annual_return": ann_ret,
        "irr": irr,
        "total_return": total_return,
        "capital_return_annualized": capital_return_annualized,
        "max_drawdown": max_dd,
        "passed": passed,
        "total_deposited": total_deposited,
        "final_value": final_value,
        "deposit_count": deposit_count,
        "beat_benchmark": beat,
        "excess_return": excess,
        "benchmark_return": bench_ret,
        "benchmark_drawdown": bench_dd,
    }


# ======================================================================
# Backtest execution (internal, used by cached getters)
# ======================================================================

def _run(data, strategy_config, cash, commission):
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(cash)
    cerebro.broker.set_checksubmit(False)
    cerebro.broker.addcommissioninfo(_StockCommission(commission=commission))
    for ticker, df in data.items():
        cerebro.adddata(_make_feed(df, ticker), name=ticker)
    Strategy._config = strategy_config
    cerebro.addanalyzer(_Tracker, _name="tracker")
    cerebro.addstrategy(Strategy)
    results = cerebro.run()
    return results[0].analyzers.tracker.get_analysis(), results[0].trade_log


def _run_buyhold(data, cash, commission):
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(cash)
    cerebro.broker.set_checksubmit(False)
    cerebro.broker.addcommissioninfo(_StockCommission(commission=commission))
    for ticker, df in data.items():
        cerebro.adddata(_make_feed(df, ticker), name=ticker)

    class _BuyAll(bt.Strategy):
        def __init__(self):
            self._bought = False
        def next(self):
            if not self._bought:
                self.order_target_percent(self.datas[0], 0.98)
                self._bought = True

    cerebro.addanalyzer(_Tracker, _name="tracker")
    cerebro.addstrategy(_BuyAll)
    results = cerebro.run()
    return results[0].analyzers.tracker.get_analysis()["value"]


# ======================================================================
# Cached execution getters (Layer 2 & 3)
# ======================================================================

def _get_strategy_result(effective_config: dict) -> dict:
    """Get cached or compute strategy portfolio data.

    Cache key: strategy_hash : config_hash
    Invalidated by: strategy.py changes OR config changes
    Survives: metrics changes, evaluate() changes
    """
    sh = _get_strategy_hash()
    ch = _execution_config_hash(effective_config)
    cache_key = f"{sh}:{ch}"

    cached = _strat_cache.get(cache_key)
    if cached is not None:
        print(f"  [strat:hit]  {cache_key}")
        return pickle.loads(cached)

    print(f"  [strat:miss] {cache_key}")

    assets = effective_config["assets"]
    tickers = [a["ticker"] for a in assets]
    weights = {a["ticker"]: a["weight"] for a in assets}
    deposits_cfg = _extract_deposits(effective_config)
    period = effective_config["period"]
    currency = effective_config.get("currency", "USD").upper()
    commission = effective_config.get("commission", get_commission(currency))

    if deposits_cfg["active"]:
        cash = max(deposits_cfg["initial"], 1.0)
    else:
        cash = effective_config.get("cash", 100000)

    bench_ticker = effective_config.get("benchmark", get_default_benchmark(currency))
    all_tickers = list(set(tickers + ([bench_ticker] if bench_ticker else [])))
    data = load_data(all_tickers, period["start"], period["end"])

    strategy_config = {
        "tickers": tickers, "weights": weights,
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
    _strat_cache.set(cache_key, pickle.dumps(result), expire=_EXEC_TTL)
    return result


def _get_benchmark(ticker: str, period: dict, cash: float, commission: float) -> pd.Series:
    """Get cached or compute buy-hold benchmark.

    Cache key: ticker:period:cash:commission
    Survives: strategy changes, metrics changes
    """
    cache_key = f"{ticker}:{period['start']}:{period['end']}:{cash}:{commission}"

    cached = _bench_cache.get(cache_key)
    if cached is not None:
        print(f"  [bench:hit]  {ticker}")
        return pickle.loads(cached)

    print(f"  [bench:miss] {ticker}")
    data = load_data([ticker], period["start"], period["end"])
    result = _run_buyhold({ticker: data[ticker]}, cash, commission)
    _bench_cache.set(cache_key, pickle.dumps(result), expire=_EXEC_TTL)
    return result


# ======================================================================
# Public API
# ======================================================================

def run_backtest(config, profile=None):
    """Run backtest with 3-layer caching. Returns metrics dict."""
    effective = _deep_merge(config, profile) if profile else config
    deposits_cfg = _extract_deposits(effective)
    currency = effective.get("currency", "USD").upper()
    commission = effective.get("commission", get_commission(currency))
    period = effective["period"]
    bench_ticker = effective.get("benchmark", get_default_benchmark(currency))

    # Layer 3: strategy result (cached)
    strat = _get_strategy_result(effective)

    # Layer 2: benchmark (cached)
    if deposits_cfg["active"]:
        bench_cash = deposits_cfg["total_capital"]
    else:
        bench_cash = effective.get("cash", 100000)

    benchmark = None
    if bench_ticker:
        benchmark = _get_benchmark(bench_ticker, period, bench_cash, commission)

    # Pure computation (instant, no caching needed)
    tracker_data = {
        "value": strat["portfolio"],
        "total_deposited": strat["total_deposited"],
        "deposit_dates": strat["deposit_dates"],
        "deposit_amounts": strat["deposit_amounts"],
    }

    return evaluate(strat["portfolio"], benchmark, tracker_data,
                    currency=currency, risk_free_rate=effective.get("risk_free_rate"))


def clear_cache(layer: str | None = None):
    """Clear execution caches. layer: 'data'|'strategy'|'benchmark'|None (all)."""
    caches = {
        "data": _data_cache,
        "strategy": _strat_cache,
        "benchmark": _bench_cache,
    }
    targets = {layer: caches[layer]} if layer else caches
    for name, cache in targets.items():
        cache.clear()
        print(f"[cache:clear] {name}")


# ======================================================================
# Output
# ======================================================================

def print_results(m, effective, profile_name="", desc=""):
    passed = "✅" if m.get("passed") else "❌ 未跑赢基准"
    is_dca = m.get("deposit_count", 0) > 0

    print()
    print("=" * 60)
    if desc:
        print(f"  {desc}")
    print(f"  sortino:           {m['sortino']:>12.6f}  {passed}")

    ret_label = "总资金年化" if is_dca else "年化收益"
    ret_value = m["capital_return_annualized"] if is_dca else m["annual_return"]
    print(f"  {ret_label}:       {ret_value:>+11.2%}")
    print(f"  最大回撤:         {m['max_drawdown']:>11.2%}")

    # Benchmark
    if m.get("benchmark_return") is not None:
        print()
        print(f"  【vs 基准（纯买 {effective.get('benchmark', '?')}）】")
        print(f"  基准年化:         {m['benchmark_return']:>+11.2%}")
        print(f"  基准回撤:         {m['benchmark_drawdown']:>11.2%}")
        if m.get("beat_benchmark") is not None:
            print(f"  跑赢基准:         {'是 ✅' if m['beat_benchmark'] else '否 ❌'}")
        if m.get("excess_return") is not None:
            print(f"  超额收益:         {m['excess_return']:>+11.2%}")

    # DCA details
    if is_dca:
        print()
        print(f"  【定投明细】")
        print(f"  累计投入:         {m['total_deposited']:>11,.0f}")
        print(f"  期末市值:         {m['final_value']:>11,.0f}")
        print(f"  总收益率:         {m['total_return']:>+11.2%}")
        print(f"  总资金年化:       {m['capital_return_annualized']:>+11.2%}")
        print(f"  IRR (仅供参考):   {m['irr']:>+11.2%}")
        print(f"  定投期数:         {m['deposit_count']:>11d}")

    print("=" * 60)


# ======================================================================
# Main
# ======================================================================

def main():
    try:
        profile_name = config_path = None
        args = sys.argv[1:]
        for i, a in enumerate(args):
            if a == "--profile" and i + 1 < len(args):
                profile_name = args[i + 1]
            if a == "--config" and i + 1 < len(args):
                config_path = args[i + 1]

        config = load_config(config_path)
        profile_name, profile = select_profile(config, profile_name)
        effective = _deep_merge(config, profile) if profile else config

        assets = effective["assets"]
        tickers = [a["ticker"] for a in assets]
        period = effective["period"]
        currency = effective.get("currency", "USD")
        deposits_cfg = _extract_deposits(effective)
        is_dca = deposits_cfg["active"]

        print(f"[config] profile:    {profile_name}")
        desc = profile.get("description", "")
        if desc:
            print(f"[config] desc:       {desc}")
        print(f"[config] tickers:    {', '.join(tickers)}")
        weight_str = ', '.join(f"{a['ticker']}:{a['weight']}" for a in assets)
        print(f"[config] weights:    {weight_str}")
        print(f"[config] period:     {period['start']} ~ {period['end']}")
        print(f"[config] currency:   {currency}")
        print(f"[config] commission: {get_commission(currency)*10000:.0f} bps")

        if is_dca:
            print(f"[config] total_cap:  {deposits_cfg['total_capital']:,}")
            print(f"[config] initial:    {deposits_cfg['initial']:,}")
            amt_label = "auto" if deposits_cfg.get("amount_auto") else "fixed"
            print(f"[config] amount:     {deposits_cfg['amount']:,.2f} ({amt_label})")

        params = effective.get("params", {})
        if params:
            print(f"[config] params:     {params}")

        bench_ticker = effective.get("benchmark", get_default_benchmark(currency))
        print(f"[config] benchmark:  {bench_ticker}")
        print()

        metrics = run_backtest(config, profile)
        print_results(metrics, effective, profile_name, desc)

    except Exception as e:
        print(f"\n[CRASH] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
