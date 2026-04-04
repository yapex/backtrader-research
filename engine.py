"""Backward-compatible facade + CLI entry point.

All internal logic has been moved to the `btresearch` package following
SOLID principles. This module re-exports the public API and provides
backward-compatible aliases for previously-private names.

Usage (unchanged):
    uv run engine.py --config examples/cn_permanent.yaml
    uv run engine.py --profile <name>
"""

from __future__ import annotations

import sys
from pathlib import Path

# ======================================================================
# Public API re-exports
# ======================================================================

from btresearch import (
    # Config
    load_config,
    select_profile,
    deep_merge,
    extract_deposits,
    get_commission,
    get_risk_free_rate,
    get_default_benchmark,
    BENCHMARK_DEFAULT,
    RISK_FREE_RATE,
    COMMISSION_TABLE,
    COMMISSION_DEFAULT,
    # Cache
    CacheManager,
    get_cache_manager,
    # Data
    DataProvider,
    YahooProvider,
    CNIndexProvider,
    CNEtfProvider,
    DataLoader,
    get_data_loader,
    # Metrics
    AnnualReturn,
    SharpeRatio,
    SortinoRatio,
    MaxDrawdown,
    CalmarRatio,
    IRRMetric,
    Evaluator,
    annual_return,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
    TRADING_DAYS_PER_YEAR,
    # Engine
    run_backtest,
    get_strategy_result,
    get_benchmark,
    load_data,
    clear_cache,
    # Output
    print_results,
    # Backtrader components
    Tracker,
    StockCommission,
    Strategy,
)

# ======================================================================
# Backward-compatible aliases for previously-private names
# ======================================================================

_deep_merge = deep_merge
_annual_return = annual_return
_max_drawdown = max_drawdown


def _get_strategy_hash():
    return get_cache_manager().get_strategy_hash()


def _execution_config_hash(config: dict) -> str:
    return CacheManager.execution_config_hash(config)


# ======================================================================
# Quick modes: --buy / --compare / --stock-bond / --permanent (no YAML)
# ======================================================================

# Fixed assets for templates
_BOND = "511010.SS"   # 国债ETF
_GOLD = "518880.SS"   # 黄金ETF
_CASH = "511990.SS"   # 货币基金


def _parse_period(period_str: str) -> tuple[str, str]:
    """Parse '2019-2025' or '2019-01-01:2025-12-31' into (start, end)."""
    if ':' in period_str:
        return period_str.split(':', 1)
    parts = period_str.split('-')
    return f"{parts[0]}-01-01", f"{parts[1]}-12-31"


def _dca_deposit(total_capital: float, initial: float = 0) -> dict:
    """Build deposit config for DCA mode."""
    return {
        "total_capital": total_capital,
        "initial": initial,
        "freq": "monthly",
        "day": 1,
        "day_mode": "first",
    }


def _template_config(
    stock_ticker: str,
    template: str,
    period_start: str,
    period_end: str,
    benchmark: str | None,
    cash: float,
    currency: str,
    dca: bool = False,
    rebalance_freq: str = "monthly",
) -> dict:
    """Build config from a template. stock_ticker fills the 'stock' slot."""
    if template == "stock-bond":
        assets = [
            {"ticker": stock_ticker, "role": "equity", "weight": 0.3},
            {"ticker": _BOND, "role": "bond", "weight": 0.7},
        ]
    elif template == "permanent":
        assets = [
            {"ticker": stock_ticker, "role": "equity", "weight": 0.25},
            {"ticker": _BOND, "role": "bond", "weight": 0.25},
            {"ticker": _GOLD, "role": "gold", "weight": 0.25},
            {"ticker": _CASH, "role": "cash", "weight": 0.25},
        ]
    else:
        assets = [{"ticker": stock_ticker, "weight": 1.0}]

    config: dict = {
        "assets": assets,
        "period": {"start": period_start, "end": period_end},
        "currency": currency,
        "benchmark": benchmark or get_default_benchmark(currency),
        "params": {"rebalance_freq": rebalance_freq, "stop_loss": None},
    }

    if dca:
        config["deposits"] = _dca_deposit(cash)
    else:
        config["cash"] = cash
        config["deposits"] = {"total_capital": 0}

    return config


def _run_template(
    stock_ticker: str,
    template: str,
    period_start: str,
    period_end: str,
    benchmark: str | None,
    cash: float,
    currency: str,
    dca: bool = False,
    rebalance_freq: str = "monthly",
) -> dict:
    """Run a template backtest, return metrics."""
    config = _template_config(
        stock_ticker, template, period_start, period_end,
        benchmark, cash, currency, dca, rebalance_freq,
    )
    return run_backtest(config)


def _run_sweep(
    stock_tickers: list[str],
    template: str,
    period_start: str,
    period_end: str,
    benchmark: str | None,
    cash: float,
    currency: str,
    dca: bool = False,
    rebalance_freq: str = "monthly",
) -> list[tuple[str, dict]]:
    """Run a template for multiple stock tickers, return [(ticker, metrics)]."""
    results = []
    for t in stock_tickers:
        m = _run_template(
            t, template, period_start, period_end,
            benchmark, cash, currency, dca, rebalance_freq,
        )
        results.append((t, m))
    return results


def _label(template: str, dca: bool, rebalance_freq: str) -> str:
    """Human-readable label for a template + mode combination."""
    names = {"stock-bond": "股债30/70", "permanent": "永久组合"}
    parts = [names.get(template, template)]
    if dca:
        parts.append("定投")
    else:
        parts.append("一次性")
    return " ".join(parts)


def _print_table(
    results: list[tuple[str, dict]],
    bench_ticker: str,
    show_dca: bool = False,
) -> None:
    """Print a formatted comparison table."""
    w = max(len(t) for t, _ in results)
    w = max(w, len(bench_ticker) + 3)

    if show_dca:
        header = f"  {'基金':<{w}s}  {'总资金年化':>9s}  {'最大回撤':>9s}  {'Sortino':>8s}  {'超额收益':>9s}  {'跑赢':>4s}"
        sort_key = lambda x: x[1].get("capital_return_annualized", 0)
    else:
        header = f"  {'基金':<{w}s}  {'年化收益':>9s}  {'最大回撤':>9s}  {'Sortino':>8s}  {'超额收益':>9s}  {'跑赢':>4s}"
        sort_key = lambda x: x[1].get("annual_return", 0)

    sep = "  " + "─" * len(header)
    print(header)
    print(sep)

    for ticker, m in sorted(results, key=sort_key, reverse=True):
        ann = m["capital_return_annualized"] if show_dca else m["annual_return"]
        dd = m["max_drawdown"]
        so = m["sortino"]
        exc = m.get("excess_return")
        beat = m.get("beat_benchmark")
        mark = "✅" if beat else "❌"
        exc_str = f"{exc:+.2%}" if exc is not None else "—"
        print(f"  {ticker:<{w}s}  {ann:>+8.2%}  {dd:>8.2%}  {so:>7.3f}  {exc_str:>9s}  {mark:>4s}")

    bench_m = results[0][1] if results else {}
    bench_ann = bench_m.get("benchmark_return")
    bench_dd = bench_m.get("benchmark_drawdown")
    if bench_ann is not None:
        print(sep)
        print(f"  {bench_ticker + ' (基准)':<{w}s}  {bench_ann:>+8.2%}  {bench_dd:>8.2%}")
    print()


# ======================================================================
# Machine-readable output (--json mode)
# ======================================================================

# Metrics to output in --json mode (ordered for readability)
_JSON_METRIC_KEYS = [
    ("sortino", "sortino"),
    ("sharpe", "sharpe"),
    ("calmar", "calmar"),
    ("annual_return", "annual_return"),
    ("max_drawdown", "max_drawdown"),
    ("irr", "irr"),
    ("total_return", "total_return"),
    ("capital_return_annualized", "capital_return_annualized"),
    ("final_value", "final_value"),
    ("total_deposited", "total_deposited"),
    ("deposit_count", "deposit_count"),
    ("beat_benchmark", "beat_benchmark"),
    ("excess_return", "excess_return"),
    ("benchmark_return", "benchmark_return"),
    ("benchmark_drawdown", "benchmark_drawdown"),
]


def _print_json_metrics(m: dict) -> None:
    """Print metrics as 'key: value' lines. Designed for grep/sed parsing."""
    for key, _ in _JSON_METRIC_KEYS:
        v = m.get(key)
        if v is None:
            continue
        if isinstance(v, bool):
            print(f"{key}: {int(v)}")
        elif isinstance(v, float):
            print(f"{key}: {v:.6f}")
        else:
            print(f"{key}: {v}")


def _print_json_crash(error_msg: str) -> None:
    """Print zero-metrics on crash. LLM sees these and logs 'crash'."""
    for key, _ in _JSON_METRIC_KEYS:
        if key in ("beat_benchmark", "deposit_count"):
            print(f"{key}: 0")
        else:
            print(f"{key}: 0.000000")
    print(f"crash: 1")
    print(f"crash_reason: {error_msg}", file=sys.stderr)


def _batch_run(yaml_files: list[str], json_mode: bool = False) -> None:
    """Run multiple YAML configs, output TSV summary.

    Each config is run independently. Crashes are recorded as zero-metrics.
    Output is a TSV to stdout (one line per config).
    """
    _orig_stdout = sys.stdout
    if not json_mode:
        sys.stdout = sys.stderr

    cols = ["config", "sortino", "strategy_return", "max_drawdown", "calmar",
            "sharpe", "deposit_count", "beat_benchmark", "excess_return", "final_value", "crash"]
    rows = []

    for i, fpath in enumerate(yaml_files, 1):
        label = Path(fpath).stem
        print(f"\r[{i}/{len(yaml_files)}] {label:<30s}", end="", flush=True, file=sys.stderr)
        try:
            config = load_config(fpath)
            m = _run_single_config(config)
            # Use capital_return_annualized for DCA, annual_return for lump sum
            is_dca = m.get("deposit_count", 0) > 0
            strat_ret = m["capital_return_annualized"] if is_dca else m["annual_return"]
            rows.append({
                "config": label,
                "sortino": f"{m['sortino']:.6f}",
                "strategy_return": f"{strat_ret:.6f}",
                "max_drawdown": f"{m['max_drawdown']:.6f}",
                "calmar": f"{m['calmar']:.6f}",
                "sharpe": f"{m['sharpe']:.6f}",
                "deposit_count": m.get("deposit_count", 0),
                "beat_benchmark": int(m.get("beat_benchmark", 0)),
                "excess_return": f"{m.get('excess_return', 0):.6f}",
                "final_value": f"{m['final_value']:.0f}",
                "crash": 0,
            })
        except Exception as e:
            rows.append({
                "config": label,
                "sortino": "0.000000", "strategy_return": "0.000000",
                "max_drawdown": "0.000000", "calmar": "0.000000",
                "sharpe": "0.000000", "deposit_count": 0,
                "beat_benchmark": 0,
                "excess_return": "0.000000", "final_value": "0",
                "crash": 1,
            })
            print(f"\n  [CRASH] {label}: {e}", file=sys.stderr)

    # Output TSV to stdout
    sys.stdout = _orig_stdout
    print("\t".join(cols))
    for r in rows:
        print("\t".join(str(r[c]) for c in cols))


# ======================================================================
# CLI entry point
# ======================================================================

def _run_single_config(config: dict, profile: dict | None = None) -> dict:
    """Run a single config and return metrics dict. Raises on failure."""
    return run_backtest(config, profile)


def main():
    """CLI entry point.

    Modes:
      --config FILE [--profile NAME]   YAML config mode (original)
      --batch FILE [FILE ...]          Batch mode: run multiple YAMLs, output TSV
      --buy TICKER                      Single fund buy-and-hold
      --compare T1 T2 ...               Multi-fund buy-and-hold
      --stock-bond T1 T2 ...            Stock-bond 30/70 (swap stock slot)
      --permanent T1 T2 ...             Permanent portfolio (swap stock slot)

    Global flags: --json  --period  --benchmark  --cash  --currency  --dca

    --json: Output metrics as key: value lines (machine-readable). Log noise goes to stderr.
           Example: sortino: 0.723660\nannual_return: 0.0612\nmax_drawdown: -0.1246
    --batch: Run N YAML configs, output TSV with all results. Crash rows show 0s.
    """
    import sys
    import json as _json

    try:
        args = sys.argv[1:]

        # Global flags
        json_mode = "--json" in args
        batch_mode = "--batch" in args
        args = [a for a in args if a != "--json" and a != "--batch"]

        # ---- Batch mode: --batch c1.yaml c2.yaml ... ----
        if batch_mode:
            yaml_files = [a for a in args if not a.startswith("-")]
            if not yaml_files:
                print("[ERROR] --batch requires at least one YAML file", file=sys.stderr)
                sys.exit(1)
            _batch_run(yaml_files, json_mode)
            return

        # Redirect log noise to stderr in --json mode
        if json_mode:
            _orig_stdout = sys.stdout
            sys.stdout = sys.stderr

        # Detect mode
        mode = "config"  # default
        for a in args:
            if a in ("--buy", "--compare", "--stock-bond", "--permanent"):
                mode = a.lstrip("-")
                break

        # ---- Quick mode ----
        if mode in ("buy", "compare", "stock-bond", "permanent"):
            parser = _QuickArgParser(args)
            tickers = parser.tickers
            period_start, period_end = parser.period
            benchmark = parser.benchmark
            cash = parser.cash
            currency = parser.currency
            dca = parser.dca
            template = mode if mode in ("stock-bond", "permanent") else None
            rebalance_freq = parser.rebalance_freq

            if not tickers:
                print("[ERROR] No tickers specified")
                sys.exit(1)

            # Run
            if template:
                results = _run_sweep(
                    tickers, template, period_start, period_end,
                    benchmark, cash, currency, dca, rebalance_freq,
                )
                lbl = _label(template, dca, rebalance_freq)
                print(f"[sweep] {lbl}")
            else:
                results = []
                for t in tickers:
                    m = _run_template(t, "buy", period_start, period_end,
                                        benchmark, cash, currency)
                    results.append((t, m))

            print(f"[period]  {period_start} ~ {period_end}")
            print(f"[cash]    {cash:,.0f} {currency}")
            print(f"[bench]   {benchmark}")
            print()

            if mode == "buy" and len(results) == 1:
                ticker, m = results[0]
                effective = _template_config(ticker, "buy", period_start, period_end,
                                           benchmark, cash, currency)
                print_results(m, effective, ticker)
            else:
                _print_table(results, benchmark, show_dca=dca)
            return

        # ---- YAML config mode (original) ----
        profile_name = config_path = None
        for i, a in enumerate(args):
            if a == "--profile" and i + 1 < len(args):
                profile_name = args[i + 1]
            if a == "--config" and i + 1 < len(args):
                config_path = args[i + 1]

        config = load_config(config_path)
        profile_name, profile = select_profile(config, profile_name)
        effective = deep_merge(config, profile) if profile else config

        assets = effective["assets"]
        tickers = [a["ticker"] for a in assets]
        period = effective["period"]
        currency = effective.get("currency", "USD")
        deposits_cfg = extract_deposits(effective)
        is_dca = deposits_cfg["active"]

        print(f"[config] profile:    {profile_name}")
        desc = profile.get("description", "")
        if desc:
            print(f"[config] desc:       {desc}")
        print(f"[config] tickers:    {', '.join(tickers)}")
        weight_str = ", ".join(f"{a['ticker']}:{a['weight']}" for a in assets)
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

        # ---- Output ----
        if json_mode:
            sys.stdout = _orig_stdout
            _print_json_metrics(metrics)
        else:
            print_results(metrics, effective, profile_name, desc)

    except Exception as e:
        if json_mode:
            # Restore and print crash metrics
            sys.stdout = _orig_stdout
            _print_json_crash(str(e))
        else:
            print(f"\n[CRASH] {type(e).__name__}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
        sys.exit(1)


class _QuickArgParser:
    """Minimal arg parser for quick modes.

    Supports:
      TICKER... --period 2019-2025 --benchmark 510300.SS --cash 1000000 --currency CNY
                --dca --rebalance monthly|quarterly|yearly
    """

    def __init__(self, args: list[str]):
        self.tickers: list[str] = []
        self._period_str = "2014-2025"
        self.benchmark: str | None = None
        self.cash = 1_000_000
        self.currency = "CNY"
        self.dca = False
        self.rebalance_freq = "monthly"

        i = 0
        while i < len(args):
            a = args[i]
            if a in ("--buy", "--compare", "--stock-bond", "--permanent"):
                i += 1
                continue
            elif a == "--period" and i + 1 < len(args):
                self._period_str = args[i + 1]
                i += 2
            elif a == "--benchmark" and i + 1 < len(args):
                self.benchmark = args[i + 1]
                i += 2
            elif a == "--cash" and i + 1 < len(args):
                self.cash = float(args[i + 1])
                i += 2
            elif a == "--currency" and i + 1 < len(args):
                self.currency = args[i + 1]
                i += 2
            elif a == "--dca":
                self.dca = True
                i += 1
            elif a == "--rebalance" and i + 1 < len(args):
                self.rebalance_freq = args[i + 1]
                i += 2
            elif a.startswith("-"):
                i += 1  # skip unknown flags
            else:
                self.tickers.append(a)
                i += 1

    @property
    def period(self) -> tuple[str, str]:
        return _parse_period(self._period_str)


if __name__ == "__main__":
    main()
