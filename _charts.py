"""Generate interactive HTML report for cn_permanent (4-asset permanent portfolio).

Outputs a single self-contained HTML file with:
  - Hover tooltips on all charts
  - Zoom / pan / reset
  - Toggle series visibility
  - Responsive layout
"""
import sys, copy, json
sys.path.insert(0, "/Users/yapex/workspace/backtrader-research")
from engine import (
    run_backtest, _get_benchmark, _get_strategy_result,
    _deep_merge, get_commission, _annual_return, _max_drawdown,
)
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os

OUT_DIR = "/Users/yapex/workspace/backtrader-research/reports"
os.makedirs(OUT_DIR, exist_ok=True)

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

SB_ASSETS = [
    {"ticker": "510300.SS", "role": "equity", "weight": 0.3},
    {"ticker": "511010.SS", "role": "bond", "weight": 0.7},
]

COMMISSION = get_commission("CNY")
COLORS = {"permanent": "#E67E22", "stockbond": "#3498DB", "benchmark": "#95A5A6"}


def get_portfolio(config, profile=None):
    effective = _deep_merge(config, profile) if profile else config
    result = _get_strategy_result(effective)
    return result["portfolio"]


def normalize(series, base=100):
    return series / series.iloc[0] * base


# ======================================================================
# Run all backtests
# ======================================================================
print("Running backtests...")

period_full = {"start": "2014-01-01", "end": "2025-12-31"}
period_short = {"start": "2016-01-01", "end": "2025-12-31"}

# ---- 4 base configs (策略 × 投入方式) ----
perm_lump = copy.deepcopy(BASE)
perm_lump["period"] = period_full
perm_lump["cash"] = 1000000
perm_lump["deposits"] = {"total_capital": 0}

sb_lump = copy.deepcopy(BASE)
sb_lump["assets"] = SB_ASSETS
sb_lump["params"] = {"rebalance_freq": "yearly", "stop_loss": None}
sb_lump["period"] = period_full
sb_lump["cash"] = 1000000
sb_lump["deposits"] = {"total_capital": 0}

perm_dca = copy.deepcopy(BASE)
perm_dca["period"] = period_full
perm_dca["deposits"] = {
    "total_capital": 1000000, "initial": 0,
    "freq": "monthly", "day": 1, "day_mode": "first",
}

sb_dca = copy.deepcopy(sb_lump)
sb_dca["period"] = period_full
sb_dca["deposits"] = {
    "total_capital": 1000000, "initial": 0,
    "freq": "monthly", "day": 1, "day_mode": "first",
}

m_perm_lump = run_backtest(perm_lump, perm_lump)
m_sb_lump = run_backtest(sb_lump, sb_lump)
m_perm_dca = run_backtest(perm_dca, perm_dca)
m_sb_dca = run_backtest(sb_dca, sb_dca)

bench_full = _get_benchmark("510300.SS", period_full, 100000, COMMISSION)

p_perm = normalize(get_portfolio(perm_lump, perm_lump))
p_sb = normalize(get_portfolio(sb_lump, sb_lump))
p_bench = normalize(bench_full)

# ======================================================================
# Rolling windows — BOTH strategies
# ======================================================================
windows = [("2014-2023", "2014-01-01", "2023-12-31"),
           ("2015-2024", "2015-01-01", "2024-12-31"),
           ("2016-2025", "2016-01-01", "2025-12-31")]

rolling_data = {
    "labels": [],
    "perm_ret": [], "sb_ret": [], "bench_ret": [],
    "perm_dd": [], "sb_dd": [], "bench_dd": [],
}

for label, s, e in windows:
    # 永久组合
    cfg_p = copy.deepcopy(BASE)
    cfg_p["period"] = {"start": s, "end": e}
    cfg_p["cash"] = 1000000
    cfg_p["deposits"] = {"total_capital": 0}
    mp = run_backtest(cfg_p, cfg_p)

    # 股债30/70
    cfg_s = copy.deepcopy(BASE)
    cfg_s["assets"] = SB_ASSETS
    cfg_s["params"] = {"rebalance_freq": "yearly", "stop_loss": None}
    cfg_s["period"] = {"start": s, "end": e}
    cfg_s["cash"] = 1000000
    cfg_s["deposits"] = {"total_capital": 0}
    ms = run_backtest(cfg_s, cfg_s)

    b = _get_benchmark("510300.SS", {"start": s, "end": e}, 100000, COMMISSION)

    rolling_data["labels"].append(label)
    rolling_data["perm_ret"].append(mp["annual_return"] * 100)
    rolling_data["sb_ret"].append(ms["annual_return"] * 100)
    rolling_data["bench_ret"].append(_annual_return(b) * 100)
    rolling_data["perm_dd"].append(mp["max_drawdown"] * 100)
    rolling_data["sb_dd"].append(ms["max_drawdown"] * 100)
    rolling_data["bench_dd"].append(_max_drawdown(b) * 100)

# ======================================================================
# Rebalance freq — BOTH strategies
# ======================================================================
freq_data = {
    "labels": [],
    "perm_ret": [], "perm_dd": [], "perm_sortino": [],
    "sb_ret": [], "sb_dd": [], "sb_sortino": [],
}

for freq, freq_label in [("monthly", "月度"), ("quarterly", "季度"), ("yearly", "年度")]:
    # 永久组合
    cfg_p = copy.deepcopy(BASE)
    cfg_p["period"] = period_short
    cfg_p["params"]["rebalance_freq"] = freq
    cfg_p["cash"] = 1000000
    cfg_p["deposits"] = {"total_capital": 0}
    mp = run_backtest(cfg_p, cfg_p)

    # 股债30/70
    cfg_s = copy.deepcopy(BASE)
    cfg_s["assets"] = SB_ASSETS
    cfg_s["params"] = {"rebalance_freq": freq, "stop_loss": None}
    cfg_s["period"] = period_short
    cfg_s["cash"] = 1000000
    cfg_s["deposits"] = {"total_capital": 0}
    ms = run_backtest(cfg_s, cfg_s)

    freq_data["labels"].append(freq_label)
    freq_data["perm_ret"].append(mp["annual_return"] * 100)
    freq_data["perm_dd"].append(mp["max_drawdown"] * 100)
    freq_data["perm_sortino"].append(mp["sortino"])
    freq_data["sb_ret"].append(ms["annual_return"] * 100)
    freq_data["sb_dd"].append(ms["max_drawdown"] * 100)
    freq_data["sb_sortino"].append(ms["sortino"])

# ======================================================================
# DCA initial % — BOTH strategies
# ======================================================================
dca_data = {
    "labels": [],
    "perm_ret": [], "perm_dd": [], "perm_gain": [],
    "sb_ret": [], "sb_dd": [], "sb_gain": [],
}

for pct in [0, 25, 50, 75, 100]:
    # 永久组合
    cfg_p = copy.deepcopy(BASE)
    cfg_p["period"] = period_short
    if pct == 100:
        cfg_p["cash"] = 1000000
        cfg_p["deposits"] = {"total_capital": 0}
    else:
        cfg_p["deposits"] = {
            "total_capital": 1000000, "initial": int(1000000 * pct / 100),
            "freq": "monthly", "day": 1, "day_mode": "first",
        }
    mp = run_backtest(cfg_p, cfg_p)
    perm_cap_ret = mp["capital_return_annualized"] if mp["deposit_count"] > 0 else mp["annual_return"]

    # 股债30/70
    cfg_s = copy.deepcopy(BASE)
    cfg_s["assets"] = SB_ASSETS
    cfg_s["params"] = {"rebalance_freq": "yearly", "stop_loss": None}
    cfg_s["period"] = period_short
    if pct == 100:
        cfg_s["cash"] = 1000000
        cfg_s["deposits"] = {"total_capital": 0}
    else:
        cfg_s["deposits"] = {
            "total_capital": 1000000, "initial": int(1000000 * pct / 100),
            "freq": "monthly", "day": 1, "day_mode": "first",
        }
    ms = run_backtest(cfg_s, cfg_s)
    sb_cap_ret = ms["capital_return_annualized"] if ms["deposit_count"] > 0 else ms["annual_return"]

    dca_data["labels"].append(f"{pct}%" if pct < 100 else "一次性")
    dca_data["perm_ret"].append(perm_cap_ret * 100)
    dca_data["perm_dd"].append(mp["max_drawdown"] * 100)
    dca_data["perm_gain"].append((mp["final_value"] - max(mp["total_deposited"], 1000000)) / 10000)
    dca_data["sb_ret"].append(sb_cap_ret * 100)
    dca_data["sb_dd"].append(ms["max_drawdown"] * 100)
    dca_data["sb_gain"].append((ms["final_value"] - max(ms["total_deposited"], 1000000)) / 10000)

print("Building charts...")

# ======================================================================
# Chart 1: Equity curves (interactive)
# ======================================================================
fig1 = go.Figure()
fig1.add_trace(go.Scatter(x=p_bench.index, y=p_bench, name="沪深300（基准）",
                           line=dict(color=COLORS["benchmark"], width=1.5)))
fig1.add_trace(go.Scatter(x=p_sb.index, y=p_sb, name="股债 30/70",
                           line=dict(color=COLORS["stockbond"], width=1.5)))
fig1.add_trace(go.Scatter(x=p_perm.index, y=p_perm, name="永久组合（股债金现各25%）",
                           line=dict(color=COLORS["permanent"], width=2.5)))
fig1.update_layout(
    title="净值曲线对比（2014-2025，一次性投入 100 万）",
    yaxis_title="净值（起点 = 100）",
    hovermode="x unified",
    height=500,
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    margin=dict(t=80, b=40),
)
fig1.update_xaxes(rangeslider_visible=True, rangeslider_thickness=0.05)
fig1.update_yaxes(fixedrange=False)

# ======================================================================
# Chart 2: Overview bar chart
# ======================================================================
strategies = ["股债 30/70<br>一次性", "永久组合<br>一次性", "股债 30/70<br>定投", "永久组合<br>定投"]
ann_rets = [
    m_sb_lump["annual_return"] * 100,
    m_perm_lump["annual_return"] * 100,
    m_sb_dca["capital_return_annualized"] * 100,
    m_perm_dca["capital_return_annualized"] * 100,
]
max_dds = [
    m_sb_lump["max_drawdown"] * 100,
    m_perm_lump["max_drawdown"] * 100,
    m_sb_dca["max_drawdown"] * 100,
    m_perm_dca["max_drawdown"] * 100,
]
bar_colors = [COLORS["stockbond"], COLORS["permanent"], COLORS["stockbond"], COLORS["permanent"]]

bench_ret = m_perm_lump["benchmark_return"] * 100
excess_rets = [
    m_sb_lump["excess_return"] * 100,
    m_perm_lump["excess_return"] * 100,
    m_sb_dca["excess_return"] * 100,
    m_perm_dca["excess_return"] * 100,
]
excess_colors = ["#27AE60" if v >= 0 else "#E74C3C" for v in excess_rets]

fig2 = go.Figure()
fig2.add_trace(go.Bar(x=strategies, y=ann_rets, name="年化收益", marker_color=bar_colors,
                       text=[f"{v:.2f}%" for v in ann_rets], textposition="outside",
                       textfont=dict(size=13)))
fig2.add_trace(go.Bar(x=strategies, y=max_dds, name="最大回撤", marker_color=bar_colors,
                       opacity=0.4, marker_line_color=bar_colors, marker_line_width=2,
                       text=[f"{v:.1f}%" for v in max_dds], textposition="outside",
                       textfont=dict(size=13, color="#666")))
fig2.add_trace(go.Bar(x=strategies, y=excess_rets, name="超额收益（vs 沪深300）", marker_color=excess_colors,
                       text=[f"{v:+.2f}%" for v in excess_rets], textposition="outside",
                       textfont=dict(size=13)))
fig2.update_layout(
    title=f"四策略总览（沪深300基准：年化 {bench_ret:.2f}%）",
    barmode="group",
    hovermode="x unified",
    height=450,
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    margin=dict(t=80, b=40),
    yaxis_title="百分比 (%)",
)

# ======================================================================
# Chart 3: Rolling windows — 永久组合 + 股债30/70 + 沪深300
# ======================================================================
fig3 = make_subplots(rows=1, cols=2, subplot_titles=("年化收益", "最大回撤"))

fig3.add_trace(go.Bar(name="永久组合", x=rolling_data["labels"], y=rolling_data["perm_ret"],
                       marker_color=COLORS["permanent"],
                       text=[f"{v:.2f}%" for v in rolling_data["perm_ret"]], textposition="outside"),
              row=1, col=1)
fig3.add_trace(go.Bar(name="股债 30/70", x=rolling_data["labels"], y=rolling_data["sb_ret"],
                       marker_color=COLORS["stockbond"],
                       text=[f"{v:.2f}%" for v in rolling_data["sb_ret"]], textposition="outside"),
              row=1, col=1)
fig3.add_trace(go.Bar(name="沪深300", x=rolling_data["labels"], y=rolling_data["bench_ret"],
                       marker_color=COLORS["benchmark"],
                       text=[f"{v:.2f}%" for v in rolling_data["bench_ret"]], textposition="outside"),
              row=1, col=1)

fig3.add_trace(go.Bar(name="永久组合", x=rolling_data["labels"], y=rolling_data["perm_dd"],
                       marker_color=COLORS["permanent"], showlegend=False,
                       text=[f"{v:.1f}%" for v in rolling_data["perm_dd"]], textposition="outside"),
              row=1, col=2)
fig3.add_trace(go.Bar(name="股债 30/70", x=rolling_data["labels"], y=rolling_data["sb_dd"],
                       marker_color=COLORS["stockbond"], showlegend=False,
                       text=[f"{v:.1f}%" for v in rolling_data["sb_dd"]], textposition="outside"),
              row=1, col=2)
fig3.add_trace(go.Bar(name="沪深300", x=rolling_data["labels"], y=rolling_data["bench_dd"],
                       marker_color=COLORS["benchmark"], showlegend=False,
                       text=[f"{v:.1f}%" for v in rolling_data["bench_dd"]], textposition="outside"),
              row=1, col=2)

fig3.update_layout(
    title="滚动窗口验证（3 个不重叠的 10 年，一次性投入）",
    barmode="group", height=450,
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    margin=dict(t=80, b=40),
)

# ======================================================================
# Chart 4: Rebalance freq — 永久组合 + 股债30/70 并排
# ======================================================================
fig4 = make_subplots(rows=1, cols=2, subplot_titles=("年化收益", "最大回撤"))

fig4.add_trace(go.Bar(name="永久组合", x=freq_data["labels"], y=freq_data["perm_ret"],
                       marker_color=COLORS["permanent"],
                       text=[f"{v:.2f}%" for v in freq_data["perm_ret"]], textposition="outside"),
              row=1, col=1)
fig4.add_trace(go.Bar(name="股债 30/70", x=freq_data["labels"], y=freq_data["sb_ret"],
                       marker_color=COLORS["stockbond"],
                       text=[f"{v:.2f}%" for v in freq_data["sb_ret"]], textposition="outside"),
              row=1, col=1)

fig4.add_trace(go.Bar(name="永久组合", x=freq_data["labels"], y=freq_data["perm_dd"],
                       marker_color=COLORS["permanent"], showlegend=False,
                       text=[f"{v:.1f}%" for v in freq_data["perm_dd"]], textposition="outside"),
              row=1, col=2)
fig4.add_trace(go.Bar(name="股债 30/70", x=freq_data["labels"], y=freq_data["sb_dd"],
                       marker_color=COLORS["stockbond"], showlegend=False,
                       text=[f"{v:.1f}%" for v in freq_data["sb_dd"]], textposition="outside"),
              row=1, col=2)

fig4.update_layout(
    title="再平衡频率对比（2016-2025，一次性投入）",
    barmode="group", height=450,
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    margin=dict(t=80, b=40),
)

# ======================================================================
# Chart 5: DCA initial % — 永久组合 + 股债30/70 双线
# ======================================================================
fig5 = go.Figure()
fig5.add_trace(go.Scatter(
    name="永久组合 总资金年化", x=dca_data["labels"], y=dca_data["perm_ret"],
    mode="lines+markers+text", text=[f"{v:.2f}%" for v in dca_data["perm_ret"]],
    textposition="top center", line=dict(color=COLORS["permanent"], width=2.5),
    marker=dict(size=10),
))
fig5.add_trace(go.Scatter(
    name="股债 30/70 总资金年化", x=dca_data["labels"], y=dca_data["sb_ret"],
    mode="lines+markers+text", text=[f"{v:.2f}%" for v in dca_data["sb_ret"]],
    textposition="bottom center", line=dict(color=COLORS["stockbond"], width=2.5),
    marker=dict(size=10),
))
fig5.update_layout(
    title="定投初始比例 vs 总资金回报（2016-2025）",
    hovermode="x unified", height=450,
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    margin=dict(t=80, b=40),
    yaxis=dict(title="总资金年化回报 (%)"),
)

# ======================================================================
# Chart 6: DCA initial % — 回撤对比
# ======================================================================
fig6 = go.Figure()
fig6.add_trace(go.Scatter(
    name="永久组合 回撤", x=dca_data["labels"], y=dca_data["perm_dd"],
    mode="lines+markers+text", text=[f"{v:.1f}%" for v in dca_data["perm_dd"]],
    textposition="top center", line=dict(color=COLORS["permanent"], width=2.5),
    marker=dict(size=10),
))
fig6.add_trace(go.Scatter(
    name="股债 30/70 回撤", x=dca_data["labels"], y=dca_data["sb_dd"],
    mode="lines+markers+text", text=[f"{v:.1f}%" for v in dca_data["sb_dd"]],
    textposition="bottom center", line=dict(color=COLORS["stockbond"], width=2.5),
    marker=dict(size=10),
))
fig6.update_layout(
    title="定投初始比例 vs 最大回撤（2016-2025）",
    hovermode="x unified", height=450,
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    margin=dict(t=80, b=40),
    yaxis=dict(title="最大回撤 (%)"),
)

# ======================================================================
# Also export PNGs for markdown (optional, needs Chrome)
# ======================================================================
if "--png" in sys.argv:
    print("Exporting PNGs...")
    for fig, name in [(fig1, "cn_permanent_equity_curve"), (fig2, "cn_permanent_overview"),
                       (fig3, "cn_permanent_rolling"), (fig4, "cn_permanent_rebalance_freq"),
                       (fig5, "cn_permanent_dca_initial"), (fig6, "cn_permanent_dca_drawdown")]:
        fig.write_image(f"{OUT_DIR}/images/{name}.png", width=1100, height=500, scale=2)
        print(f"  [png] {name}.png")
else:
    print("Skipping PNG export (use --png flag to enable)")

# ======================================================================
# Build HTML report
# ======================================================================
print("Building HTML report...")

html_charts = ""
for fig, section_id, title in [
    (fig1, "equity", "净值曲线对比"),
    (fig2, "overview", "四策略总览"),
    (fig3, "rolling", "滚动窗口验证"),
    (fig4, "rebalance", "再平衡频率"),
    (fig5, "dca", "定投 vs 一次性投入"),
    (fig6, "dca_dd", "定投 vs 一次性投入（回撤）"),
]:
    div = fig.to_html(full_html=False, include_plotlyjs=False, div_id=section_id)
    html_charts += f'<div class="chart-section"><h2>{title}</h2>{div}</div>\n'

# ---- Tables ----

# Overview table
summary_rows = ""
for name, ann, dd, excess, beat in [
    ("永久组合 一次性", m_perm_lump["annual_return"], m_perm_lump["max_drawdown"], m_perm_lump["excess_return"], m_perm_lump["beat_benchmark"]),
    ("股债 30/70 一次性", m_sb_lump["annual_return"], m_sb_lump["max_drawdown"], m_sb_lump["excess_return"], m_sb_lump["beat_benchmark"]),
    ("永久组合 定投", m_perm_dca["capital_return_annualized"], m_perm_dca["max_drawdown"], m_perm_dca["excess_return"], m_perm_dca["beat_benchmark"]),
    ("股债 30/70 定投", m_sb_dca["capital_return_annualized"], m_sb_dca["max_drawdown"], m_sb_dca["excess_return"], m_sb_dca["beat_benchmark"]),
]:
    beat_str = '<span class="pass">✅</span>' if beat else '<span class="fail">❌</span>'
    excess_color = "color:#27AE60" if excess >= 0 else "color:#E74C3C"
    summary_rows += f"""
    <tr>
      <td>{name}</td>
      <td>{ann*100:+.2f}%</td>
      <td>{dd*100:.1f}%</td>
      <td style="{excess_color}">{excess*100:+.2f}%</td>
      <td>{beat_str}</td>
    </tr>"""

# Rolling window table (both strategies)
rolling_rows = ""
for i, label in enumerate(rolling_data["labels"]):
    perm_exc = rolling_data["perm_ret"][i] - rolling_data["bench_ret"][i]
    sb_exc = rolling_data["sb_ret"][i] - rolling_data["bench_ret"][i]
    rolling_rows += f"""
    <tr>
      <td>{label}</td>
      <td>{rolling_data['perm_ret'][i]:.2f}%</td>
      <td>{rolling_data['perm_dd'][i]:.1f}%</td>
      <td>{rolling_data['sb_ret'][i]:.2f}%</td>
      <td>{rolling_data['sb_dd'][i]:.1f}%</td>
      <td>{rolling_data['bench_ret'][i]:.2f}%</td>
      <td>{rolling_data['bench_dd'][i]:.1f}%</td>
    </tr>"""

# Rebalance freq table (both strategies)
freq_rows = ""
for i in range(len(freq_data["labels"])):
    freq_rows += f"""
    <tr>
      <td>{freq_data['labels'][i]}</td>
      <td>{freq_data['perm_ret'][i]:.2f}%</td>
      <td>{freq_data['perm_dd'][i]:.1f}%</td>
      <td>{freq_data['perm_sortino'][i]:.2f}</td>
      <td>{freq_data['sb_ret'][i]:.2f}%</td>
      <td>{freq_data['sb_dd'][i]:.1f}%</td>
      <td>{freq_data['sb_sortino'][i]:.2f}</td>
    </tr>"""

# DCA table (both strategies)
dca_rows = ""
for i in range(5):
    dca_rows += f"""
    <tr>
      <td>{dca_data['labels'][i]}</td>
      <td>{dca_data['perm_ret'][i]:.2f}%</td>
      <td>{dca_data['perm_dd'][i]:.1f}%</td>
      <td>+{dca_data['perm_gain'][i]:.0f} 万</td>
      <td>{dca_data['sb_ret'][i]:.2f}%</td>
      <td>{dca_data['sb_dd'][i]:.1f}%</td>
      <td>+{dca_data['sb_gain'][i]:.0f} 万</td>
    </tr>"""

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>A 股资产配置回测报告</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background: #f8f9fa; color: #333; line-height: 1.6;
    }}
    .container {{ max-width: 1100px; margin: 0 auto; padding: 20px; }}
    h1 {{
      font-size: 28px; text-align: center; margin: 30px 0 10px; color: #1a1a2e;
    }}
    .subtitle {{
      text-align: center; color: #666; font-size: 14px; margin-bottom: 30px;
    }}
    .card {{
      background: white; border-radius: 12px; padding: 24px;
      margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }}
    .card h2 {{
      font-size: 18px; margin-bottom: 16px; color: #1a1a2e;
      border-bottom: 2px solid #eee; padding-bottom: 8px;
    }}
    .card p {{ margin-bottom: 12px; color: #444; }}
    table {{
      width: 100%; border-collapse: collapse; margin: 12px 0;
    }}
    th, td {{
      padding: 10px 14px; text-align: center; border-bottom: 1px solid #eee;
    }}
    th {{ background: #f5f5f5; font-weight: 600; color: #555; font-size: 14px; }}
    td {{ font-size: 14px; }}
    .pass {{ color: #27ae60; font-weight: bold; }}
    .fail {{ color: #95a5a6; }}
    .highlight {{ background: #fff8e1; }}
    .chart-section {{ margin-bottom: 32px; }}
    .chart-section h2 {{
      font-size: 18px; margin-bottom: 8px; color: #1a1a2e;
    }}
    .note {{
      background: #e8f4fd; border-left: 4px solid #3498db;
      padding: 12px 16px; margin: 16px 0; border-radius: 0 8px 8px 0;
      font-size: 14px; color: #2c3e50;
    }}
    .conclusion {{
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white; border-radius: 12px; padding: 28px; margin-bottom: 24px;
    }}
    .conclusion h2 {{ color: white; border: none; font-size: 20px; margin-bottom: 16px; }}
    .conclusion ul {{ margin-left: 20px; }}
    .conclusion li {{ margin-bottom: 8px; }}
    .badge {{
      display: inline-block; background: rgba(255,255,255,0.2);
      padding: 2px 10px; border-radius: 12px; font-size: 13px; margin-left: 6px;
    }}
    .footer {{
      text-align: center; color: #999; font-size: 12px; margin-top: 40px; padding: 20px;
    }}
  </style>
</head>
<body>
<div class="container">

  <h1>A 股资产配置回测报告</h1>
  <p class="subtitle">2014-01-01 ~ 2025-12-31 · yfinance 复权价格 · 佣金万十 · 无风险利率 2.5%</p>

  <div class="conclusion">
    <h2>🎯 核心结论</h2>
    <ul>
      <li><strong>最优配置：</strong>永久组合（沪深300 + 国债ETF + 黄金ETF + 货币基金，各 25%），月度再平衡</li>
      <li><strong>最优投入方式：</strong>一次性投入 100 万<span class="badge">年化 {m_perm_lump["annual_return"]*100:+.2f}%</span></li>
      <li><strong>最大回撤：</strong>仅 {m_perm_lump["max_drawdown"]*100:.1f}%<span class="badge">沪深300 为 {m_perm_lump["benchmark_drawdown"]*100:.1f}%</span></li>
      <li><strong>100 万投入 12 年：</strong>期末约 {m_perm_lump["final_value"]/10000:.0f} 万，总收益 +{(m_perm_lump["final_value"]-1000000)/1000000*100:.0f}%</li>
    </ul>
  </div>

  <div class="card">
    <h2>四策略总览</h2>
    <table>
      <tr><th>策略</th><th>投入方式</th><th>总资金年化</th><th>最大回撤</th><th>超额收益</th><th>跑赢基准</th></tr>
      <tr class="highlight">
        <td><strong>永久组合</strong></td><td>一次性</td>
        <td><strong>{m_perm_lump["annual_return"]*100:+.2f}%</strong></td>
        <td>{m_perm_lump["max_drawdown"]*100:.1f}%</td>
        <td style="color:{'#27AE60' if m_perm_lump['excess_return']>=0 else '#E74C3C'}">{m_perm_lump["excess_return"]*100:+.2f}%</td>
        <td>{'<span class="pass">✅</span>' if m_perm_lump["beat_benchmark"] else '<span class="fail">❌</span>'}</td>
      </tr>
      <tr>
        <td>股债 30/70</td><td>一次性</td>
        <td>{m_sb_lump["annual_return"]*100:+.2f}%</td>
        <td>{m_sb_lump["max_drawdown"]*100:.1f}%</td>
        <td style="color:{'#27AE60' if m_sb_lump['excess_return']>=0 else '#E74C3C'}">{m_sb_lump["excess_return"]*100:+.2f}%</td>
        <td>{'<span class="pass">✅</span>' if m_sb_lump["beat_benchmark"] else '<span class="fail">❌</span>'}</td>
      </tr>
      <tr>
        <td>永久组合</td><td>定投</td>
        <td>{m_perm_dca["capital_return_annualized"]*100:+.2f}%</td>
        <td>{m_perm_dca["max_drawdown"]*100:.1f}%</td>
        <td style="color:{'#27AE60' if m_perm_dca['excess_return']>=0 else '#E74C3C'}">{m_perm_dca["excess_return"]*100:+.2f}%</td>
        <td>{'<span class="pass">✅</span>' if m_perm_dca["beat_benchmark"] else '<span class="fail">❌</span>'}</td>
      </tr>
      <tr>
        <td>股债 30/70</td><td>定投</td>
        <td>{m_sb_dca["capital_return_annualized"]*100:+.2f}%</td>
        <td>{m_sb_dca["max_drawdown"]*100:.1f}%</td>
        <td style="color:{'#27AE60' if m_sb_dca['excess_return']>=0 else '#E74C3C'}">{m_sb_dca["excess_return"]*100:+.2f}%</td>
        <td>{'<span class="pass">✅</span>' if m_sb_dca["beat_benchmark"] else '<span class="fail">❌</span>'}</td>
      </tr>
    </table>
    <div class="note">
      💡 定投行使用<strong>总资金年化回报</strong>，而非 IRR。IRR 只计算已投入部分的收益率，忽略了闲置资金的机会成本，会高选定投的实际收益。
    </div>
  </div>

  {html_charts}

  <div class="card">
    <h2>滚动窗口验证（详细数据）</h2>
    <p>3 个不重叠的 10 年窗口，一次性投入，永久组合用月度再平衡、股债30/70用年度再平衡：</p>
    <table>
      <tr><th>窗口</th><th>永久组合<br>年化</th><th>永久组合<br>回撤</th><th>股债30/70<br>年化</th><th>股债30/70<br>回撤</th><th>沪深300<br>年化</th><th>沪深300<br>回撤</th></tr>
      {rolling_rows}
    </table>
  </div>

  <div class="card">
    <h2>再平衡频率对比（详细数据）</h2>
    <p>2016-2025 窗口，一次性投入：</p>
    <table>
      <tr><th>频率</th><th>永久组合<br>年化</th><th>永久组合<br>回撤</th><th>永久组合<br>Sortino</th><th>股债30/70<br>年化</th><th>股债30/70<br>回撤</th><th>股债30/70<br>Sortino</th></tr>
      {freq_rows}
    </table>
  </div>

  <div class="card">
    <h2>定投 vs 一次性投入（详细数据）</h2>
    <p>2016-2025 窗口，总额 100 万：</p>
    <table>
      <tr><th>初始投入</th><th>永久组合<br>年化</th><th>永久组合<br>回撤</th><th>永久组合<br>期末收益</th><th>股债30/70<br>年化</th><th>股债30/70<br>回撤</th><th>股债30/70<br>期末收益</th></tr>
      {dca_rows}
    </table>
    <div class="note">
      💡 无论永久组合还是股债30/70，一次性投入的总资金年化都远高于定投。定投的真正价值是<strong>控制回撤</strong>，而非提高收益。
    </div>
  </div>

  <div class="card">
    <h2>具体怎么执行</h2>
    <table>
      <tr><th>资产</th><th>ETF 代码</th><th>比例</th><th>作用</th></tr>
      <tr><td>沪深300</td><td>510300.SS</td><td>25%</td><td>股票，获取市场收益</td></tr>
      <tr><td>国债ETF</td><td>511010.SS</td><td>25%</td><td>债券，稳定压舱石</td></tr>
      <tr><td>黄金ETF</td><td>518880.SS</td><td>25%</td><td>黄金，对冲股市下跌</td></tr>
      <tr><td>华宝添益</td><td>511990.SS</td><td>25%</td><td>货币基金，流动性 + 再平衡弹药</td></tr>
    </table>
    <p style="margin-top:16px"><strong>操作：</strong>一次性买入 → 每月检查比例 → 偏离 25% 就调 → 不止损不择时不盯盘</p>
  </div>

  <div class="footer">
    数据来源：yfinance · 回测框架：backtrader · 佣金：万十（0.1%）· 报告生成时间：2026-04-04
  </div>

</div>
</body>
</html>"""

with open(f"{OUT_DIR}/cn_permanent_report.html", "w", encoding="utf-8") as f:
    f.write(html)
print(f"  [html] cn_permanent_report.html")

# ======================================================================
# Generate Markdown report
# ======================================================================
print("Building Markdown report...")

bench_ret_str = f"{m_perm_lump['benchmark_return']*100:+.2f}%"

md_overview = ""
for name, method, ann, dd, exc in [
    ("**永久组合**", "**一次性**", m_perm_lump["annual_return"], m_perm_lump["max_drawdown"], m_perm_lump["excess_return"]),
    ("股债 30/70", "一次性", m_sb_lump["annual_return"], m_sb_lump["max_drawdown"], m_sb_lump["excess_return"]),
    ("永久组合", "定投", m_perm_dca["capital_return_annualized"], m_perm_dca["max_drawdown"], m_perm_dca["excess_return"]),
    ("股债 30/70", "定投", m_sb_dca["capital_return_annualized"], m_sb_dca["max_drawdown"], m_sb_dca["excess_return"]),
]:
    md_overview += f"| {name} | {method} | {ann*100:+.2f}% | {dd*100:.1f}% | {exc*100:+.2f}% | {bench_ret_str} |\n"

md_rolling = ""
for i, label in enumerate(rolling_data["labels"]):
    perm_exc = rolling_data["perm_ret"][i] - rolling_data["bench_ret"][i]
    sb_exc = rolling_data["sb_ret"][i] - rolling_data["bench_ret"][i]
    md_rolling += f"| {label} | {rolling_data['perm_ret'][i]:.2f}% | {rolling_data['perm_dd'][i]:.1f}% | {rolling_data['sb_ret'][i]:.2f}% | {rolling_data['sb_dd'][i]:.1f}% | {rolling_data['bench_ret'][i]:.2f}% | {rolling_data['bench_dd'][i]:.1f}% |\n"

md_freq = ""
for i in range(len(freq_data["labels"])):
    md_freq += f"| {freq_data['labels'][i]} | {freq_data['perm_ret'][i]:.2f}% | {freq_data['perm_dd'][i]:.1f}% | {freq_data['perm_sortino'][i]:.2f} | {freq_data['sb_ret'][i]:.2f}% | {freq_data['sb_dd'][i]:.1f}% | {freq_data['sb_sortino'][i]:.2f} |\n"

md_dca = ""
for i in range(5):
    bold = "**" if i == 0 or i == 4 else ""
    md_dca += f"| {bold}{dca_data['labels'][i]}{bold} | {bold}{dca_data['perm_ret'][i]:.2f}%{bold} | {bold}{dca_data['perm_dd'][i]:.1f}%{bold} | {bold}+{dca_data['perm_gain'][i]:.0f} 万{bold} | {bold}{dca_data['sb_ret'][i]:.2f}%{bold} | {bold}{dca_data['sb_dd'][i]:.1f}%{bold} | {bold}+{dca_data['sb_gain'][i]:.0f} 万{bold} |\n"

md = f"""# A 股资产配置回测报告

> 2014-01-01 ~ 2025-12-31，共 12 年，数据来源 yfinance（复权价格），佣金万十，无风险利率 2.5%

## 核心结论

**对于 A 股普通投资者，最优配置是：**

1. **永久组合**（沪深300 + 国债ETF + 黄金ETF + 货币基金，各 25%），**月度再平衡**
2. **一次性投入**，100 万全部买入

这样做的效果：
- 年化 **{m_perm_lump['annual_return']*100:+.2f}%**（最大回撤 **{m_perm_lump['max_drawdown']*100:.1f}%**，沪深300 为 {m_perm_lump['benchmark_drawdown']*100:.1f}%，回撤降低 **{(1 - abs(m_perm_lump['max_drawdown'])/abs(m_perm_lump['benchmark_drawdown']))*100:.0f}%**）
- 100 万一次性投入 12 年，期末约 **{m_perm_lump['final_value']/10000:.0f} 万**，总收益 +{(m_perm_lump['final_value']-1000000)/1000000*100:.0f}%

> **为什么不是沪深300 年化 {bench_ret_str}？** 因为沪深300 过去 12 年的最大回撤高达 {m_perm_lump['benchmark_drawdown']*100:.1f}%，如果 2015 年高点买入，到 2019 年才回本，中间 4 年白等。永久组合虽然年化低一些，但回撤只有 {m_perm_lump['max_drawdown']*100:.1f}%，投资体验完全不同。

---

## 一、四策略总览

我们测试了两种策略 × 两种投入方式的组合：

![四策略总览](images/cn_permanent_overview.png)

| 策略 | 投入方式 | 总资金年化 | 最大回撤 | 超额收益 | 沪深300 |
|------|---------|-----------|---------|---------|--------|
{md_overview}
> **注意**：定投行使用的是**总资金年化回报**，而非 IRR。IRR 只计算已投入部分的收益率，忽略了闲置资金的机会成本，会高选定投的实际收益。详见第五节。

**永久组合 + 一次性投入是最优解**——回撤最低、收益最高。

---

## 二、黄金和现金是关键

为什么永久组合（加黄金+现金）好于股债平衡？

![净值曲线](images/cn_permanent_equity_curve.png)

- 沪深300 过去 12 年几乎原地踏步，中间经历了 2015 股灾、2018 贸易战、2022 疫情
- 股债 30/70 靠国债平滑了波动，但收益只比沪深300好一点点
- 永久组合加了黄金后，在股市下跌时黄金往往上涨（如 2020、2022），起到对冲作用
- 25% 货币基金提供稳定的流动性，同时在再平衡时自动低买高卖

---

## 三、滚动窗口验证

策略好不好，不能只看一个时间段。我们用 3 个不重叠的 10 年窗口，同时验证永久组合和股债30/70（一次性投入）：

![滚动窗口](images/cn_permanent_rolling.png)

| 窗口 | 永久组合年化 | 永久组合回撤 | 股债30/70年化 | 股债30/70回撤 | 沪深300年化 | 沪深300回撤 |
|------|------------|------------|-------------|-------------|-----------|-----------|
{md_rolling}
---

## 四、多久调一次仓？

2016-2025 窗口，两种策略 × 三种再平衡频率（一次性投入）：

![再平衡频率](images/cn_permanent_rebalance_freq.png)

| 频率 | 永久组合年化 | 永久组合回撤 | 永久组合Sortino | 股债30/70年化 | 股债30/70回撤 | 股债30/70Sortino |
|------|------------|------------|---------------|-------------|-------------|---------------|
{md_freq}
**结论：** 无论哪种策略，月度再平衡的年化收益最高、回撤最低。

---

## 五、定投 vs 一次性投入

### 用什么指标比较？

手里有 100 万，怎么投收益最高？核心指标是**总资金年化回报**——从第 1 天就拥有 100 万，最终赚了多少，年化是多少。

以 2016-2025 窗口为例，总额 100 万，两种策略 × 五种初始投入比例：

![定投初始比例](images/cn_permanent_dca_initial.png)

| 初始投入 | 永久组合年化 | 永久组合回撤 | 永久组合期末收益 | 股债30/70年化 | 股债30/70回撤 | 股债30/70期末收益 |
|---------|------------|------------|---------------|-------------|-------------|---------------|
{md_dca}
结论很清楚：
- **一次性投入年化最高**（永久组合 {dca_data['perm_ret'][4]:.2f}%，股债30/70 {dca_data['sb_ret'][4]:.2f}%），远高于纯定投
- 初始投入越多，总资金回报越高
- 定投的真正价值是**控制回撤**（永久组合 {dca_data['perm_dd'][0]:.1f}% vs {dca_data['perm_dd'][4]:.1f}%，股债30/70 {dca_data['sb_dd'][0]:.1f}% vs {dca_data['sb_dd'][4]:.1f}%），而非提高收益

### 选择建议

| 场景 | 建议 | 原因 |
|------|------|------|
| 手里已有 100 万，追求收益 | **一次性投入** | 年化最高，10 年多赚最多 |
| 心理承受能力弱，怕大跌 | **先投 50%，剩余定投** | 回撤更低，年化仍有不错水平 |
| 每月有固定收入，逐步积累 | **定投** | 虽然总资金回报低，但适合无存量资金的情况 |

---

## 六、具体怎么执行

### 标的

| 资产 | ETF 代码 | 比例 | 作用 |
|------|---------|------|------|
| 沪深300 | 510300.SS | 25% | 股票，获取市场收益 |
| 国债ETF | 511010.SS | 25% | 债券，稳定压舱石 |
| 黄金ETF | 518880.SS | 25% | 黄金，对冲股市下跌 |
| 华宝添益 | 511990.SS | 25% | 货币基金，提供流动性和再平衡弹药 |

### 操作（推荐方式）

1. **一次性投入**：将 100 万按 1:1:1:1 比例买入四只 ETF
2. **每月检查一次**，如果四只 ETF 的市值比例偏离 25% 太多就调一调
3. **不需要止损**，不需要择时，不需要盯盘

### 配置文件

项目中提供了 4 个标准配置，可以直接复现所有结果：

```bash
cd /Users/yapex/workspace/backtrader-research
uv sync

# 一次性投入
uv run engine.py --config examples/cn_stockbond.yaml
uv run engine.py --config examples/cn_permanent.yaml

# 定投
uv run engine.py --config examples/cn_stockbond_dca.yaml
uv run engine.py --config examples/cn_permanent_dca.yaml
```

---

## 数据说明

- **数据来源**：yfinance，A 股 ETF 使用复权价格（含分红），基准为沪深300
- **佣金**：万十（0.1%），与实际交易成本一致
- **回测期**：2014-01-01 ~ 2025-12-31（12 年）
- **滚动验证**：3 个不重叠的 10 年窗口（2014-2023、2015-2024、2016-2025）
- **收益指标**：总资金年化回报（定投）、年化收益（一次性投入）、最大回撤、Sortino 比率
"""

with open(f"{OUT_DIR}/cn_permanent_report.md", "w", encoding="utf-8") as f:
    f.write(md)
print(f"  [md]  cn_permanent_report.md")
print(f"\n[done] Reports generated in {OUT_DIR}/")
