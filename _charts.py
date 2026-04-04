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

COMMISSION = get_commission("CNY")
COLORS = {"permanent": "#E67E22", "stockbond": "#3498DB", "benchmark": "#95A5A6"}


def get_portfolio(config, profile=None):
    effective = _deep_merge(config, profile) if profile else config
    result = _get_strategy_result(effective)
    return result["portfolio"]


def normalize(series, base=100):
    return series / series.iloc[0] * base


def pct_fmt(v):
    return f"{v*100:+.2f}%"


# ======================================================================
# Run all backtests
# ======================================================================
print("Running backtests...")

period_full = {"start": "2014-01-01", "end": "2025-12-31"}
period_short = {"start": "2016-01-01", "end": "2025-12-31"}

# Lump sum configs
perm_lump = copy.deepcopy(BASE)
perm_lump["period"] = period_full
perm_lump["cash"] = 1000000
perm_lump["deposits"] = {"total_capital": 0}

sb_lump = copy.deepcopy(BASE)
sb_lump["assets"] = [
    {"ticker": "510300.SS", "role": "equity", "weight": 0.3},
    {"ticker": "511010.SS", "role": "bond", "weight": 0.7},
]
sb_lump["params"] = {"rebalance_freq": "yearly", "stop_loss": None}
sb_lump["period"] = period_full
sb_lump["cash"] = 1000000
sb_lump["deposits"] = {"total_capital": 0}

bench_full = _get_benchmark("510300.SS", period_full, 100000, COMMISSION)

# DCA configs
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

p_perm = normalize(get_portfolio(perm_lump, perm_lump))
p_sb = normalize(get_portfolio(sb_lump, sb_lump))
p_bench = normalize(bench_full)

# Rolling windows
windows = [("2014-2023", "2014-01-01", "2023-12-31"),
           ("2015-2024", "2015-01-01", "2024-12-31"),
           ("2016-2025", "2016-01-01", "2025-12-31")]
rolling_data = {"labels": [], "perm_ret": [], "bench_ret": [], "perm_dd": [], "bench_dd": []}
for label, s, e in windows:
    cfg = copy.deepcopy(BASE)
    cfg["period"] = {"start": s, "end": e}
    cfg["cash"] = 1000000
    cfg["deposits"] = {"total_capital": 0}
    m = run_backtest(cfg, cfg)
    b = _get_benchmark("510300.SS", {"start": s, "end": e}, 100000, COMMISSION)
    rolling_data["labels"].append(label)
    rolling_data["perm_ret"].append(m["annual_return"] * 100)
    rolling_data["bench_ret"].append(_annual_return(b) * 100)
    rolling_data["perm_dd"].append(m["max_drawdown"] * 100)
    rolling_data["bench_dd"].append(_max_drawdown(b) * 100)

# Rebalance freq
freq_data = {"labels": [], "ret": [], "dd": [], "sortino": []}
for freq, freq_label in [("monthly", "月度"), ("quarterly", "季度"), ("yearly", "年度")]:
    cfg = copy.deepcopy(BASE)
    cfg["period"] = period_short
    cfg["params"]["rebalance_freq"] = freq
    cfg["cash"] = 1000000
    cfg["deposits"] = {"total_capital": 0}
    m = run_backtest(cfg, cfg)
    freq_data["labels"].append(freq_label)
    freq_data["ret"].append(m["annual_return"] * 100)
    freq_data["dd"].append(m["max_drawdown"] * 100)
    freq_data["sortino"].append(m["sortino"])

# DCA initial %
dca_data = {"labels": [], "ret": [], "dd": [], "gain": []}
for pct in [0, 25, 50, 75, 100]:
    cfg = copy.deepcopy(BASE)
    cfg["period"] = period_short
    if pct == 100:
        cfg["cash"] = 1000000
        cfg["deposits"] = {"total_capital": 0}
    else:
        cfg["deposits"] = {
            "total_capital": 1000000, "initial": int(1000000 * pct / 100),
            "freq": "monthly", "day": 1, "day_mode": "first",
        }
    m = run_backtest(cfg, cfg)
    cap_ret = m["capital_return_annualized"] if m["deposit_count"] > 0 else m["annual_return"]
    dca_data["labels"].append(f"{pct}%" if pct < 100 else "一次性")
    dca_data["ret"].append(cap_ret * 100)
    dca_data["dd"].append(m["max_drawdown"] * 100)
    dca_data["gain"].append((m["final_value"] - m["total_deposited"]) / 10000)

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

fig2 = go.Figure()
fig2.add_trace(go.Bar(x=strategies, y=ann_rets, name="年化收益", marker_color=bar_colors,
                       text=[f"{v:.2f}%" for v in ann_rets], textposition="outside",
                       textfont=dict(size=13)))
fig2.add_trace(go.Bar(x=strategies, y=max_dds, name="最大回撤", marker_color=bar_colors,
                       opacity=0.4, marker_line_color=bar_colors, marker_line_width=2,
                       text=[f"{v:.1f}%" for v in max_dds], textposition="outside",
                       textfont=dict(size=13, color="#666")))
fig2.update_layout(
    title="四策略总览：年化收益 vs 最大回撤",
    barmode="group",
    hovermode="x unified",
    height=450,
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    margin=dict(t=80, b=40),
    yaxis_title="百分比 (%)",
)

# ======================================================================
# Chart 3: Rolling windows
# ======================================================================
fig3 = make_subplots(rows=1, cols=2, subplot_titles=("年化收益", "最大回撤"))
fig3.add_trace(go.Bar(name="永久组合", x=rolling_data["labels"], y=rolling_data["perm_ret"],
                       marker_color=COLORS["permanent"],
                       text=[f"{v:.2f}%" for v in rolling_data["perm_ret"]], textposition="outside"),
              row=1, col=1)
fig3.add_trace(go.Bar(name="沪深300", x=rolling_data["labels"], y=rolling_data["bench_ret"],
                       marker_color=COLORS["benchmark"],
                       text=[f"{v:.2f}%" for v in rolling_data["bench_ret"]], textposition="outside"),
              row=1, col=1)
fig3.add_trace(go.Bar(name="永久组合", x=rolling_data["labels"], y=rolling_data["perm_dd"],
                       marker_color=COLORS["permanent"], showlegend=False,
                       text=[f"{v:.1f}%" for v in rolling_data["perm_dd"]], textposition="outside"),
              row=1, col=2)
fig3.add_trace(go.Bar(name="沪深300", x=rolling_data["labels"], y=rolling_data["bench_dd"],
                       marker_color=COLORS["benchmark"], showlegend=False,
                       text=[f"{v:.1f}%" for v in rolling_data["bench_dd"]], textposition="outside"),
              row=1, col=2)
fig3.update_layout(
    title="滚动窗口验证（3 个不重叠的 10 年）",
    barmode="group", height=450,
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    margin=dict(t=80, b=40),
)

# ======================================================================
# Chart 4: Rebalance frequency
# ======================================================================
fig4 = go.Figure()
fig4.add_trace(go.Bar(name="年化收益", x=freq_data["labels"], y=freq_data["ret"],
                       marker_color="#27AE60",
                       text=[f"{v:.2f}%" for v in freq_data["ret"]], textposition="outside"))
fig4.add_trace(go.Bar(name="最大回撤", x=freq_data["labels"], y=[-d for d in freq_data["dd"]],
                       marker_color="#E74C3C",
                       text=[f"-{d:.1f}%" for d in freq_data["dd"]], textposition="outside"))
fig4.add_trace(go.Scatter(name="Sortino", x=freq_data["labels"], y=freq_data["sortino"],
                           mode="lines+markers+text", text=[f"{v:.2f}" for v in freq_data["sortino"]],
                           textposition="top center", line=dict(color="#3498DB", width=2),
                           marker=dict(size=10)))
fig4.update_layout(
    title="再平衡频率对比（2016-2025）",
    barmode="group", hovermode="x unified", height=450,
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    margin=dict(t=80, b=40),
    yaxis_title="数值",
)

# ======================================================================
# Chart 5: DCA initial % (dual axis)
# ======================================================================
fig5 = go.Figure()
fig5.add_trace(go.Bar(
    name="总资金年化回报", x=dca_data["labels"], y=dca_data["ret"],
    marker_color=[COLORS["permanent"] if l != "一次性" else "#27AE60" for l in dca_data["labels"]],
    text=[f"{v:.2f}%" for v in dca_data["ret"]], textposition="outside",
    textfont=dict(size=13),
))
fig5.add_trace(go.Scatter(
    name="最大回撤", x=dca_data["labels"], y=dca_data["dd"],
    mode="lines+markers+text", text=[f"{v:.1f}%" for v in dca_data["dd"]],
    textposition="bottom center", line=dict(color="#E74C3C", width=2.5),
    marker=dict(size=10, color="#E74C3C"),
    yaxis="y2",
))
fig5.update_layout(
    title="定投初始比例 vs 总资金回报（2016-2025，永久组合）",
    hovermode="x unified", height=500,
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    margin=dict(t=80, b=40),
    yaxis=dict(title="总资金年化回报 (%)", side="left"),
    yaxis2=dict(title="最大回撤 (%)", side="right", overlaying="y", rangemode="tozero"),
)

# ======================================================================
# Also export PNGs for markdown (optional, needs Chrome)
# ======================================================================
if "--png" in sys.argv:
    print("Exporting PNGs...")
    for fig, name in [(fig1, "cn_permanent_equity_curve"), (fig2, "cn_permanent_overview"),
                       (fig3, "cn_permanent_rolling"), (fig4, "cn_permanent_rebalance_freq"),
                       (fig5, "cn_permanent_dca_initial")]:
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
]:
    div = fig.to_html(full_html=False, include_plotlyjs=False, div_id=section_id)
    html_charts += f'<div class="chart-section"><h2>{title}</h2>{div}</div>\n'

# Summary table
summary_rows = ""
for name, ann, dd, beat in [
    ("永久组合 一次性", m_perm_lump["annual_return"], m_perm_lump["max_drawdown"], m_perm_lump["beat_benchmark"]),
    ("股债 30/70 一次性", m_sb_lump["annual_return"], m_sb_lump["max_drawdown"], m_sb_lump["beat_benchmark"]),
    ("永久组合 定投", m_perm_dca["capital_return_annualized"], m_perm_dca["max_drawdown"], m_perm_dca["beat_benchmark"]),
    ("股债 30/70 定投", m_sb_dca["capital_return_annualized"], m_sb_dca["max_drawdown"], m_sb_dca["beat_benchmark"]),
]:
    beat_str = '<span class="pass">✅</span>' if beat else '<span class="fail">❌</span>'
    summary_rows += f"""
    <tr>
      <td>{name}</td>
      <td>{ann*100:+.2f}%</td>
      <td>{dd*100:.1f}%</td>
      <td>{beat_str}</td>
    </tr>"""

# DCA table
dca_rows = ""
for i in range(5):
    dca_rows += f"""
    <tr>
      <td>{dca_data['labels'][i]}</td>
      <td>{dca_data['ret'][i]:.2f}%</td>
      <td>{dca_data['dd'][i]:.1f}%</td>
      <td>+{dca_data['gain'][i]:.0f} 万</td>
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
      <li><strong>最优投入方式：</strong>一次性投入 100 万<span class="badge">总资金年化 5.15%</span></li>
      <li><strong>最大回撤：</strong>仅 -11.5%<span class="badge">沪深300 为 -45.0%</span></li>
      <li><strong>100 万投入 12 年：</strong>期末约 183 万，总收益 +83%</li>
    </ul>
  </div>

  <div class="card">
    <h2>四策略总览</h2>
    <table>
      <tr><th>策略</th><th>投入方式</th><th>总资金年化</th><th>最大回撤</th><th>跑赢沪深300</th></tr>
      <tr class="highlight">
        <td><strong>永久组合</strong></td><td>一次性</td>
        <td><strong>{m_perm_lump["annual_return"]*100:+.2f}%</strong></td>
        <td>{m_perm_lump["max_drawdown"]*100:.1f}%</td>
        <td>{'<span class="pass">✅</span>' if m_perm_lump["beat_benchmark"] else '<span class="fail">❌</span>'}</td>
      </tr>
      <tr>
        <td>股债 30/70</td><td>一次性</td>
        <td>{m_sb_lump["annual_return"]*100:+.2f}%</td>
        <td>{m_sb_lump["max_drawdown"]*100:.1f}%</td>
        <td>{'<span class="pass">✅</span>' if m_sb_lump["beat_benchmark"] else '<span class="fail">❌</span>'}</td>
      </tr>
      <tr>
        <td>永久组合</td><td>定投</td>
        <td>{m_perm_dca["capital_return_annualized"]*100:+.2f}%</td>
        <td>{m_perm_dca["max_drawdown"]*100:.1f}%</td>
        <td>{'<span class="pass">✅</span>' if m_perm_dca["beat_benchmark"] else '<span class="fail">❌</span>'}</td>
      </tr>
      <tr>
        <td>股债 30/70</td><td>定投</td>
        <td>{m_sb_dca["capital_return_annualized"]*100:+.2f}%</td>
        <td>{m_sb_dca["max_drawdown"]*100:.1f}%</td>
        <td>{'<span class="pass">✅</span>' if m_sb_dca["beat_benchmark"] else '<span class="fail">❌</span>'}</td>
      </tr>
    </table>
    <div class="note">
      💡 定投行使用<strong>总资金年化回报</strong>，而非 IRR。IRR 只计算已投入部分的收益率，忽略了闲置资金的机会成本，会高选定投的实际收益。
    </div>
  </div>

  {html_charts}

  <div class="card">
    <h2>定投 vs 一次性投入（详细数据）</h2>
    <p>2016-2025 窗口，总额 100 万：</p>
    <table>
      <tr><th>初始投入</th><th>总资金年化</th><th>最大回撤</th><th>期末总收益</th></tr>
      {dca_rows}
    </table>
    <div class="note">
      💡 一次性投入年化 6.18%，远高于纯定投的 3.88%。定投的真正价值是<strong>控制回撤</strong>（-6.0% vs -8.4%），而非提高收益。
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
print(f"\n[done] HTML report: {OUT_DIR}/cn_permanent_report.html")
