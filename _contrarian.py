"""Contrarian vs Crisis vs No-mode: 别人恐惧我贪婪.

Three philosophies for drawdown management:
  1. Crisis (defensive):   跌了 → 砍股票（趋势跟随，原报告方案）
  2. Contrarian (greedy):  跌了 → 加股票（逆向抄底，巴菲特方案）
  3. No-mode (passive):    不管，纯阈值再平衡

Plus an extension:
  4. Contrarian + profit-take: 跌了加仓，涨多了减仓（完整的别人恐惧我贪婪，别人贪婪我恐惧）

Experiments:
  A. A 股：三种模式对比 + contrarian 参数扫描
  B. 美股：三种模式对比 + contrarian 参数扫描
"""

import sys
import copy
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from btresearch import run_backtest, clear_cache

# ======================================================================
# Helpers
# ======================================================================

def _cn_weights(equity: float, bond: float, gold: float, cash: float) -> dict:
    return {
        "510300.SS": equity,
        "511010.SS": bond,
        "518880.SS": gold,
        "511990.SS": cash,
    }

def _us_weights(equity: float, agg: float, gld: float, shy: float) -> dict:
    return {
        "QQQ": equity,
        "AGG": agg,
        "GLD": gld,
        "SHY": shy,
    }


def _cn_config(
    eq=0.25, bond=0.25, gold=0.25, cash=0.25,
    threshold=0.07,
    stop_loss=None, mode=None,
    crisis_weights=None,
    recovery=None, profit_take=None, pt_weights=None,
):
    """Build A-share config."""
    cfg = {
        "benchmark": "510300.SS",
        "currency": "CNY",
        "cash": 1_000_000,
        "deposits": {"total_capital": 0},
        "assets": [
            {"ticker": "510300.SS", "role": "equity", "weight": eq},
            {"ticker": "511010.SS", "role": "bond", "weight": bond},
            {"ticker": "518880.SS", "role": "gold", "weight": gold},
            {"ticker": "511990.SS", "role": "cash", "weight": cash},
        ],
        "period": {"start": "2014-01-01", "end": "2025-12-31"},
        "params": {
            "rebalance_freq": "never",
            "rebalance_threshold": threshold,
            "stop_loss": stop_loss,
        },
    }
    if mode:
        cfg["params"]["stop_loss_mode"] = mode
    if crisis_weights:
        cfg["params"]["crisis_weights"] = crisis_weights
    if recovery is not None:
        cfg["params"]["recovery_threshold"] = recovery
    if profit_take is not None:
        cfg["params"]["profit_take"] = profit_take
    if pt_weights:
        cfg["params"]["profit_take_weights"] = pt_weights
    return cfg


def _us_config(
    eq=0.40, agg=0.20, gld=0.20, shy=0.20,
    threshold=0.10,
    stop_loss=None, mode=None,
    crisis_weights=None,
    recovery=None, profit_take=None, pt_weights=None,
):
    """Build US config."""
    cfg = {
        "benchmark": "^GSPC",
        "currency": "USD",
        "cash": 1_000_000,
        "deposits": {"total_capital": 0},
        "assets": [
            {"ticker": "QQQ", "role": "equity", "weight": eq},
            {"ticker": "AGG", "role": "bond", "weight": agg},
            {"ticker": "GLD", "role": "gold", "weight": gld},
            {"ticker": "SHY", "role": "cash", "weight": shy},
        ],
        "period": {"start": "2005-01-01", "end": "2025-12-31"},
        "params": {
            "rebalance_freq": "never",
            "rebalance_threshold": threshold,
            "stop_loss": stop_loss,
        },
    }
    if mode:
        cfg["params"]["stop_loss_mode"] = mode
    if crisis_weights:
        cfg["params"]["crisis_weights"] = crisis_weights
    if recovery is not None:
        cfg["params"]["recovery_threshold"] = recovery
    if profit_take is not None:
        cfg["params"]["profit_take"] = profit_take
    if pt_weights:
        cfg["params"]["profit_take_weights"] = pt_weights
    return cfg


def _fmt(m):
    return f"{m['sortino']:.3f}  {m['annual_return']:+.2%}  {m['max_drawdown']:.2%}"


def _run(cfg):
    t0 = time.time()
    m = run_backtest(cfg)
    return m, time.time() - t0


# ======================================================================
# Experiment A: A 股三种模式对比
# ======================================================================

def experiment_cn_three_modes():
    print("=" * 90)
    print("  实验 A：A 股 — 危机模式 vs 逆向模式 vs 无模式")
    print("=" * 90)
    print(f"  {'模式':<20s}  {'Sortino':>8s}  {'年化':>8s}  {'回撤':>8s}  {'时间':>6s}")
    print("-" * 90)

    configs = [
        ("① 无模式（阈值7%）", _cn_config(threshold=0.07)),
        ("② 危机模式（跌→砍仓）", _cn_config(
            threshold=0.07, stop_loss=0.10, mode="crisis",
            crisis_weights=_cn_weights(0.03, 0.39, 0.34, 0.24),
        )),
        ("③ 逆向模式（跌→加仓）", _cn_config(
            threshold=0.07, stop_loss=0.10, mode="contrarian",
            crisis_weights=_cn_weights(0.45, 0.20, 0.20, 0.15),
            recovery=0.05,
        )),
        ("④ 逆向+止盈（完整版）", _cn_config(
            threshold=0.07, stop_loss=0.10, mode="contrarian",
            crisis_weights=_cn_weights(0.45, 0.20, 0.20, 0.15),
            recovery=0.05, profit_take=0.12,
            pt_weights=_cn_weights(0.15, 0.30, 0.30, 0.25),
        )),
    ]

    results = []
    for label, cfg in configs:
        m, elapsed = _run(cfg)
        print(f"  {label:<20s}  {m['sortino']:>8.3f}  {m['annual_return']:>+7.2%}  {m['max_drawdown']:>7.2%}  {elapsed:>5.1f}s")
        results.append((label, cfg, m))

    best = max(results, key=lambda x: x[2]["sortino"])
    print(f"\n  ★ Sortino 最优: {best[0]} ({best[2]['sortino']:.3f})")
    best_ret = max(results, key=lambda x: x[2]["annual_return"])
    print(f"  ★ 年化最优:   {best_ret[0]} ({best_ret[2]['annual_return']:+.2%})")
    return results


# ======================================================================
# Experiment A2: A 股逆向模式参数扫描
# ======================================================================

def experiment_cn_contrarian_sweep():
    print("\n" + "=" * 90)
    print("  实验 A2：A 股逆向模式 — 加仓幅度 × 触发阈值 × 止盈幅度")
    print("=" * 90)

    CONTRARIAN_EQ = [0.35, 0.45, 0.55]
    TRIGGERS = [0.08, 0.10, 0.15]
    RECOVERIES = [0.03, 0.05]
    PT_LEVELS = [None, 0.15, 0.25]

    results = []
    count = 0
    total = len(CONTRARIAN_EQ) * len(TRIGGERS) * len(RECOVERIES) * len(PT_LEVELS)

    for ceq in CONTRARIAN_EQ:
        for trigger in TRIGGERS:
            for recovery in RECOVERIES:
                for pt in PT_LEVELS:
                    count += 1
                    rem = 1.0 - ceq
                    cw = _cn_weights(ceq, rem * 0.40, rem * 0.35, rem * 0.25)

                    ptw = None
                    if pt is not None:
                        # profit take: reduce equity to below base
                        pt_eq = max(0.10, ceq - 0.20)
                        pt_rem = 1.0 - pt_eq
                        ptw = _cn_weights(pt_eq, pt_rem * 0.40, pt_rem * 0.35, pt_rem * 0.25)

                    cfg = _cn_config(
                        threshold=0.07,
                        stop_loss=trigger, mode="contrarian",
                        crisis_weights=cw,
                        recovery=recovery,
                        profit_take=pt, pt_weights=ptw,
                    )
                    m, _ = _run(cfg)

                    pt_str = f"{pt*100:.0f}%" if pt else "无"
                    tag = f"加仓{ceq*100:.0f}% | 触发{trigger*100:.0f}% | 恢复{recovery*100:.0f}% | 止盈{pt_str}"
                    results.append((ceq, trigger, recovery, pt, tag, m))

                    sys.stdout.write(f"\r  [{count}/{total}] {tag:<55s}")
                    sys.stdout.flush()

    # Sortino ranking
    results.sort(key=lambda x: x[5]["sortino"], reverse=True)

    print(f"\n\n  Top 10（按 Sortino 排序）:")
    print(f"  {'#':>3s}  {'配置':<55s}  {'Sortino':>8s}  {'年化':>8s}  {'回撤':>8s}")
    print("  " + "-" * 90)
    for i, (ceq, trigger, recovery, pt, tag, m) in enumerate(results[:10], 1):
        print(f"  {i:>3d}  {tag:<55s}  {m['sortino']:>8.3f}  {m['annual_return']:>+7.2%}  {m['max_drawdown']:>7.2%}")

    # Also show best by annual return
    ret_sorted = sorted(results, key=lambda x: x[5]["annual_return"], reverse=True)
    print(f"\n  Top 5（按年化排序）:")
    print(f"  {'#':>3s}  {'配置':<55s}  {'Sortino':>8s}  {'年化':>8s}  {'回撤':>8s}")
    print("  " + "-" * 90)
    for i, (ceq, trigger, recovery, pt, tag, m) in enumerate(ret_sorted[:5], 1):
        print(f"  {i:>3d}  {tag:<55s}  {m['sortino']:>8.3f}  {m['annual_return']:>+7.2%}  {m['max_drawdown']:>7.2%}")

    # Compare with crisis mode
    print(f"\n  对照：危机模式最优")
    m_crisis, _ = _run(_cn_config(
        threshold=0.07, stop_loss=0.10, mode="crisis",
        crisis_weights=_cn_weights(0.03, 0.39, 0.34, 0.24),
    ))
    print(f"  {'危机模式（3/39/34/24）':<55s}  {m_crisis['sortino']:>8.3f}  {m_crisis['annual_return']:>+7.2%}  {m_crisis['max_drawdown']:>7.2%}")

    best = results[0]
    print(f"\n  ★ 逆向模式最优: {best[4]}")
    print(f"    Sortino={best[5]['sortino']:.3f} vs 危机模式 {m_crisis['sortino']:.3f}")
    if best[5]["sortino"] > m_crisis["sortino"]:
        print(f"    ✅ 逆向模式胜出（Sortino +{best[5]['sortino'] - m_crisis['sortino']:.3f}）")
    else:
        print(f"    ❌ 危机模式仍然更优（Sortino +{m_crisis['sortino'] - best[5]['sortino']:.3f}）")

    return results, m_crisis


# ======================================================================
# Experiment B: 美股三种模式对比
# ======================================================================

def experiment_us_three_modes():
    print("\n" + "=" * 90)
    print("  实验 B：美股 — 危机模式 vs 逆向模式 vs 无模式")
    print("=" * 90)
    print(f"  {'模式':<20s}  {'Sortino':>8s}  {'年化':>8s}  {'回撤':>8s}  {'时间':>6s}")
    print("-" * 90)

    configs = [
        ("① 无模式（阈值10%）", _us_config(threshold=0.10)),
        ("② 危机模式（跌→砍仓）", _us_config(
            threshold=0.10, stop_loss=0.15, mode="crisis",
            crisis_weights=_us_weights(0.15, 0.30, 0.30, 0.25),
        )),
        ("③ 逆向模式（跌→加仓）", _us_config(
            threshold=0.10, stop_loss=0.15, mode="contrarian",
            crisis_weights=_us_weights(0.60, 0.15, 0.15, 0.10),
            recovery=0.05,
        )),
        ("④ 逆向+止盈（完整版）", _us_config(
            threshold=0.10, stop_loss=0.15, mode="contrarian",
            crisis_weights=_us_weights(0.60, 0.15, 0.15, 0.10),
            recovery=0.05, profit_take=0.15,
            pt_weights=_us_weights(0.25, 0.27, 0.24, 0.24),
        )),
    ]

    results = []
    for label, cfg in configs:
        m, elapsed = _run(cfg)
        print(f"  {label:<20s}  {m['sortino']:>8.3f}  {m['annual_return']:>+7.2%}  {m['max_drawdown']:>7.2%}  {elapsed:>5.1f}s")
        results.append((label, cfg, m))

    best = max(results, key=lambda x: x[2]["sortino"])
    print(f"\n  ★ Sortino 最优: {best[0]} ({best[2]['sortino']:.3f})")
    best_ret = max(results, key=lambda x: x[2]["annual_return"])
    print(f"  ★ 年化最优:   {best_ret[0]} ({best_ret[2]['annual_return']:+.2%})")
    return results


# ======================================================================
# Experiment B2: 美股逆向模式参数扫描
# ======================================================================

def experiment_us_contrarian_sweep():
    print("\n" + "=" * 90)
    print("  实验 B2：美股逆向模式 — 加仓幅度 × 触发阈值 × 止盈幅度")
    print("=" * 90)

    CONTRARIAN_EQ = [0.50, 0.60, 0.70]
    TRIGGERS = [0.10, 0.15, 0.20]
    RECOVERIES = [0.05, 0.08]
    PT_LEVELS = [None, 0.10, 0.15, 0.25]

    results = []
    count = 0
    total = len(CONTRARIAN_EQ) * len(TRIGGERS) * len(RECOVERIES) * len(PT_LEVELS)

    for ceq in CONTRARIAN_EQ:
        for trigger in TRIGGERS:
            for recovery in RECOVERIES:
                for pt in PT_LEVELS:
                    count += 1
                    rem = 1.0 - ceq
                    each = rem / 3
                    cw = _us_weights(ceq, each, each, each)

                    ptw = None
                    if pt is not None:
                        pt_eq = max(0.25, ceq - 0.20)
                        pt_rem = 1.0 - pt_eq
                        pt_each = pt_rem / 3
                        ptw = _us_weights(pt_eq, pt_each, pt_each, pt_each)

                    cfg = _us_config(
                        threshold=0.10,
                        stop_loss=trigger, mode="contrarian",
                        crisis_weights=cw,
                        recovery=recovery,
                        profit_take=pt, pt_weights=ptw,
                    )
                    m, _ = _run(cfg)

                    pt_str = f"{pt*100:.0f}%" if pt else "无"
                    tag = f"加仓{ceq*100:.0f}% | 触发{trigger*100:.0f}% | 恢复{recovery*100:.0f}% | 止盈{pt_str}"
                    results.append((ceq, trigger, recovery, pt, tag, m))

                    sys.stdout.write(f"\r  [{count}/{total}] {tag:<55s}")
                    sys.stdout.flush()

    results.sort(key=lambda x: x[5]["sortino"], reverse=True)

    print(f"\n\n  Top 10（按 Sortino 排序）:")
    print(f"  {'#':>3s}  {'配置':<55s}  {'Sortino':>8s}  {'年化':>8s}  {'回撤':>8s}")
    print("  " + "-" * 90)
    for i, (ceq, trigger, recovery, pt, tag, m) in enumerate(results[:10], 1):
        print(f"  {i:>3d}  {tag:<55s}  {m['sortino']:>8.3f}  {m['annual_return']:>+7.2%}  {m['max_drawdown']:>7.2%}")

    ret_sorted = sorted(results, key=lambda x: x[5]["annual_return"], reverse=True)
    print(f"\n  Top 5（按年化排序）:")
    print(f"  {'#':>3s}  {'配置':<55s}  {'Sortino':>8s}  {'年化':>8s}  {'回撤':>8s}")
    print("  " + "-" * 90)
    for i, (ceq, trigger, recovery, pt, tag, m) in enumerate(ret_sorted[:5], 1):
        print(f"  {i:>3d}  {tag:<55s}  {m['sortino']:>8.3f}  {m['annual_return']:>+7.2%}  {m['max_drawdown']:>7.2%}")

    # Compare with no-mode baseline
    m_base, _ = _run(_us_config(threshold=0.10))
    print(f"\n  对照：无模式（40% QQQ + 阈值10%）")
    print(f"  {'无模式':<55s}  {m_base['sortino']:>8.3f}  {m_base['annual_return']:>+7.2%}  {m_base['max_drawdown']:>7.2%}")

    best = results[0]
    print(f"\n  ★ 逆向模式最优: {best[4]}")
    print(f"    Sortino={best[5]['sortino']:.3f} vs 无模式 {m_base['sortino']:.3f}")
    if best[5]["sortino"] > m_base["sortino"]:
        print(f"    ✅ 逆向模式胜出（Sortino +{best[5]['sortino'] - m_base['sortino']:.3f}）")
    else:
        print(f"    ❌ 无模式仍然更优")

    return results, m_base


# ======================================================================
# Experiment C: 对比表 — 所有模式在所有窗口
# ======================================================================

def experiment_cn_windows():
    """Run best contrarian vs best crisis vs no-mode across A-share windows."""
    print("\n" + "=" * 90)
    print("  实验 C：A 股滚动窗口 — 三种模式稳定性对比")
    print("=" * 90)

    windows = [
        ("2014-2025", "2014-01-01", "2025-12-31"),
        ("2015-2024", "2015-01-01", "2024-12-31"),
        ("2016-2025", "2016-01-01", "2025-12-31"),
    ]

    modes = [
        ("无模式", lambda p: _cn_config(threshold=0.07)),
        ("危机(砍仓)", lambda p: _cn_config(
            threshold=0.07, stop_loss=0.10, mode="crisis",
            crisis_weights=_cn_weights(0.03, 0.39, 0.34, 0.24),
        )),
        ("逆向(加仓)", lambda p: _cn_config(
            threshold=0.07, stop_loss=0.10, mode="contrarian",
            crisis_weights=_cn_weights(0.45, 0.20, 0.20, 0.15),
            recovery=0.05,
        )),
        ("逆向+止盈", lambda p: _cn_config(
            threshold=0.07, stop_loss=0.10, mode="contrarian",
            crisis_weights=_cn_weights(0.45, 0.20, 0.20, 0.15),
            recovery=0.05, profit_take=0.12,
            pt_weights=_cn_weights(0.15, 0.30, 0.30, 0.25),
        )),
    ]

    print(f"\n  {'模式':<12s}", end="")
    for w_label, _, _ in windows:
        print(f"  | {w_label:>8s} Sortino   年化     回撤", end="")
    print()
    print("  " + "-" * (12 + 8 + 38 * len(windows)))

    for mode_name, mode_fn in modes:
        print(f"  {mode_name:<12s}", end="")
        for w_label, w_start, w_end in windows:
            cfg = mode_fn(None)
            cfg["period"] = {"start": w_start, "end": w_end}
            m, _ = _run(cfg)
            print(f"  | {m['sortino']:>7.3f}  {m['annual_return']:>+6.2%}  {m['max_drawdown']:>6.2%}", end="")
        print()


def experiment_us_windows():
    """Run best contrarian vs no-mode across US windows."""
    print("\n" + "=" * 90)
    print("  实验 D：美股滚动窗口 — 三种模式稳定性对比")
    print("=" * 90)

    windows = [
        ("2005-2014", "2005-01-01", "2014-12-31"),
        ("2007-2016", "2007-01-01", "2016-12-31"),
        ("2009-2018", "2009-01-01", "2018-12-31"),
        ("2011-2020", "2011-01-01", "2020-12-31"),
        ("2013-2022", "2013-01-01", "2022-12-31"),
        ("2015-2024", "2015-01-01", "2024-12-31"),
    ]

    modes = [
        ("无模式", lambda p: _us_config(threshold=0.10)),
        ("逆向(加仓)", lambda p: _us_config(
            threshold=0.10, stop_loss=0.15, mode="contrarian",
            crisis_weights=_us_weights(0.60, 0.15, 0.15, 0.10),
            recovery=0.05,
        )),
        ("逆向+止盈", lambda p: _us_config(
            threshold=0.10, stop_loss=0.15, mode="contrarian",
            crisis_weights=_us_weights(0.60, 0.15, 0.15, 0.10),
            recovery=0.05, profit_take=0.15,
            pt_weights=_us_weights(0.25, 0.27, 0.24, 0.24),
        )),
    ]

    print(f"\n  {'模式':<12s}", end="")
    for w_label, _, _ in windows:
        print(f"  | {w_label:>8s} Sortino   回撤", end="")
    print()
    print("  " + "-" * (12 + 8 + 28 * len(windows)))

    for mode_name, mode_fn in modes:
        print(f"  {mode_name:<12s}", end="")
        for w_label, w_start, w_end in windows:
            cfg = mode_fn(None)
            cfg["period"] = {"start": w_start, "end": w_end}
            m, _ = _run(cfg)
            print(f"  | {m['sortino']:>7.3f}  {m['max_drawdown']:>6.2%}", end="")
        print()


# ======================================================================
# Main
# ======================================================================

def main():
    clear_cache()

    print("别人恐惧我贪婪 — 逆向模式实验\n")

    cn_modes = experiment_cn_three_modes()
    cn_sweep, cn_crisis = experiment_cn_contrarian_sweep()
    experiment_cn_windows()

    us_modes = experiment_us_three_modes()
    us_sweep, us_base = experiment_us_contrarian_sweep()
    experiment_us_windows()

    # ==================================================================
    # Final summary
    # ==================================================================
    print("\n\n" + "=" * 90)
    print("  最终对比：危机模式 vs 逆向模式")
    print("=" * 90)

    print(f"\n  A 股（2014-2025）:")
    print(f"  {'模式':<20s}  {'Sortino':>8s}  {'年化':>8s}  {'回撤':>8s}")
    print("  " + "-" * 50)
    for label, cfg, m in cn_modes:
        print(f"  {label:<20s}  {m['sortino']:>8.3f}  {m['annual_return']:>+7.2%}  {m['max_drawdown']:>7.2%}")

    print(f"\n  美股（2005-2025）:")
    print(f"  {'模式':<20s}  {'Sortino':>8s}  {'年化':>8s}  {'回撤':>8s}")
    print("  " + "-" * 50)
    for label, cfg, m in us_modes:
        print(f"  {label:<20s}  {m['sortino']:>8.3f}  {m['annual_return']:>+7.2%}  {m['max_drawdown']:>7.2%}")

    # Verdict
    cn_best = max(cn_modes, key=lambda x: x[2]["sortino"])
    us_best = max(us_modes, key=lambda x: x[2]["sortino"])

    print(f"\n  A 股最优: {cn_best[0]} (Sortino={cn_best[2]['sortino']:.3f})")
    print(f"  美股最优: {us_best[0]} (Sortino={us_best[2]['sortino']:.3f})")

    cn_is_contrarian = "逆向" in cn_best[0]
    us_is_contrarian = "逆向" in us_best[0]

    if cn_is_contrarian:
        print(f"\n  📈 A 股：别人恐惧我贪婪 — 逆向模式胜出！")
    else:
        print(f"\n  📉 A 股：恐惧时还是得跑 — 危机/无模式更优")

    if us_is_contrarian:
        print(f"  📈 美股：别人恐惧我贪婪 — 逆向模式胜出！")
    else:
        print(f"  📉 美股：恐惧时还是得跑 — 危机/无模式更优")


if __name__ == "__main__":
    main()
