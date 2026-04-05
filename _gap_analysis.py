"""Gap analysis: fix two experimental blind spots.

Blind spot 1: 7% threshold was never validated on US stocks.
  → Sweep thresholds 3%, 5%, 7%, 8%, 10% on US permanent portfolio (QQQ).

Blind spot 2: Crisis mode equity weight was always 5%, never varied.
  → Sweep crisis equity 0%, 3%, 5%, 10%, 15% for A-shares (沪深300).
"""

import sys
import copy
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from btresearch import run_backtest, clear_cache

# ======================================================================
# Experiment 1: US threshold sweep
# ======================================================================

US_CONFIG = {
    "benchmark": "^GSPC",
    "currency": "USD",
    "cash": 1_000_000,
    "deposits": {"total_capital": 0},
    "assets": [
        {"ticker": "QQQ", "role": "equity", "weight": 0.30},
        {"ticker": "AGG", "role": "bond", "weight": 0.2333},
        {"ticker": "GLD", "role": "gold", "weight": 0.2333},
        {"ticker": "SHY", "role": "cash", "weight": 0.2333},
    ],
    "period": {"start": "2005-01-01", "end": "2025-12-31"},
    "params": {"rebalance_freq": "never", "stop_loss": None},
}

THRESHOLDS = [0.03, 0.05, 0.07, 0.08, 0.10]


def experiment_us_threshold():
    """Sweep rebalance thresholds on US permanent portfolio."""
    print("=" * 80)
    print("  实验 1：美股阈值扫描（QQQ 永久组合，2005-2025）")
    print("=" * 80)
    print(f"  {'阈值':>6s}  {'Sortino':>8s}  {'年化':>8s}  {'回撤':>8s}  {'Calmar':>8s}")
    print("-" * 80)

    results = []
    for thresh in THRESHOLDS:
        cfg = copy.deepcopy(US_CONFIG)
        cfg["params"]["rebalance_threshold"] = thresh

        t0 = time.time()
        m = run_backtest(cfg)
        elapsed = time.time() - t0

        label = f"{thresh*100:.0f}%"
        print(
            f"  {label:>6s}  {m['sortino']:>8.3f}  "
            f"{m['annual_return']:>+7.2%}  {m['max_drawdown']:>7.2%}  "
            f"{m['calmar']:>8.3f}  ({elapsed:.1f}s)"
        )
        results.append((thresh, m))

    # Also run monthly baseline for comparison
    cfg_base = copy.deepcopy(US_CONFIG)
    cfg_base["params"]["rebalance_freq"] = "monthly"
    cfg_base["params"]["rebalance_threshold"] = None
    m_base = run_backtest(cfg_base)
    print(
        f"  {'月度':>6s}  {m_base['sortino']:>8.3f}  "
        f"{m_base['annual_return']:>+7.2%}  {m_base['max_drawdown']:>7.2%}  "
        f"{m_base['calmar']:>8.3f}  (基线)"
    )

    # Find best
    best = max(results, key=lambda x: x[1]["sortino"])
    best_thresh = best[0]
    print(f"\n  ✅ 美股最优阈值: {best_thresh*100:.0f}% (Sortino={best[1]['sortino']:.3f})")
    if best_thresh != 0.07:
        print(f"  ⚠️  与 A 股的 7% 不同！A 股结论不能直接套用美股")
    else:
        print(f"  ✅ 与 A 股一致，7% 是中美通用最优阈值")

    return results, m_base


# ======================================================================
# Experiment 2: Crisis equity sweep (A-shares)
# ======================================================================

CN_BASE = {
    "benchmark": "510300.SS",
    "currency": "CNY",
    "cash": 1_000_000,
    "deposits": {"total_capital": 0},
    "assets": [
        {"ticker": "510300.SS", "role": "equity", "weight": 0.25},
        {"ticker": "511010.SS", "role": "bond", "weight": 0.25},
        {"ticker": "518880.SS", "role": "gold", "weight": 0.25},
        {"ticker": "511990.SS", "role": "cash", "weight": 0.25},
    ],
    "period": {"start": "2014-01-01", "end": "2025-12-31"},
    "params": {
        "rebalance_freq": "never",
        "rebalance_threshold": 0.07,
        "stop_loss": 0.10,
        "stop_loss_mode": "crisis",
    },
}

CRISIS_EQUITY_LEVELS = [0.00, 0.03, 0.05, 0.10, 0.15]


def _make_crisis_weights(equity: float) -> dict:
    """Build crisis weights with given equity level.
    
    Distribute remaining (1 - equity) among bond/gold/cash in 40/35/20 ratio
    (the original optimal ratio for the non-equity portion).
    """
    remaining = 1.0 - equity
    bond = remaining * 0.40
    gold = remaining * 0.35
    cash = remaining * 0.25
    return {
        "510300.SS": equity,
        "511010.SS": bond,
        "518880.SS": gold,
        "511990.SS": cash,
    }


def experiment_cn_crisis_equity():
    """Sweep crisis equity weight for A-shares."""
    print("\n" + "=" * 80)
    print("  实验 2：A 股危机模式股票权重扫描（阈值 7%，止损 10%）")
    print("=" * 80)
    print(f"  {'危机股票':>8s}  {'危机权重(股/债/金/现)':>24s}  {'Sortino':>8s}  {'年化':>8s}  {'回撤':>8s}")
    print("-" * 100)

    results = []
    for eq in CRISIS_EQUITY_LEVELS:
        cfg = copy.deepcopy(CN_BASE)
        cw = _make_crisis_weights(eq)
        cfg["params"]["crisis_weights"] = cw

        t0 = time.time()
        m = run_backtest(cfg)
        elapsed = time.time() - t0

        cw_str = f"{eq*100:.0f}/{cw['511010.SS']*100:.0f}/{cw['518880.SS']*100:.0f}/{cw['511990.SS']*100:.0f}"
        label = f"{eq*100:.0f}%"
        print(
            f"  {label:>8s}  {cw_str:>24s}  {m['sortino']:>8.3f}  "
            f"{m['annual_return']:>+7.2%}  {m['max_drawdown']:>7.2%}  ({elapsed:.1f}s)"
        )
        results.append((eq, cw, m))

    # Also run no-crisis baseline
    cfg_base = copy.deepcopy(CN_BASE)
    cfg_base["params"]["stop_loss"] = None
    cfg_base["params"]["stop_loss_mode"] = None
    cfg_base["params"]["crisis_weights"] = None
    m_base = run_backtest(cfg_base)
    print(
        f"  {'无危机':>8s}  {'25/25/25/25':>24s}  {m_base['sortino']:>8.3f}  "
        f"{m_base['annual_return']:>+7.2%}  {m_base['max_drawdown']:>7.2%}  (对照)"
    )

    # Find best
    best = max(results, key=lambda x: x[2]["sortino"])
    best_eq = best[0]
    best_cw = best[1]
    print(f"\n  ✅ 最优危机股票权重: {best_eq*100:.0f}%")
    print(f"     危机权重: {best_eq*100:.0f}/{best_cw['511010.SS']*100:.0f}/{best_cw['518880.SS']*100:.0f}/{best_cw['511990.SS']*100:.0f}")
    print(f"     Sortino: {best[2]['sortino']:.3f}")

    # Compare with original 5%
    orig = [r for r in results if abs(r[0] - 0.05) < 0.001]
    if orig and abs(best_eq - 0.05) > 0.001:
        print(f"  ⚠️  原报告的 5% 并非最优！最优是 {best_eq*100:.0f}%")
    elif orig and abs(best_eq - 0.05) < 0.001:
        print(f"  ✅ 原报告的 5% 确认最优")

    return results, m_base


# ======================================================================
# Experiment 3: US threshold × equity weight sweep (bonus)
# ======================================================================

US_EQUITY_LEVELS = [0.20, 0.25, 0.30, 0.35, 0.40, 0.50]


def experiment_us_threshold_equity():
    """Sweep both threshold and equity weight for US."""
    print("\n" + "=" * 80)
    print("  实验 3：美股阈值 × 股票权重交叉扫描")
    print("=" * 80)

    # Find best US equity weight with best threshold from experiment 1
    results = []
    for eq in US_EQUITY_LEVELS:
        for thresh in THRESHOLDS:
            cfg = copy.deepcopy(US_CONFIG)
            remaining = 1.0 - eq
            each = remaining / 3
            cfg["assets"] = [
                {"ticker": "QQQ", "role": "equity", "weight": eq},
                {"ticker": "AGG", "role": "bond", "weight": each},
                {"ticker": "GLD", "role": "gold", "weight": each},
                {"ticker": "SHY", "role": "cash", "weight": each},
            ]
            cfg["params"]["rebalance_threshold"] = thresh

            t0 = time.time()
            m = run_backtest(cfg)
            elapsed = time.time() - t0

            results.append((eq, thresh, m))

    # Print heatmap
    print(f"\n  Sortino 热力图（行=股票权重，列=阈值）")
    print(f"  {'':>8s}", end="")
    for thresh in THRESHOLDS:
        print(f"  {thresh*100:>5.0f}%", end="")
    print()
    print("  " + "-" * (8 + 7 * len(THRESHOLDS)))

    for eq in US_EQUITY_LEVELS:
        print(f"  {eq*100:>6.0f}%", end="")
        for thresh in THRESHOLDS:
            r = [x for x in results if x[0] == eq and x[1] == thresh]
            if r:
                so = r[0][2]["sortino"]
                # Mark best
                is_best = so == max(x[2]["sortino"] for x in results)
                marker = " ★" if is_best else ""
                print(f"  {so:>6.3f}{marker}", end="")
        print()

    # Find global best
    best = max(results, key=lambda x: x[2]["sortino"])
    print(f"\n  ★ 全局最优: 股票 {best[0]*100:.0f}% + 阈值 {best[1]*100:.0f}%")
    print(f"    Sortino={best[2]['sortino']:.3f}, 年化={best[2]['annual_return']:+.2%}, 回撤={best[2]['max_drawdown']:.2%}")

    return results


# ======================================================================
# Main
# ======================================================================

def main():
    clear_cache()

    print("补盲实验：修复报告中的两个实验设计漏洞\n")

    us_results, us_base = experiment_us_threshold()
    cn_results, cn_base = experiment_cn_crisis_equity()
    us_cross = experiment_us_threshold_equity()

    print("\n" + "=" * 80)
    print("  总结")
    print("=" * 80)

    us_best = max(us_results, key=lambda x: x[1]["sortino"])
    print(f"\n  1. 美股阈值: 最优 = {us_best[0]*100:.0f}% (Sortino={us_best[1]['sortino']:.3f})")
    if us_best[0] == 0.07:
        print(f"     → 与 A 股一致，7% 中美通用")
    else:
        print(f"     → 与 A 股不同！报告结论需要修正")

    cn_best = max(cn_results, key=lambda x: x[2]["sortino"])
    print(f"\n  2. A 股危机股票权重: 最优 = {cn_best[0]*100:.0f}% (Sortino={cn_best[2]['sortino']:.3f})")
    if abs(cn_best[0] - 0.05) < 0.001:
        print(f"     → 原报告的 5% 确认最优")
    else:
        cw = cn_best[1]
        print(f"     → 原报告的 5% 并非最优！应为 {cn_best[0]*100:.0f}%")
        print(f"     → 危机权重: {cn_best[0]*100:.0f}/{cw['511010.SS']*100:.0f}/{cw['518880.SS']*100:.0f}/{cw['511990.SS']*100:.0f}")


if __name__ == "__main__":
    main()
