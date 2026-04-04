"""Backtest research toolkit — public API.

Refactored from monolithic engine.py into focused modules following SOLID principles.

SRP: Each module has one clear responsibility.
OCP: Data providers and metrics are extensible without modifying existing code.
DIP: Engine depends on abstractions (CacheManager, DataLoader, Evaluator).
ISP: Convenience functions for common operations; full control via classes.
"""

from .config import (
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
)
from .cache import CacheManager, get_cache_manager
from .data_provider import (
    DataProvider,
    YahooProvider,
    CNIndexProvider,
    CNEtfProvider,
    DataLoader,
    get_data_loader,
)
from .metrics import (
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
)
from .engine import (
    run_backtest,
    get_strategy_result,
    get_benchmark,
    load_data,
    clear_cache,
)
from .output import print_results
from .tracker import Tracker
from .commission import StockCommission, COMMISSION_DEFAULT
from .strategy import Strategy

__all__ = [
    # Config
    "load_config",
    "select_profile",
    "deep_merge",
    "extract_deposits",
    "get_commission",
    "get_risk_free_rate",
    "get_default_benchmark",
    # Cache
    "CacheManager",
    "get_cache_manager",
    # Data
    "DataProvider",
    "YahooProvider",
    "CNIndexProvider",
    "CNEtfProvider",
    "DataLoader",
    "get_data_loader",
    # Metrics
    "AnnualReturn",
    "SharpeRatio",
    "SortinoRatio",
    "MaxDrawdown",
    "CalmarRatio",
    "IRRMetric",
    "Evaluator",
    "annual_return",
    "max_drawdown",
    "sharpe_ratio",
    "sortino_ratio",
    # Engine
    "run_backtest",
    "get_strategy_result",
    "get_benchmark",
    "load_data",
    "clear_cache",
    # Output
    "print_results",
    # Backtrader components
    "Tracker",
    "StockCommission",
    "Strategy",
]
