"""CLI output formatting.

SRP: Solely responsible for formatting and printing backtest results.
"""

from __future__ import annotations


def print_results(
    m: dict,
    effective: dict,
    profile_name: str = "",
    desc: str = "",
) -> None:
    """Print formatted backtest results to stdout."""
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
        print(f"  定投期数:         {m['deposit_count']:>11d}")

    print("=" * 60)
