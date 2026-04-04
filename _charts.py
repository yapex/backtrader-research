"""Generate report charts for cn_permanent (4-asset permanent portfolio)."""
import sys, copy
sys.path.insert(0, "/Users/yapex/workspace/backtrader-research")
from engine import run_backtest, _get_benchmark, _get_strategy_result, _deep_merge, get_commission
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import os

plt.rcParams["font.family"] = ["Arial Unicode MS", "PingFang SC", "Heiti TC", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

OUT = "/Users/yapex/workspace/backtrader-research/reports/images"
os.makedirs(OUT, exist_ok=True)

BASE = {
    "benchmark": "510300.SS",
    "currency": "CNY",
    "assets": [
        {"ticker": "510300.SS", "role": "equity", "weight": 0.25},
        {"ticker": "511010.SS", "role": "bond", "weight": 0.25},
        {"ticker": "518880.SS", "role": "gold", "weight": 0.25},
        {"ticker": "511990.SS", "role": "cash", "weight": 0.25},
    ],
    "params": {"rebalance_freq": "monthly", "stop_loss": None},
}

COMMISSION = get_commission("CNY")
COLORS = {
    "permanent": "#E67E22",
    "stockbond": "#3498DB",
    "benchmark": "#95A5A6",
    "dca_permanent": "#E67E22",
    "dca_stockbond": "#3498DB",
}


def get_portfolio(config, profile=None):
    effective = _deep_merge(config, profile) if profile else config
    result = _get_strategy_result(effective)
    return result["portfolio"]


def normalize(series, base=100):
    return series / series.iloc[0] * base


# ======================================================================
# Chart 1: Overview bar chart (4 strategies)
# ======================================================================
def chart_overview():
    strategies = [
        ("股债 30/70\n一次性", "stockbond", False),
        ("永久组合\n一次性", "permanent", False),
        ("股债 30/70\n定投", "stockbond", True),
        ("永久组合\n定投", "permanent", True),
    ]
    configs = {
        "permanent": {
            "benchmark": "510300.SS", "currency": "CNY",
            "assets": [
                {"ticker": "510300.SS", "role": "equity", "weight": 0.25},
                {"ticker": "511010.SS", "role": "bond", "weight": 0.25},
                {"ticker": "518880.SS", "role": "gold", "weight": 0.25},
                {"ticker": "511990.SS", "role": "cash", "weight": 0.25},
            ],
            "params": {"rebalance_freq": "monthly", "stop_loss": None},
        },
        "stockbond": {
            "benchmark": "510300.SS", "currency": "CNY",
            "assets": [
                {"ticker": "510300.SS", "role": "equity", "weight": 0.3},
                {"ticker": "511010.SS", "role": "bond", "weight": 0.7},
            ],
            "params": {"rebalance_freq": "monthly", "stop_loss": None},
        },
    }
    periods = [
        {"start": "2014-01-01", "end": "2025-12-31"},
        {"start": "2016-01-01", "end": "2025-12-31"},
    ]

    annual_rets = []
    max_dds = []
    labels = []
    colors = []

    for name, key, is_dca in strategies:
        cfg = copy.deepcopy(configs[key])
        cfg["period"] = periods[1 if is_dca else 0]
        if is_dca:
            cfg["deposits"] = {
                "total_capital": 1000000, "initial": 0,
                "freq": "monthly", "day": 1, "day_mode": "first",
            }
        else:
            cfg["cash"] = 1000000
            cfg["deposits"] = {"total_capital": 0}

        m = run_backtest(cfg, cfg)
        if is_dca:
            annual_rets.append(m["capital_return_annualized"] * 100)
        else:
            annual_rets.append(m["annual_return"] * 100)
        max_dds.append(m["max_drawdown"] * 100)
        labels.append(name)
        colors.append(COLORS["dca_" + key] if is_dca else COLORS[key])

    fig, ax1 = plt.subplots(figsize=(10, 5))
    x = np.arange(len(labels))
    w = 0.35
    bars1 = ax1.bar(x - w/2, annual_rets, w, color=colors, alpha=0.85, label="年化收益(%)")
    bars2 = ax1.bar(x + w/2, max_dds, w, color=colors, alpha=0.4, edgecolor=colors, linewidth=1.2, label="最大回撤(%)")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=11)
    ax1.set_ylabel("百分比 (%)", fontsize=11)
    ax1.legend(fontsize=10, loc="upper right")
    ax1.axhline(y=0, color="grey", linewidth=0.5)
    for bar in bars1:
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, h + 0.2, f"{h:.1f}%",
                 ha="center", va="bottom", fontsize=9, fontweight="bold")
    for bar in bars2:
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, h - 0.5, f"{h:.1f}%",
                 ha="center", va="top", fontsize=9, color="#555")
    ax1.set_title("四策略总览：年化收益 vs 最大回撤", fontsize=13, fontweight="bold")
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    plt.tight_layout()
    plt.savefig(f"{OUT}/cn_permanent_overview.png", dpi=150)
    plt.close()
    print("[chart] overview")


# ======================================================================
# Chart 2: Equity curves (2014-2025, lump sum)
# ======================================================================
def chart_equity_curve():
    period = {"start": "2014-01-01", "end": "2025-12-31"}

    # Permanent portfolio
    perm = copy.deepcopy(BASE)
    perm["period"] = period
    perm["cash"] = 1000000
    perm["deposits"] = {"total_capital": 0}
    p_perm = normalize(get_portfolio(perm, perm))

    # Stock/bond 30/70
    sb = copy.deepcopy(perm)
    sb["assets"] = [
        {"ticker": "510300.SS", "role": "equity", "weight": 0.3},
        {"ticker": "511010.SS", "role": "bond", "weight": 0.7},
    ]
    sb["params"] = {"rebalance_freq": "yearly", "stop_loss": None}
    p_sb = normalize(get_portfolio(sb, sb))

    # Benchmark
    bench = _get_benchmark("510300.SS", period, 100000, COMMISSION)
    p_bench = normalize(bench)

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(p_bench.index, p_bench, color=COLORS["benchmark"], linewidth=1.5, label="沪深300（基准）")
    ax.plot(p_sb.index, p_sb, color=COLORS["stockbond"], linewidth=1.5, label="股债 30/70")
    ax.plot(p_perm.index, p_perm, color=COLORS["permanent"], linewidth=2, label="永久组合（股债金现各25%）")
    ax.set_ylabel("净值（起点=100）", fontsize=11)
    ax.set_title("净值曲线对比（2014-2025，一次性投入）", fontsize=13, fontweight="bold")
    ax.legend(fontsize=10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    plt.savefig(f"{OUT}/cn_permanent_equity_curve.png", dpi=150)
    plt.close()
    print("[chart] equity_curve")


# ======================================================================
# Chart 3: Rolling windows (2014-2023, 2015-2024, 2016-2025)
# ======================================================================
def chart_rolling():
    windows = [("2014-2023", "2014-01-01", "2023-12-31"),
               ("2015-2024", "2015-01-01", "2024-12-31"),
               ("2016-2025", "2016-01-01", "2025-12-31")]

    perm_annual = []
    bench_annual = []
    perm_dd = []
    bench_dd = []
    wlabels = []

    for label, start, end in windows:
        cfg = copy.deepcopy(BASE)
        cfg["period"] = {"start": start, "end": end}
        cfg["cash"] = 1000000
        cfg["deposits"] = {"total_capital": 0}
        m = run_backtest(cfg, cfg)
        perm_annual.append(m["annual_return"] * 100)

        bench = _get_benchmark("510300.SS", {"start": start, "end": end}, 100000, COMMISSION)
        from engine import _annual_return, _max_drawdown
        bench_annual.append(_annual_return(bench) * 100)
        bench_dd.append(_max_drawdown(bench) * 100)
        perm_dd.append(m["max_drawdown"] * 100)
        wlabels.append(label)

    x = np.arange(len(wlabels))
    w = 0.3
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    ax1.bar(x - w/2, perm_annual, w, color=COLORS["permanent"], label="永久组合")
    ax1.bar(x + w/2, bench_annual, w, color=COLORS["benchmark"], label="沪深300")
    ax1.set_xticks(x)
    ax1.set_xticklabels(wlabels)
    ax1.set_ylabel("年化收益 (%)", fontsize=11)
    ax1.set_title("滚动窗口年化收益", fontsize=12, fontweight="bold")
    ax1.legend(fontsize=10)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    ax2.bar(x - w/2, perm_dd, w, color=COLORS["permanent"], label="永久组合")
    ax2.bar(x + w/2, bench_dd, w, color=COLORS["benchmark"], label="沪深300")
    ax2.set_xticks(x)
    ax2.set_xticklabels(wlabels)
    ax2.set_ylabel("最大回撤 (%)", fontsize=11)
    ax2.set_title("滚动窗口最大回撤", fontsize=12, fontweight="bold")
    ax2.legend(fontsize=10)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    plt.tight_layout()
    plt.savefig(f"{OUT}/cn_permanent_rolling.png", dpi=150)
    plt.close()
    print("[chart] rolling")


# ======================================================================
# Chart 4: Rebalance frequency
# ======================================================================
def chart_rebalance_freq():
    freqs = ["monthly", "quarterly", "yearly"]
    freq_labels = ["月度", "季度", "年度"]
    annuals = []
    dds = []
    sortinos = []

    for freq in freqs:
        cfg = copy.deepcopy(BASE)
        cfg["period"] = {"start": "2016-01-01", "end": "2025-12-31"}
        cfg["params"]["rebalance_freq"] = freq
        cfg["cash"] = 1000000
        cfg["deposits"] = {"total_capital": 0}
        m = run_backtest(cfg, cfg)
        annuals.append(m["annual_return"] * 100)
        dds.append(m["max_drawdown"] * 100)
        sortinos.append(m["sortino"])

    x = np.arange(len(freqs))
    fig, ax = plt.subplots(figsize=(8, 5))
    w = 0.25
    ax.bar(x - w, annuals, w, color="#27AE60", label="年化收益(%)")
    ax.bar(x, [-d for d in dds], w, color="#E74C3C", label="最大回撤(%)")
    ax.bar(x + w, sortinos, w, color="#3498DB", label="Sortino")
    ax.set_xticks(x)
    ax.set_xticklabels(freq_labels, fontsize=11)
    ax.set_ylabel("数值", fontsize=11)
    ax.set_title("再平衡频率对比（2016-2025）", fontsize=13, fontweight="bold")
    ax.legend(fontsize=10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    plt.savefig(f"{OUT}/cn_permanent_rebalance_freq.png", dpi=150)
    plt.close()
    print("[chart] rebalance_freq")


# ======================================================================
# Chart 5: DCA initial % (2016-2025)
# ======================================================================
def chart_dca_initial():
    pcts = [0, 25, 50, 75, 100]
    annuals = []
    dds = []

    for pct in pcts:
        cfg = copy.deepcopy(BASE)
        cfg["period"] = {"start": "2016-01-01", "end": "2025-12-31"}
        if pct == 100:
            cfg["cash"] = 1000000
            cfg["deposits"] = {"total_capital": 0}
        else:
            cfg["deposits"] = {
                "total_capital": 1000000, "initial": int(1000000 * pct / 100),
                "freq": "monthly", "day": 1, "day_mode": "first",
            }
        m = run_backtest(cfg, cfg)
        if m["deposit_count"] > 0:
            annuals.append(m["capital_return_annualized"] * 100)
        else:
            annuals.append(m["annual_return"] * 100)
        dds.append(m["max_drawdown"] * 100)

    labels = ["0%\n(纯定投)", "25%", "50%", "75%", "100%\n(一次性)"]
    x = np.arange(len(labels))

    fig, ax1 = plt.subplots(figsize=(9, 5))
    bars = ax1.bar(x, annuals, 0.5, color=[COLORS["permanent"] if p < 100 else "#27AE60" for p in pcts],
                   alpha=0.85, edgecolor="white", linewidth=1)
    ax2 = ax1.twinx()
    ax2.plot(x, dds, "o-", color="#E74C3C", linewidth=2, markersize=8, label="最大回撤")

    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=11)
    ax1.set_ylabel("总资金年化回报 (%)", fontsize=11, color=COLORS["permanent"])
    ax2.set_ylabel("最大回撤 (%)", fontsize=11, color="#E74C3C")
    ax1.set_title("定投初始比例 vs 总资金回报（2016-2025，永久组合）", fontsize=13, fontweight="bold")

    for bar, val in zip(bars, annuals):
        ax1.text(bar.get_x() + bar.get_width()/2, val + 0.15, f"{val:.1f}%",
                 ha="center", va="bottom", fontsize=10, fontweight="bold")
    for i, val in enumerate(dds):
        ax2.annotate(f"{val:.1f}%", (x[i], val), textcoords="offset points",
                     xytext=(0, -14), ha="center", fontsize=9, color="#E74C3C")

    ax2.legend(fontsize=10, loc="upper left")
    ax1.spines["top"].set_visible(False)
    plt.tight_layout()
    plt.savefig(f"{OUT}/cn_permanent_dca_initial.png", dpi=150)
    plt.close()
    print("[chart] dca_initial")


if __name__ == "__main__":
    chart_overview()
    chart_equity_curve()
    chart_rolling()
    chart_rebalance_freq()
    chart_dca_initial()
    print("\n[done] all charts saved to", OUT)
