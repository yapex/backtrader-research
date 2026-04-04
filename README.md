# backtrader-research

帮普通用户找最优资产配置的回测框架。

## 核心问题

> 选好 ETF 和债券后，**按什么比例、多久调一次、要不要止损**，收益最高、回撤最小？

## 两种回测模式

### 模式一：资产配置回测

三维度穷举搜索（比例 × 频率 × 止损），自动生成 75 种组合并排名。

```bash
# 单个 profile
uv run engine.py --profile 6040_Q_none

# 批量穷举
bash sweep.sh

# 查看排名
sort -t$'\t' -k2 -rn results/results_*.tsv | head -20
```

### 模式二：定投回测

支持固定总额和无限定投两种模式，计算 IRR、平均成本、vs 一次性投入对比。

```bash
# A 股定投（100万，按月自动算金额）
uv run engine.py --config examples/dca_cn300_fixed.yaml

# A 股定投穷举（5 比例 × 5 初始比例 = 25 组合）
bash sweep.sh examples/dca_sweep_cn.yaml

# 美股周频定投（每周 $500）
uv run engine.py --config examples/dca_sp500_weekly.yaml
```

## 搜索空间

| 维度 | 选项 | 用户理解 |
|------|------|---------|
| **比例** | 70/30、60/40、50/50、40/60、30/70 | 股票占多少，债券占多少 |
| **频率** | 月度(M)、季度(Q)、年度(Y) | 多久调一次 |
| **止损** | 无、10%、15%、20%、25% | 跌多少就跑 |

共 5 × 3 × 5 = **75 种组合**，逐一跑完即可找到最优解。

## 评分规则

score = 夏普比率（收益/风险），带惩罚和奖励：
- 最大回撤 > 30%: score -= 0.1
- 最大回撤 > 40%: score -= 0.3
- 跑赢基准（纯持有 ETF）: score += 0.05
- 超额收益 > 1%: score += 0.05

## 快速开始

```bash
uv sync

# 用默认配置跑（美股股债平衡）
uv run engine.py

# 跑 example 配置
uv run engine.py --config examples/cn_dividend.yaml

# 批量穷举所有 profile
bash sweep.sh

# 清除缓存
bash sweep.sh --clear
```

## Example 配置

| 文件 | 市场 | 模式 | 标的 |
|------|------|------|------|
| `us_stockbond.yaml` | 美股 | 资产配置 | SPY + TLT |
| `us_permanent.yaml` | 美股 | 资产配置 | SPY + TLT + GLD + MINT |
| `cn_stockbond.yaml` | A 股 | 资产配置 | 沪深300 + 国债 |
| `cn_permanent.yaml` | A 股 | 资产配置 | 沪深300 + 国债 + 黄金 |
| `cn_dividend.yaml` | A 股 | 资产配置 | 红利ETF + 国债 |
| `cn_zhongzheng_red.yaml` | A 股 | 资产配置 | 中证红利 + 国债 |
| `dca_cn300_fixed.yaml` | A 股 | 定投 | 沪深300（自动算金额） |
| `dca_sp500_weekly.yaml` | 美股 | 定投 | SPY（每周 $500） |
| `dca_sweep_cn.yaml` | A 股 | 定投穷举 | 沪深300 + 国债（25 组合） |

## 核心结论

### 资产配置

| 市场 | 结论 |
|------|------|
| **美股** | 所有策略跑不赢纯买 SPY，但回撤能缩一半。追求收益选 70/30 季度+25%止损，追求安稳选永久组合经典配置 |
| **A 股** | 所有策略都能跑赢沪深300！永久组合（股债金各1/3）年化 **7.38%**，远超基准 2.50% |
| **止损** | 在两个市场都效果有限 |
| **频率** | 年度再平衡最省心，和月度/季度差别不大 |

### 定投（A 股）

| 策略 | IRR | 最大回撤 | 跑赢基准 |
|------|-----|---------|---------|
| 60/40 初始0% | +3.44% | -12.56% | ✅ |
| 50/50 初始0% | +3.31% | -9.69% | ✅ |
| 70/30 初始0% | +3.57% | -15.31% | ✅ |

初始投入比例越高收益越高，但回撤也越大。初始 0%（纯定投）回撤最小。

## 数据源

| 市场 | 数据源 | 示例 ticker |
|------|--------|------------|
| A 股 ETF / 指数 | akshare | `510300.SS`、`000922.SS` |
| 美股 / 港股 | yfinance | `SPY`、`0700.HK` |

## 项目结构

| 文件 | 说明 |
|------|------|
| `engine.py` | 统一回测引擎（3 层缓存：数据 → 基准 → 策略） |
| `strategy.py` | 统一策略（定投 + 再平衡 + 止损） |
| `research.yaml` | 默认实验配置（含 metadata） |
| `_sweep.py` | 参数穷举驱动 |
| `sweep.sh` | 批量穷举入口 |
| `program.md` | 研究指引（评分规则、搜索空间） |
| `cn_permanent_report.md` | A 股永久组合回测报告 |
| `examples/` | 各市场示例配置 |
| `results/` | 实验结果数据（TSV + 图表） |

## 技术特性

- **3 层缓存**：数据（7d TTL）→ 基准（90d）→ 策略（90d），改评分只重算不重跑
- **统一引擎**：资产配置和定投共用 `engine.py` + `strategy.py`，通过 YAML 配置驱动
- **配置驱动**：通过 YAML 添加 profile，无需改代码
