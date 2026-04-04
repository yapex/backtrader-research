# backtrader-research

A 股资产配置回测框架。用历史数据回答：**手上有 100 万，怎么投收益最高、回撤最小？**

## 快速开始

```bash
uv sync

# 跑单个配置
uv run engine.py --config examples/cn_permanent.yaml

# 生成交互式 HTML 报告（含所有图表）
uv run python _charts.py

# 清除缓存
uv run python -c "from engine import clear_cache; clear_cache()"
```

## 核心结论（A 股，2014-2025）

| 策略 | 投入方式 | 总资金年化 | 最大回撤 | 超额收益 | 沪深300 |
|------|---------|-----------|---------|---------|---------|
| 永久组合 | 一次性 | +6.11% | -12.5% | -1.86% | +7.98% |
| 股债 30/70 | 一次性 | +5.17% | -16.1% | -2.80% | +7.98% |
| 永久组合 | 定投 | +3.49% | -5.9% | -4.49% | +7.98% |
| 股债 30/70 | 定投 | +2.00% | -9.2% | -5.97% | +7.98% |

- 永久组合（沪深300 + 国债 + 黄金 + 货币基金，各 25%）年化虽然打不过沪深300，但回撤从 -45% 降到 -12%
- 一次性投入始终优于定投（定投的闲置资金拖累了总收益）
- 详细报告见 [`reports/cn_permanent_report.html`](reports/cn_permanent_report.html)

## 配置说明

### 一次性投入

```yaml
cash: 1000000          # 初始资金
assets:
  - ticker: 510300.SS  # 沪深300
    weight: 0.25
  - ticker: 511010.SS  # 国债ETF
    weight: 0.25
  - ticker: 518880.SS  # 黄金ETF
    weight: 0.25
  - ticker: 511990.SS  # 货币基金（华宝添益）
    weight: 0.25
params:
  rebalance_freq: monthly   # monthly | quarterly | yearly | never
  stop_loss: null           # null | 0.10 | 0.15 | 0.20
```

### 定投

```yaml
deposits:
  total_capital: 1000000    # 总额
  initial: 0                # 初始投入比例
  freq: monthly             # weekly | monthly
  day: 1
  day_mode: first           # exact | first | last
```

## Example 配置

| 文件 | 策略 | 投入方式 |
|------|------|---------|
| `cn_permanent.yaml` | 永久组合（股债金现 25%×4） | 一次性 |
| `cn_permanent_dca.yaml` | 永久组合 | 定投 |
| `cn_stockbond.yaml` | 股债 30/70 | 一次性 |
| `cn_stockbond_dca.yaml` | 股债 30/70 | 定投 |

## 项目结构

```
engine.py              # 回测引擎（3 层缓存）
strategy.py            # 策略（再平衡 + 定投 + 止损）
_charts.py             # 交互式图表 + 报告生成（Plotly）
_sweep.py              # 参数穷举驱动
sweep.sh               # 批量穷举入口
examples/              # 配置文件
reports/               # 生成的报告（HTML + MD + 图表）
```

## 技术特性

- **3 层缓存**：数据（7d）→ 基准（90d）→ 策略（90d），改指标只重算不重跑
- **统一引擎**：资产配置和定投共用 engine + strategy，YAML 配置驱动
- **交互式报告**：Plotly 图表，支持 hover / zoom / pan
