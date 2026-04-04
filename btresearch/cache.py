"""Three-layer caching system with selective invalidation.

SRP: Encapsulates all caching concerns.
DIP: Provides CacheManager abstraction; consumers don't depend on diskcache directly.

Cache hierarchy:
  Layer 1 (data):       Raw ticker daily data (7d TTL)
  Layer 2 (benchmark):  Buy-hold daily NAV (90d TTL)
  Layer 3 (strategy):   Strategy daily NAV + deposit records (90d TTL)

Cache key design:
  - Changing metrics → recompute evaluate() only, no backtrader rerun
  - Changing strategy.py → invalidate ALL strategy caches (via MD5 hash)
  - Changing one profile → only that profile reruns
  - Benchmark results survive strategy changes and vice versa
"""

from __future__ import annotations

import hashlib
import json
import pickle
from pathlib import Path

import diskcache
import pandas as pd


class CacheManager:
    """Manages the three-layer caching system.

    All cache operations go through this class, making it easy to
    swap implementations or add instrumentation.
    """

    def __init__(
        self,
        data_dir: str = "~/.cache/btresearch/data",
        benchmark_dir: str = "~/.cache/btresearch/benchmark",
        strategy_dir: str = "~/.cache/btresearch/strategy",
        data_ttl: int = 7 * 24 * 60 * 60,
        exec_ttl: int = 90 * 24 * 60 * 60,
    ):
        self._data_cache = diskcache.Cache(data_dir)
        self._bench_cache = diskcache.Cache(benchmark_dir)
        self._strat_cache = diskcache.Cache(strategy_dir)
        self._data_ttl = data_ttl
        self._exec_ttl = exec_ttl
        self._strategy_hash: str | None = None

    # ------------------------------------------------------------------
    # Hash helpers
    # ------------------------------------------------------------------

    def get_strategy_hash(self, strategy_path: str | None = None) -> str:
        """MD5[:10] of strategy.py — changes invalidate ALL strategy caches."""
        if self._strategy_hash is None:
            if strategy_path is None:
                strategy_path = str(Path(__file__).parent / "strategy.py")
            p = Path(strategy_path)
            self._strategy_hash = hashlib.md5(p.read_bytes()).hexdigest()[:10]
        return self._strategy_hash

    @staticmethod
    def execution_config_hash(config: dict) -> str:
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

    # ------------------------------------------------------------------
    # Layer 1: Data cache
    # ------------------------------------------------------------------

    def get_data(self, key: str) -> pd.DataFrame | None:
        """Retrieve cached ticker data, or None if not cached."""
        cached = self._data_cache.get(key)
        if cached is not None:
            return pickle.loads(cached)
        return None

    def set_data(self, key: str, df: pd.DataFrame) -> None:
        """Store ticker data in cache."""
        self._data_cache.set(key, pickle.dumps(df), expire=self._data_ttl)

    # ------------------------------------------------------------------
    # Layer 2: Benchmark cache
    # ------------------------------------------------------------------

    def get_benchmark(self, key: str) -> pd.Series | None:
        """Retrieve cached benchmark data, or None if not cached."""
        cached = self._bench_cache.get(key)
        if cached is not None:
            return pickle.loads(cached)
        return None

    def set_benchmark(self, key: str, series: pd.Series) -> None:
        """Store benchmark data in cache."""
        self._bench_cache.set(key, pickle.dumps(series), expire=self._exec_ttl)

    # ------------------------------------------------------------------
    # Layer 3: Strategy cache
    # ------------------------------------------------------------------

    def get_strategy(self, key: str) -> dict | None:
        """Retrieve cached strategy result, or None if not cached."""
        cached = self._strat_cache.get(key)
        if cached is not None:
            return pickle.loads(cached)
        return None

    def set_strategy(self, key: str, result: dict) -> None:
        """Store strategy result in cache."""
        self._strat_cache.set(key, pickle.dumps(result), expire=self._exec_ttl)

    def strategy_cache_key(self, effective_config: dict) -> str:
        """Build cache key for a strategy config."""
        sh = self.get_strategy_hash()
        ch = self.execution_config_hash(effective_config)
        return f"{sh}:{ch}"

    # ------------------------------------------------------------------
    # Clear
    # ------------------------------------------------------------------

    def clear(self, layer: str | None = None) -> None:
        """Clear caches. layer: 'data'|'strategy'|'benchmark'|None (all)."""
        caches = {
            "data": self._data_cache,
            "strategy": self._strat_cache,
            "benchmark": self._bench_cache,
        }
        targets = {layer: caches[layer]} if layer else caches
        for name, cache in targets.items():
            cache.clear()
            print(f"[cache:clear] {name}")


# ------------------------------------------------------------------
# Module-level singleton
# ------------------------------------------------------------------

_cache_manager: CacheManager | None = None


def get_cache_manager() -> CacheManager:
    """Get the global CacheManager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
