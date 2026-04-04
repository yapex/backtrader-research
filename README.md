# backtrader-research

A 股资产配置回测框架。用历史数据回答：**手上有 100 万，怎么投收益最高、回撤最小？**

## 快速开始

```bash
uv sync

# 一行命令，无需写 YAML
uv run engine.py --compare 159905.SZ 510880.SS --period 2019-2025

# 股债平衡、永久组合，只填"股"那个位置
uv run engine.py --stock-bond 159905.SZ 510880.SS --dca
uv run engine.py --permanent 159905.SZ 510880.SS

# 传统 YAML 配置模式
uv run engine.py --config examples/cn_permanent.yaml

# 生成交互式 HTML 报告（含所有图表）
uv run python _charts.py

# 清除缓存
uv run python -c "from btresearch import clear_cache; clear_cache()"
```

## CLI 用法

### 买入持有模式

| 命令 | 说明 |
|------|------|
| `--buy 159905.SZ` | 单只基金买入持有 |
| `--compare 159905.SZ 510880.SS 512890.SS` | 多只基金横向对比 |

### 模板模式（只换"股"那个位置）

| 命令 | 说明 |
|------|------|
| `--stock-bond 159905.SZ 510880.SS` | 股债 30/70（股=输入，债=国债ETF 固定） |
| `--permanent 159905.SZ 510880.SS` | 永久组合（股=输入，债/金/现 固定） |

### 全局参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--period 2019-2025` | `2014-2025` | 回测区间，支持 `2019-2025` 或 `2019-01-01:2025-12-31` |
| `--benchmark 510300.SS` | 沪深300 ETF | 基准（默认按币种选择） |
| `--cash 1000000` | `1000000` | 初始资金（或定投总额） |
| `--currency CNY` | `CNY` | 币种 |
| `--dca` | 关 | 切换为定投模式 |
| `--rebalance monthly` | `monthly` | 再平衡频率：`monthly` / `quarterly` / `yearly` / `never` |

### 模板内置的固定资产

| 模板 | 股 | 债 | 金 | 现金 |
|------|----|----|----|------|
| `--stock-bond` | 30%（输入） | 70%（511010 国债ETF） | — | — |
| `--permanent` | 25%（输入） | 25%（511010 国债ETF） | 25%（518880 黄金ETF） | 25%（511990 货币基金） |

### 示例

```bash
# 红利 ETF 系列横向对比（买入持有）
uv run engine.py --compare 159905.SZ 510880.SS 512890.SS 515180.SS --period 2019-2025

# 红利 ETF 作为"股"放入股债组合，定投，季度调仓
uv run engine.py --stock-bond 159905.SZ 510880.SS --period 2019-2025 --dca --rebalance quarterly

# 永久组合，一次性投入
uv run engine.py --permanent 159905.SZ 510880.SS --period 2019-2025
```

## 核心结论（A 股，2014-2025）

### 永久组合 / 股债平衡（沪深300 作为股）

| 策略 | 投入方式 | 总资金年化 | 最大回撤 | 超额收益 | 沪深300 |
|------|---------|-----------|---------|---------|---------|
| 永久组合 | 一次性 | +6.11% | -12.5% | -1.86% | +7.98% |
| 股债 30/70 | 一次性 | +5.17% | -16.1% | -2.80% | +7.98% |
| 永久组合 | 定投 | +3.49% | -5.9% | -4.49% | +7.98% |
| 股债 30/70 | 定投 | +2.00% | -9.2% | -5.97% | +7.98% |

### 红利 ETF 系列对比（2019-2025，买入持有）

| 基金 | 年化收益 | 最大回撤 | 超额收益 vs 沪深300 |
|------|---------|---------|---------------------|
| 上证红利 510880 | +8.22% | -19.96% | -0.65% |
| 中证红利 159905 | +8.05% | -49.51% | -0.82% |
| 中证红利低波 512890 | +2.37% | -49.16% | -6.50% |
| 沪深300（基准） | +8.87% | -41.75% | — |

### 红利 ETF 系列（2019-2025，永久组合）

| 基金（作为股） | 年化收益 | 最大回撤 | 超额收益 vs 沪深300 |
|---------------|---------|---------|---------------------|
| 中证红利低波 512890 | +8.54% | -5.44% | -0.33% |
| 中证红利 159905 | +7.88% | -13.19% | -0.99% |
| 上证红利 510880 | +7.73% | -5.53% | -1.14% |
| 沪深300（基准） | +8.87% | -41.75% | — |

- 永久组合回撤从沪深300的 -45% 降到 -5~-13%，代价是年化低 1-2 个百分点
- 一次性投入始终优于定投（定投的闲置资金拖累了总收益）
- 详细报告见 [`reports/cn_permanent_report.html`](reports/cn_permanent_report.html)

## YAML 配置模式

模板模式覆盖大多数场景，复杂配置仍可用 YAML：

```yaml
# 一次性投入
cash: 1000000
assets:
  - ticker: 510300.SS
    weight: 0.25
  - ticker: 511010.SS
    weight: 0.25
  - ticker: 518880.SS
    weight: 0.25
  - ticker: 511990.SS
    weight: 0.25
params:
  rebalance_freq: monthly
  stop_loss: null

# 定投
deposits:
  total_capital: 1000000
  initial: 0
  freq: monthly
  day: 1
  day_mode: first
```

## Example 配置

| 文件 | 策略 | 投入方式 |
|------|------|---------|
| `cn_permanent.yaml` | 永久组合（股债金现 25%×4） | 一次性 |
| `cn_permanent_dca.yaml` | 永久组合 | 定投 |
| `cn_stockbond.yaml` | 股债 30/70 | 一次性 |
| `cn_stockbond_dca.yaml` | 股债 30/70 | 定投 |
| `cn_dividend.yaml` | 中证红利 ETF 买入持有 | 一次性 |
| `cn_dividend_lowvol.yaml` | 红利低波/红利/上证红利对比 | 一次性 |

## 项目结构

```
btresearch/            # 核心包（SOLID 重构）
  __init__.py          # 公共 API 导出
  config.py            # 配置加载、市场默认值
  cache.py             # CacheManager（3 层缓存）
  data_provider.py     # 数据源协议 + 注册（Yahoo / akshare / ETF）
  metrics.py           # 指标协议 + 组合评估器
  engine.py            # 引擎（依赖注入）
  output.py            # CLI 输出格式化
  tracker.py           # 组合净值跟踪器
  commission.py        # 佣金模型
  feed.py              # DataFrame → backtrader 数据转换
  strategy.py          # 策略（再平衡 + 定投 + 止损）
engine.py              # CLI 入口（模板模式 + YAML 模式 + 向后兼容 facade）
_charts.py             # 交互式图表 + 报告生成（Plotly）
_sweep.py              # 参数穷举驱动
examples/              # YAML 配置文件
reports/               # 生成的报告（HTML + MD + 图表）
```

## 技术特性

- **一行命令**：`--compare`、`--stock-bond`、`--permanent` 模板模式，不需要写 YAML
- **模板化**：股债平衡和永久组合只需填"股"的位置，债/金/现内置固定
- **3 层缓存**：数据（7d）→ 基准（90d）→ 策略（90d），改指标只重算不重跑
- **SOLID 架构**：Protocol 接口、依赖注入、开闭原则（添加数据源/指标不改现有代码）
- **交互式报告**：Plotly 图表，支持 hover / zoom / pan
