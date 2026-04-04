"""Configuration loading, profile selection, and market defaults.

SRP: This module is solely responsible for configuration concerns.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml


# ======================================================================
# Market defaults
# ======================================================================

BENCHMARK_DEFAULT: dict[str, str] = {"CNY": "000300.SS", "USD": "^GSPC"}
RISK_FREE_RATE: dict[str, float] = {"CNY": 0.025, "USD": 0.040}
COMMISSION_TABLE: dict[str, float] = {"USD": 0.0000, "CNY": 0.0010}
COMMISSION_DEFAULT = 0.0003


def get_commission(currency: str) -> float:
    """Get default commission rate for a currency."""
    return COMMISSION_TABLE.get(currency.upper(), COMMISSION_DEFAULT)


def get_risk_free_rate(currency: str) -> float:
    """Get risk-free rate for a currency."""
    return RISK_FREE_RATE.get(currency.upper(), 0.03)


def get_default_benchmark(currency: str) -> str:
    """Get default benchmark ticker for a currency."""
    return BENCHMARK_DEFAULT.get(currency.upper(), "^GSPC")


# ======================================================================
# Config loading
# ======================================================================

def load_config(config_path: str | None = None) -> dict:
    """Load YAML configuration file."""
    if config_path is None:
        config_path = "research.yaml"
    path = Path(config_path)
    if not path.exists():
        print(f"[ERROR] {config_path} not found")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def select_profile(config: dict, profile_name: str | None = None) -> tuple[str, dict]:
    """Select a profile from config. Returns (name, profile_dict)."""
    profiles = config.get("profiles", {})
    if not profiles:
        return ("default", config)
    if profile_name is None:
        profile_name = next(iter(profiles))
        print(f"[config] no --profile specified, using: {profile_name}")
    if profile_name not in profiles:
        print(
            f"[ERROR] profile '{profile_name}' not found. "
            f"Available: {', '.join(profiles)}"
        )
        sys.exit(1)
    return profile_name, profiles[profile_name]


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Override wins on conflicts."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def extract_deposits(config: dict) -> dict:
    """Parse deposit configuration into a normalized dict.

    Handles auto-calculation of deposit amounts when not explicitly set.
    """
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
            if freq == "weekly":
                n = max(1, (e - s).days // 7)
            else:
                n = max(1, (e.year - s.year) * 12 + (e.month - s.month))
            amount = remaining / n

    return {
        "initial": initial,
        "amount": amount,
        "freq": freq,
        "day": day,
        "day_mode": day_mode,
        "total_capital": total,
        "active": active,
        "amount_auto": amount_auto,
    }
