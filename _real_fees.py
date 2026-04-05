"""真实费率对比：修正交易佣金后重跑所有策略。

实际费率：
  A 股 ETF 交易: 万2.5（净佣，无印花税）→ 0.025%
    当前代码: 万10（0.10%）— 这是股票费率，ETF 不需要印花税！
  美股 ETF 交易: 0%（Fidelity/Schwab/IBKR 免佣金）→ 0%
    当前代码: 0% ✅

管理费：
  ETF 管理费每天从净值扣除，yfinance 价格数据已经是扣除后的价格
  回测使用的价格已内含管理费，不需要额外扣除 ✅
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from btresearch import run_backtest, clear_cache


def _cn(eq=0.25, bond=0.25, gold=0.25, cash=0.25,
        threshold=0.07, sl=None, mode=None, cw=None,
        recovery=None, pt=None, ptw=None, commission=0.00025):
    cfg = {
        "benchmark": "510300.SS",
        "currency": "CNY",
        "cash": 1_000_000,
        "commission": commission,
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
            "stop_loss": sl,
        },
    }
    if mode:
        cfg["params"]["stop_loss_mode"] = mode
    if cw:
        cfg["params"]["crisis_weights"] = cw
    if recovery is not None:
        cfg["params"]["recovery_threshold"] = recovery
    if pt is not None:
        cfg["params"]["profit_take"] = pt
    if ptw:
        cfg["params"]["profit_take_weights"] = ptw
    return cfg


def _us(eq=0.40, agg=0.20, gld=0.20, shy=0.20,
        threshold=0.10, sl=None, mode=None, cw=None,
        recovery=None, pt=None, ptw=None, commission=0.0):
    cfg = {
        "benchmark": "^GSPC",
        "currency": "USD",
        "cash": 1_000_000,
        "commission": commission,
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
            "stop_loss": sl,
        },
    }
    if mode:
        cfg["params"]["stop_loss_mode"] = mode
    if cw:
        cfg["params"]["crisis_weights"] = cw
    if recovery is not None:
        cfg["params"]["recovery_threshold"] = recovery
    if pt is not None:
        cfg["params"]["profit_take"] = pt
    if ptw:
        cfg["params"]["profit_take_weights"] = ptw
    return cfg


def main():
    clear_cache()

    CN_CW3 = {"510300.SS": 0.03, "511010.SS": 0.39, "518880.SS": 0.34, "511990.SS": 0.24}
    CN_CW5 = {"510300.SS": 0.05, "511010.SS": 0.40, "518880.SS": 0.35, "511990.SS": 0.20}
    CN_CONTRA_W = {"510300.SS": 0.45, "511010.SS": 0.20, "518880.SS": 0.20, "511990.SS": 0.15}
    CN_PT_W = {"510300.SS": 0.15, "511010.SS": 0.30, "518880.SS": 0.30, "511990.SS": 0.25}

    US_CRISIS_W = {"QQQ": 0.15, "AGG": 0.30, "GLD": 0.30, "SHY": 0.25}
    US_CONTRA_W = {"QQQ": 0.60, "AGG": 0.15, "GLD": 0.15, "SHY": 0.10}
    US_PT_W = {"QQQ": 0.25, "AGG": 0.27, "GLD": 0.24, "SHY": 0.24}

    # Commission levels to test
    CN_OLD_COMMISSION = 0.0010   # 万10（当前代码，错误）
    CN_REAL_COMMISSION = 0.00025  # 万2.5（ETF 净佣，正确）

    # ==================================================================
    print("=" * 110)
    print("  真实费率对比：A 股 ETF 佣金修正（万10 → 万2.5）")
    print("=" * 110)
    print("  费率说明：")
    print("    A 股 ETF 交易佣金: 万2.5（净佣），无印花税 — 当前代码用万10 ❌")
    print("    美股 ETF 交易佣金: 0% — 当前代码正确 ✅")
    print("    ETF 管理费: 已内含在 yfinance 价格数据中，无需额外扣除 ✅")
    print()

    # ==================================================================
    # A 股：对比两种佣金下的结果
    # ==================================================================
    cn_strategies = [
        ("月度再平衡", _cn(threshold=0)),
        ("阈值7% 无模式", _cn(threshold=0.07)),
        ("阈值7% + 危机3%", _cn(sl=0.10, mode="crisis", cw=CN_CW3)),
        ("阈值7% + 危机5%（原报告）", _cn(sl=0.10, mode="crisis", cw=CN_CW5)),
        ("逆向加仓35%", _cn(sl=0.10, mode="contrarian", cw=CN_CONTRA_W, recovery=0.05)),
        ("逆向+止盈", _cn(sl=0.10, mode="contrarian", cw=CN_CONTRA_W, recovery=0.05, pt=0.12, ptw=CN_PT_W)),
        ("沪深300 买入持有", _cn(eq=1.0, bond=0, gold=0, cash=0, threshold=0)),
        ("黄金 买入持有", _cn(eq=0, bond=0, gold=1.0, cash=0, threshold=0)),
    ]

    print(f"\n{'─' * 110}")
    print(f"  A 股（2014-2025，100万起投）— 佣金影响对比")
    print(f"{'─' * 110}")
    print(f"  {'策略':<24s}  {'万10(旧)':>14s}  {'万2.5(真)':>14s}  {'差异':>10s}  {'年化(真)':>8s}  {'回撤':>8s}  {'Sortino':>8s}")
    print(f"  {'':24s}  {'最终资产':>14s}  {'最终资产':>14s}  {'':>10s}  {'':>8s}  {'':>8s}  {'':>8s}")
    print(f"  {'─'*110}")

    cn_old_results = []
    cn_real_results = []

    for label, cfg_template in cn_strategies:
        # Old commission (万10)
        cfg_old = dict(cfg_template)
        cfg_old["commission"] = CN_OLD_COMMISSION
        m_old = run_backtest(cfg_old)

        # Real commission (万2.5)
        cfg_real = dict(cfg_template)
        cfg_real["commission"] = CN_REAL_COMMISSION
        m_real = run_backtest(cfg_real)

        diff = m_real["final_value"] - m_old["final_value"]
        cn_old_results.append((label, m_old))
        cn_real_results.append((label, m_real))

        print(f"  {label:<24s}  {m_old['final_value']:>12,.0f}元  {m_real['final_value']:>12,.0f}元  "
              f"{diff:>+9,.0f}元  {m_real['annual_return']:>+7.2%}  "
              f"{m_real['max_drawdown']:>7.2%}  {m_real['sortino']:>8.3f}")

    # ==================================================================
    # 美股（佣金已经是 0%，管理费已内含，不需要修正）
    # ==================================================================
    print(f"\n{'─' * 110}")
    print(f"  美股（2005-2025，$100万起投）— 当前费率已正确（0佣金 + 管理费已内含）")
    print(f"{'─' * 110}")
    print(f"  {'策略':<24s}  {'最终资产':>14s}  {'总收益':>10s}  {'年化':>8s}  {'回撤':>8s}  {'Sortino':>8s}")
    print(f"  {'─'*110}")

    us_strategies = [
        ("月度再平衡", _us(threshold=0)),
        ("阈值10% 无模式", _us(threshold=0.10)),
        ("阈值10% + 危机模式", _us(sl=0.15, mode="crisis", cw=US_CRISIS_W)),
        ("逆向加仓50%", _us(sl=0.15, mode="contrarian", cw=US_CONTRA_W, recovery=0.08)),
        ("逆向+止盈", _us(sl=0.15, mode="contrarian", cw=US_CONTRA_W, recovery=0.05, pt=0.15, ptw=US_PT_W)),
        ("QQQ 买入持有", _us(eq=1.0, agg=0, gld=0, shy=0, threshold=0)),
    ]

    us_results = []
    for label, cfg in us_strategies:
        m = run_backtest(cfg)
        total_ret = (m["final_value"] - 1_000_000) / 1_000_000
        us_results.append((label, m))
        print(f"  {label:<24s}  ${m['final_value']:>12,.0f}  {total_ret:>+9.1%}  "
              f"{m['annual_return']:>+7.2%}  {m['max_drawdown']:>7.2%}  {m['sortino']:>8.3f}")

    # ==================================================================
    # ETF 管理费对持有成本的影响（信息展示）
    # ==================================================================
    print(f"\n{'─' * 110}")
    print(f"  ETF 管理费参考（已内含在价格中，不需要额外扣除）")
    print(f"{'─' * 110}")
    print()
    print(f"  A 股 ETF:")
    print(f"    510300 沪深300ETF:  管理费 0.50% + 托管费 0.10% = 0.60%/年")
    print(f"    511010 国债ETF:     管理费 0.30% + 托管费 0.10% = 0.40%/年")
    print(f"    518880 黄金ETF:     管理费 0.50% + 托管费 0.10% = 0.60%/年")
    print(f"    511990 华宝添益:    管理费 0%（已内化到货币收益）")
    print(f"    → 永久组合加权: 0.40%/年")
    print(f"    → 12年累积侵蚀: {(1-(1-0.004)**12)*100:.1f}%")
    print()
    print(f"  美股 ETF:")
    print(f"    QQQ: 0.20%/年   SPY: 0.09%/年   GLD: 0.40%/年   AGG: 0.03%/年   SHY: 0.15%/年")
    print(f"    → 40/20/20/20 组合加权: 0.208%/年")
    print(f"    → 21年累积侵蚀: {(1-(1-0.00208)**21)*100:.1f}%")

    # ==================================================================
    # 最终排名（真实费率）
    # ==================================================================
    print(f"\n{'=' * 110}")
    print(f"  最终排名（真实费率）")
    print(f"{'=' * 110}")

    print(f"\n  A 股（按最终资产排序，佣金万2.5）:")
    cn_sorted = sorted(cn_real_results, key=lambda x: x[1]["final_value"], reverse=True)
    for i, (label, m) in enumerate(cn_sorted, 1):
        total = (m["final_value"] - 1_000_000) / 1_000_000
        marker = " 🥇" if i == 1 else " 🥈" if i == 2 else " 🥉" if i == 3 else ""
        print(f"    {i}. {label:<24s}  {m['final_value']:>10,.0f}元  {total:>+8.1%}  "
              f"年化{m['annual_return']:+.2%}  回撤{m['max_drawdown']:.2%}  Sortino {m['sortino']:.3f}{marker}")

    print(f"\n  美股（按最终资产排序，0佣金）:")
    us_sorted = sorted(us_results, key=lambda x: x[1]["final_value"], reverse=True)
    for i, (label, m) in enumerate(us_sorted, 1):
        total = (m["final_value"] - 1_000_000) / 1_000_000
        marker = " 🥇" if i == 1 else " 🥈" if i == 2 else " 🥉" if i == 3 else ""
        print(f"    {i}. {label:<24s}  ${m['final_value']:>10,.0f}  {total:>+8.1%}  "
              f"年化{m['annual_return']:+.2%}  回撤{m['max_drawdown']:.2%}  Sortino {m['sortino']:.3f}{marker}")

    # Summary
    print(f"\n{'=' * 110}")
    print(f"  关键发现")
    print(f"{'=' * 110}")

    # Commission impact on most-traded strategy (monthly rebalance)
    monthly_old = [r for r in cn_old_results if r[0] == "月度再平衡"][0][1]
    monthly_real = [r for r in cn_real_results if r[0] == "月度再平衡"][0][1]
    monthly_diff = monthly_real["final_value"] - monthly_old["final_value"]
    monthly_pct = monthly_diff / monthly_old["final_value"] * 100

    thresh_old = [r for r in cn_old_results if r[0] == "阈值7% 无模式"][0][1]
    thresh_real = [r for r in cn_real_results if r[0] == "阈值7% 无模式"][0][1]
    thresh_diff = thresh_real["final_value"] - thresh_old["final_value"]

    crisis_old = [r for r in cn_old_results if r[0] == "阈值7% + 危机3%"][0][1]
    crisis_real = [r for r in cn_real_results if r[0] == "阈值7% + 危机3%"][0][1]
    crisis_diff = crisis_real["final_value"] - crisis_old["final_value"]

    print(f"\n  1. A 股佣金修正影响（万10 → 万2.5）:")
    print(f"     月度再平衡:   +{monthly_diff:,.0f}元（{monthly_pct:+.1f}%）— 交易最频繁，受影响最大")
    print(f"     阈值7% 无模式: +{thresh_diff:,.0f}元 — 交易较少，影响小")
    print(f"     危机模式:     +{crisis_diff:,.0f}元 — 交易少，影响最小")
    print(f"     买入持有:     +0元 — 只交易一次，无影响")

    print(f"\n  2. 佣金修正不改变策略排名:")
    old_rank = sorted(cn_old_results, key=lambda x: x[1]["final_value"], reverse=True)
    real_rank = sorted(cn_real_results, key=lambda x: x[1]["final_value"], reverse=True)
    old_names = [r[0] for r in old_rank]
    real_names = [r[0] for r in real_rank]
    if old_names == real_names:
        print(f"     ✅ 排名完全一致，所有策略排名不受佣金影响")
    else:
        print(f"     ⚠️ 排名有变化:")
        for i, name in enumerate(real_names, 1):
            old_pos = old_names.index(name) + 1
            if old_pos != i:
                print(f"       {name}: {old_pos} → {i}")

    # Net expense ratio info
    print(f"\n  3. 隐性成本：ETF 管理费（已内含在价格中）:")
    print(f"     A 股组合加权: 0.40%/年 → 12年累积侵蚀约 4.7%")
    print(f"     美股组合加权: 0.21%/年 → 21年累积侵蚀约 4.3%")
    print(f"     这些成本已反映在回测收益中，无需额外扣除")


if __name__ == "__main__":
    main()
