"""Full 4-dimension sweep: strategy × invest_method × rebalance_freq × window.

Dimensions:
  1. Strategy:     永久组合 (4 assets 25% each) vs 股债30/70
  2. Invest method: 一次性投入 (lump sum) vs 定投 (DCA)
  3. Rebalance:    monthly / quarterly / yearly
  4. Window:       2014-2023, 2015-2024, 2016-2025, 2014-2025(full)

Total: 2 × 2 × 3 × 4 = 48 combinations.

Metric: total_return (总资产收益率) = (final_value - total_deposited) / total_deposited
"""

import sys
import copy
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from engine import (
    run_backtest,
    get_benchmark,
    get_commission,
    max_drawdown,
)

# ======================================================================
# Dimension definitions
# ======================================================================

STRATEGIES = {
    "永久组合": {
        "assets": [
            {"ticker": "510300.SS", "role": "equity", "weight": 0.25},
            {"ticker": "511010.SS", "role": "bond", "weight": 0.25},
            {"ticker": "518880.SS", "role": "gold", "weight": 0.25},
            {"ticker": "511990.SS", "role": "cash", "weight": 0.25},
        ],
    },
    "股债30/70": {
        "assets": [
            {"ticker": "510300.SS", "role": "equity", "weight": 0.3},
            {"ticker": "511010.SS", "role": "bond", "weight": 0.7},
        ],
    },
}

INVEST_METHODS = {
    "一次性": {
        "cash": 1000000,
        "deposits": {"total_capital": 0},
    },
    "定投": {
        "deposits": {
            "total_capital": 1000000,
            "initial": 0,
            "freq": "monthly",
            "day": 1,
            "day_mode": "first",
        },
    },
}

REBAL_FREQS = ["monthly", "quarterly", "yearly"]
REBAL_LABELS = {"monthly": "月度", "quarterly": "季度", "yearly": "年度"}

WINDOWS = [
    ("2014-2023", "2014-01-01", "2023-12-31"),
    ("2015-2024", "2015-01-01", "2024-12-31"),
    ("2016-2025", "2016-01-01", "2025-12-31"),
    ("2014-2025", "2014-01-01", "2025-12-31"),
]

BASE_CONFIG = {
    "benchmark": "510300.SS",
    "currency": "CNY",
}


# ======================================================================
# Build & run all 48 combinations
# ======================================================================

def main():
    total = (
        len(STRATEGIES)
        * len(INVEST_METHODS)
        * len(REBAL_FREQS)
        * len(WINDOWS)
    )
    print(f"=== 全维度遍历 ===")
    print(f"  策略:       {len(STRATEGIES)} ({', '.join(STRATEGIES)})")
    print(f"  投入方式:   {len(INVEST_METHODS)} ({', '.join(INVEST_METHODS)})")
    print(f"  再平衡频率: {len(REBAL_FREQS)} ({', '.join(REBAL_FREQS)})")
    print(f"  时间窗口:   {len(WINDOWS)} ({', '.join(w[0] for w in WINDOWS)})")
    print(f"  总组合数:   {total}")
    print()

    results = []
    t0 = time.time()
    count = 0

    for strat_name, strat_cfg in STRATEGIES.items():
        for method_name, method_cfg in INVEST_METHODS.items():
            for freq in REBAL_FREQS:
                for win_label, win_start, win_end in WINDOWS:
                    count += 1

                    # Build config
                    cfg = copy.deepcopy(BASE_CONFIG)
                    cfg["assets"] = copy.deepcopy(strat_cfg["assets"])
                    cfg["period"] = {"start": win_start, "end": win_end}
                    cfg["params"] = {"rebalance_freq": freq, "stop_loss": None}

                    if "cash" in method_cfg:
                        cfg["cash"] = method_cfg["cash"]
                    cfg["deposits"] = copy.deepcopy(method_cfg["deposits"])

                    tag = f"{strat_name}|{method_name}|{REBAL_LABELS[freq]}|{win_label}"
                    sys.stdout.write(f"\r[{count}/{total}] {tag:<40s}")
                    sys.stdout.flush()

                    try:
                        m = run_backtest(cfg, cfg)
                        # Fix total_return for lump sum
                        total_dep = m["total_deposited"]
                        if total_dep > 0:
                            total_ret = m["total_return"]
                        else:
                            initial_cash = method_cfg.get("cash", 1000000)
                            total_ret = (
                                (m["final_value"] - initial_cash) / initial_cash
                            )
                        results.append(
                            {
                                "tag": tag,
                                "策略": strat_name,
                                "投入方式": method_name,
                                "再平衡": REBAL_LABELS[freq],
                                "窗口": win_label,
                                "total_return": total_ret,
                                "capital_return_annualized": m.get(
                                    "capital_return_annualized", m["annual_return"]
                                ),
                                "annual_return": m["annual_return"],
                                "max_drawdown": m["max_drawdown"],
                                "sortino": m["sortino"],
                                "final_value": m["final_value"],
                                "total_deposited": total_dep,
                                "beat_benchmark": m.get("beat_benchmark"),
                                "benchmark_return": m.get("benchmark_return"),
                            }
                        )
                    except Exception as e:
                        print(f"\n  [ERROR] {tag}: {e}")

    elapsed = time.time() - t0
    print(f"\n\n[done] {len(results)}/{total} in {elapsed:.1f}s")

    # ==================================================================
    # Results: sorted by total_return (总资产收益率)
    # ==================================================================

    results.sort(key=lambda r: r["total_return"], reverse=True)

    print("\n" + "=" * 100)
    print("  全部 48 组合 — 按 总资产收益率 排序（从高到低）")
    print("=" * 100)
    print(
        f"{'排名':>4s}  {'策略':<8s}  {'投入':<5s}  {'再平衡':<4s}  {'窗口':<9s}  "
        f"{'总收益率':>8s}  {'年化回报':>8s}  {'最大回撤':>8s}  {'Sortino':>7s}  {'跑赢基准':>6s}"
    )
    print("-" * 100)

    for i, r in enumerate(results, 1):
        tr = r["total_return"] * 100
        cr = r["capital_return_annualized"] * 100
        dd = r["max_drawdown"] * 100
        so = r["sortino"]
        beat = "✅" if r["beat_benchmark"] else "❌"
        print(
            f"{i:>4d}  {r['策略']:<8s}  {r['投入方式']:<5s}  {r['再平衡']:<4s}  "
            f"{r['窗口']:<9s}  {tr:>+7.2f}%  {cr:>+7.2f}%  {dd:>7.1f}%  "
            f"{so:>7.2f}  {beat:>4s}"
        )

    # ==================================================================
    # Summary: best / worst by dimension
    # ==================================================================

    print("\n\n" + "=" * 100)
    print("  分维度汇总")
    print("=" * 100)

    # By strategy
    print("\n--- 按策略汇总 ---")
    for s in STRATEGIES:
        sub = [r for r in results if r["策略"] == s]
        avg_tr = sum(r["total_return"] for r in sub) / len(sub)
        avg_dd = sum(r["max_drawdown"] for r in sub) / len(sub)
        avg_so = sum(r["sortino"] for r in sub) / len(sub)
        wins = sum(1 for r in sub if r["beat_benchmark"])
        print(
            f"  {s:<10s}  平均总收益率={avg_tr*100:>+6.2f}%  平均回撤={avg_dd*100:>5.1f}%  "
            f"平均Sortino={avg_so:>6.2f}  跑赢次数={wins}/{len(sub)}"
        )

    # By invest method
    print("\n--- 按投入方式汇总 ---")
    for m_name in INVEST_METHODS:
        sub = [r for r in results if r["投入方式"] == m_name]
        avg_tr = sum(r["total_return"] for r in sub) / len(sub)
        avg_dd = sum(r["max_drawdown"] for r in sub) / len(sub)
        avg_so = sum(r["sortino"] for r in sub) / len(sub)
        wins = sum(1 for r in sub if r["beat_benchmark"])
        print(
            f"  {m_name:<10s}  平均总收益率={avg_tr*100:>+6.2f}%  平均回撤={avg_dd*100:>5.1f}%  "
            f"平均Sortino={avg_so:>6.2f}  跑赢次数={wins}/{len(sub)}"
        )

    # By rebalance freq
    print("\n--- 按再平衡频率汇总 ---")
    for freq in REBAL_FREQS:
        label = REBAL_LABELS[freq]
        sub = [r for r in results if r["再平衡"] == label]
        avg_tr = sum(r["total_return"] for r in sub) / len(sub)
        avg_dd = sum(r["max_drawdown"] for r in sub) / len(sub)
        avg_so = sum(r["sortino"] for r in sub) / len(sub)
        wins = sum(1 for r in sub if r["beat_benchmark"])
        print(
            f"  {label:<10s}  平均总收益率={avg_tr*100:>+6.2f}%  平均回撤={avg_dd*100:>5.1f}%  "
            f"平均Sortino={avg_so:>6.2f}  跑赢次数={wins}/{len(sub)}"
        )

    # By window
    print("\n--- 按时间窗口汇总 ---")
    for w_label, _, _ in WINDOWS:
        sub = [r for r in results if r["窗口"] == w_label]
        avg_tr = sum(r["total_return"] for r in sub) / len(sub)
        avg_dd = sum(r["max_drawdown"] for r in sub) / len(sub)
        avg_so = sum(r["sortino"] for r in sub) / len(sub)
        wins = sum(1 for r in sub if r["beat_benchmark"])
        print(
            f"  {w_label:<10s}  平均总收益率={avg_tr*100:>+6.2f}%  平均回撤={avg_dd*100:>5.1f}%  "
            f"平均Sortino={avg_so:>6.2f}  跑赢次数={wins}/{len(sub)}"
        )

    # ==================================================================
    # Verify conclusions
    # ==================================================================

    print("\n\n" + "=" * 100)
    print("  结论验证")
    print("=" * 100)

    # Top 10
    print("\n--- Top 10（总收益率最高） ---")
    for i, r in enumerate(results[:10], 1):
        print(
            f"  {i:>2d}. {r['tag']:<42s}  总收益率={r['total_return']*100:>+7.2f}%"
        )

    # Bottom 10
    print("\n--- Bottom 10（总收益率最低） ---")
    for i, r in enumerate(results[-10:], len(results) - 9):
        print(
            f"  {i:>2d}. {r['tag']:<42s}  总收益率={r['total_return']*100:>+7.2f}%"
        )

    # Is 永久组合+一次性+月度 always in top quartile?
    perm_lump_monthly = [
        r
        for r in results
        if r["策略"] == "永久组合"
        and r["投入方式"] == "一次性"
        and r["再平衡"] == "月度"
    ]
    if perm_lump_monthly:
        ranks = [results.index(r) + 1 for r in perm_lump_monthly]
        print(f"\n--- 永久组合+一次性+月度 在全部48组中的排名 ---")
        for r, rank in zip(perm_lump_monthly, ranks):
            print(
                f"  {r['窗口']:<9s}  排名={rank}/48  "
                f"总收益率={r['total_return']*100:>+7.2f}%"
            )

    # Count how often 永久组合 beats 股债30/70
    perm_wins = 0
    total_pairs = 0
    for r1 in results:
        for r2 in results:
            if (
                r1["策略"] == "永久组合"
                and r2["策略"] == "股债30/70"
                and r1["投入方式"] == r2["投入方式"]
                and r1["再平衡"] == r2["再平衡"]
                and r1["窗口"] == r2["窗口"]
            ):
                total_pairs += 1
                if r1["total_return"] > r2["total_return"]:
                    perm_wins += 1

    print(f"\n--- 永久组合 vs 股债30/70（同投入/再平衡/窗口条件下） ---")
    print(f"  永久组合胜出: {perm_wins}/{total_pairs}")

    # Count how often 一次性 beats 定投
    lump_wins = 0
    total_pairs2 = 0
    for r1 in results:
        for r2 in results:
            if (
                r1["投入方式"] == "一次性"
                and r2["投入方式"] == "定投"
                and r1["策略"] == r2["策略"]
                and r1["再平衡"] == r2["再平衡"]
                and r1["窗口"] == r2["窗口"]
            ):
                total_pairs2 += 1
                if r1["total_return"] > r2["total_return"]:
                    lump_wins += 1

    print(f"\n--- 一次性投入 vs 定投（同策略/再平衡/窗口条件下） ---")
    print(f"  一次性胜出: {lump_wins}/{total_pairs2}")

    # Count how often 月度 wins among rebalance freqs
    monthly_best = 0
    for strat_name in STRATEGIES:
        for method_name in INVEST_METHODS:
            for win_label, _, _ in WINDOWS:
                sub = [
                    r
                    for r in results
                    if r["策略"] == strat_name
                    and r["投入方式"] == method_name
                    and r["窗口"] == win_label
                ]
                if sub:
                    best = max(sub, key=lambda x: x["total_return"])
                    if best["再平衡"] == "月度":
                        monthly_best += 1

    print(f"\n--- 再平衡频率对比（在12组固定策略×投入×窗口中，月度最优的次数） ---")
    print(f"  月度最优: {monthly_best}/12")

    # Overall conclusion
    print(f"\n{'=' * 100}")
    print(f"  最终结论（基于总资产收益率）")
    print(f"{'=' * 100}")
    print(
        f"  1. 永久组合 vs 股债30/70: 永久组合胜出 {perm_wins}/{total_pairs} 次 "
        f"({'✅ 永久组合更优' if perm_wins > total_pairs/2 else '❌ 股债30/70更优' if perm_wins < total_pairs/2 else '⚖️ 打平'})"
    )
    print(
        f"  2. 一次性 vs 定投:         一次性胜出 {lump_wins}/{total_pairs2} 次 "
        f"({'✅ 一次性更优' if lump_wins > total_pairs2/2 else '❌ 定投更优' if lump_wins < total_pairs2/2 else '⚖️ 打平'})"
    )
    print(
        f"  3. 月度再平衡:             在 {monthly_best}/12 组中胜出 "
        f"({'✅ 月度最优' if monthly_best >= 6 else '❌ 非最优'})"
    )
    print(f"  4. 最优组合:               {results[0]['tag']}")
    print(
        f"     总收益率 = {results[0]['total_return']*100:+.2f}%, "
        f"年化 = {results[0]['capital_return_annualized']*100:+.2f}%, "
        f"回撤 = {results[0]['max_drawdown']*100:.1f}%"
    )

    # Save results to TSV
    out_dir = Path("results")
    out_dir.mkdir(exist_ok=True)
    tsv_path = out_dir / "full_sweep.tsv"

    cols = [
        "tag",
        "策略",
        "投入方式",
        "再平衡",
        "窗口",
        "total_return",
        "capital_return_annualized",
        "annual_return",
        "max_drawdown",
        "sortino",
        "beat_benchmark",
        "benchmark_return",
    ]
    with open(tsv_path, "w") as f:
        f.write("\t".join(cols) + "\n")
        for r in results:
            row = []
            for c in cols:
                v = r[c]
                if isinstance(v, float):
                    row.append(f"{v:.6f}")
                elif isinstance(v, bool):
                    row.append("1" if v else "0")
                else:
                    row.append(str(v))
            f.write("\t".join(row) + "\n")

    print(f"\n  结果已保存: {tsv_path}")


if __name__ == "__main__":
    main()
