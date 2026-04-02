"""
Autonomous Trading Strategy Research Engine (DO NOT MODIFY)

Reads research.yaml config, runs Strategy from strategy.py, outputs results.

Usage::

    uv run engine.py                          # run research.yaml, first profile
    uv run engine.py --profile <name>          # run specific profile
    uv run engine.py --config examples/cn_dividend.yaml  # run example config
"""

from __future__ import annotations

import inspect
import sys
import textwrap
from pathlib import Path

import backtrader as bt
import numpy as np
import pandas as pd
import pickle
import yaml
import yfinance as yf
import diskcache

# 缓存：按 ticker+period 做 key，7 天自动过期
_cache = diskcache.Cache("~/.cache/btresearch")
_CACHE_TTL = 7 * 24 * 60 * 60  # 7 days


# ======================================================================
# Config
# ======================================================================

def load_config(config_path: str | None = None) -> dict:
    if config_path is None:
        config_path = "research.yaml"
    path = Path(config_path)
    if not path.exists():
        print(f"[ERROR] {config_path} not found")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def select_profile(config: dict, profile_name: str | None) -> tuple[str, dict]:
    """Select a profile from config. Returns (name, profile_dict)."""
    profiles = config.get("profiles", {})
    if not profiles:
        # Legacy mode: no profiles defined, use top-level config as-is
        return ("default", config)

    if profile_name is None:
        # Use first profile
        profile_name = next(iter(profiles))
        print(f"[config] no --profile specified, using: {profile_name}")

    if profile_name not in profiles:
        print(f"[ERROR] profile '{profile_name}' not found. Available: {', '.join(profiles)}")
        sys.exit(1)

    return profile_name, profiles[profile_name]


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

# 交易费用：按市场区分（单边）
COMMISSION_TABLE = {
    "USD": 0.0000,  # 美股 ETF 券商大多 0 佣金
    "CNY": 0.0010,  # A 股 ETF 印花税+佣金约万十
}
COMMISSION_DEFAULT = 0.0003  # 未匹配时的默认值


def get_commission(currency: str) -> float:
    return COMMISSION_TABLE.get(currency.upper(), COMMISSION_DEFAULT)


class _StockCommission(bt.comminfo.CommInfoBase):
    params = (
        ("commission", COMMISSION_DEFAULT),
        ("stocklike", True),
        ("commtype", bt.comminfo.CommInfoBase.COMM_PERC),
        ("percabs", True),
    )


# ======================================================================
# FX rate
# ======================================================================

USD_CNY = 7.30


def normalize_cash(base_currency: str, cash: float) -> float:
    if base_currency.upper() == "CNY":
        return cash / USD_CNY
    return cash


# ======================================================================
# Data loading
# ======================================================================

def _is_cn_ticker(ticker: str) -> bool:
    """Check if ticker is a Chinese A-share ETF."""
    return ticker.endswith('.SS') or ticker.endswith('.SZ')


def _download_yahoo(ticker: str, start: str, end: str) -> pd.DataFrame:
    df = yf.download(ticker, start=start, end=end, progress=False)
    if df.empty:
        raise ValueError(f"Cannot download {ticker} from Yahoo")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.capitalize() for c in df.columns]
    return df


def _download_akshare(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Download A-share ETF data via akshare (sina interface)."""
    import akshare as ak
    # Convert ticker format: 510300.SS -> sh510300, 159209.SZ -> sz159209
    code = ticker.split('.')[0]
    prefix = 'sh' if ticker.endswith('.SS') else 'sz'
    sina_sym = f"{prefix}{code}"

    df = ak.fund_etf_hist_sina(symbol=sina_sym)
    if df is None or df.empty:
        raise ValueError(f"Cannot download {ticker} from akshare")

    # Normalize columns
    df = df.rename(columns={
        'date': 'Date', 'open': 'Open', 'high': 'High',
        'low': 'Low', 'close': 'Close', 'volume': 'Volume',
    })
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.set_index('Date')
    df = df.sort_index()

    # Filter by period
    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)
    df = df.loc[(df.index >= start_dt) & (df.index <= end_dt)]

    return df


def load_data(tickers: list[str], start: str, end: str) -> dict[str, pd.DataFrame]:
    data: dict[str, pd.DataFrame] = {}

    for ticker in tickers:
        cache_key = f"{ticker}:{start}:{end}"
        cached = _cache.get(cache_key)
        if cached is not None:
            data[ticker] = pickle.loads(cached)
            print(f"[cache] {ticker}: {len(data[ticker])} rows")
        else:
            print(f"[download] {ticker}...")
            if _is_cn_ticker(ticker):
                df = _download_akshare(ticker, start, end)
            else:
                df = _download_yahoo(ticker, start, end)
            _cache.set(cache_key, pickle.dumps(df), expire=_CACHE_TTL)
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

def _run(strategy_cls, data: dict[str, pd.DataFrame], cash: float, commission: float = COMMISSION_DEFAULT) -> pd.Series:
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(cash)
    cerebro.broker.set_checksubmit(False)
    cerebro.broker.addcommissioninfo(_StockCommission(commission=commission))

    for ticker, df in data.items():
        cerebro.adddata(_make_feed(df, ticker), name=ticker)

    cerebro.addanalyzer(_Tracker, _name="tracker")
    cerebro.addstrategy(strategy_cls)
    results = cerebro.run()
    return results[0].analyzers.tracker.get_analysis()


def _deep_merge(base: dict, override: dict) -> dict:
    """Shallow merge: override keys win, nested dicts merged recursively."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def run_backtest(config: dict, strategy_cls, profile: dict | None = None) -> dict:
    """Run full backtest with benchmark comparison."""
    # Profile can override top-level keys (assets, params, etc.)
    if profile:
        effective = _deep_merge(config, profile)
    else:
        effective = config

    assets = effective["assets"]
    tickers = [a["ticker"] for a in assets]
    weights = {a["ticker"]: a["weight"] for a in assets}
    roles = {a["ticker"]: a.get("role", "custom") for a in assets}
    period = effective["period"]
    base_currency = effective.get("currency", "USD").upper()
    cash_cny = effective.get("cash", 100000)
    bench_ticker = effective.get("benchmark", tickers[0])
    commission = get_commission(base_currency)

    cash = normalize_cash(base_currency, cash_cny)

    # Ensure benchmark data is loaded (may not be in assets)
    all_tickers = list(set(tickers + [bench_ticker]))
    data = load_data(all_tickers, period["start"], period["end"])

    # Merge profile params into strategy config
    strategy_config = {
        "tickers": tickers,
        "weights": weights,
        "roles": roles,
    }
    profile_params = effective.get("params", {})
    if profile_params:
        strategy_config["params"] = profile_params

    strategy_cls._config = strategy_config

    portfolio = _run(strategy_cls, data, cash, commission)

    bench_data = {bench_ticker: data[bench_ticker]}
    benchmark = _run(_BuyHold, bench_data, cash, commission)

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

def main():
    try:
        from strategy import Strategy
    except ImportError as e:
        print(f"[ERROR] Cannot import strategy.py: {e}")
        sys.exit(1)

    try:
        # Parse arguments
        profile_name = None
        config_path = None
        args = sys.argv[1:]
        if "--profile" in args:
            idx = args.index("--profile")
            if idx + 1 < len(args):
                profile_name = args[idx + 1]
        if "--config" in args:
            idx = args.index("--config")
            if idx + 1 < len(args):
                config_path = args[idx + 1]

        config = load_config(config_path)
        profile_name, profile = select_profile(config, profile_name)

        assets = config["assets"]
        tickers = [a["ticker"] for a in assets]
        period = config["period"]
        currency = config.get("currency", "USD")
        cash = config.get("cash", 100000)
        # Effective config = global + profile overrides
        effective = _deep_merge(config, profile)

        assets = effective["assets"]
        tickers = [a["ticker"] for a in assets]
        period = effective["period"]
        currency = effective.get("currency", "USD")
        cash = effective.get("cash", 100000)
        profile_params = effective.get("params", {})

        print(f"[config] profile:   {profile_name}")
        print(f"[config] desc:      {profile.get('description', '')}")
        print(f"[config] tickers:   {', '.join(tickers)}")
        weight_str = ', '.join(f'{a["ticker"]}:{a["weight"]}' for a in assets)
        print(f"[config] weights:   {weight_str}")
        print(f"[config] benchmark: {effective.get('benchmark', 'N/A')}")
        print(f"[config] period:    {period['start']} ~ {period['end']}")
        print(f"[config] currency:  {currency}, cash: {cash:,}")
        commission = get_commission(currency)
        print(f"[config] commission: {commission*10000:.0f} bps ({commission*100:.2f}%)")
        print(f"[config] USD/CNY:   {USD_CNY}")
        print(f"[config] params:    {profile_params}")
        print()

        metrics = run_backtest(config, Strategy, profile)
        print_results(metrics)
    except Exception as e:
        print(f"\n[CRASH] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
