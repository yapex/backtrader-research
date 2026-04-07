# backtrader-research

A 股 / 美股资产配置回测框架。用历史数据回答：**手上有 100 万，怎么投收益最高、回撤最小？**

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

## 核心结论

### A 股最优配置（2014-2025，12 年）

**阈值 7% + 危机模式（回撤 10% → 切到 3/39/34/24）**

| 指标 | 原始永久组合 | 最优配置 | 沪深300 |
|------|------------|---------|---------|
| Sortino | 0.724 | **1.094** | 0.313 |
| 年化收益 | +6.1% | **+8.4%** | +8.0% |
| 最大回撤 | -12.5% | **-10.8%** | -45.0% |

- 危机模式是 A 股杀手锏：回撤超 10% 自动切到防御配置（股票砍到 3%），Sortino 提升 35%
- 黄金是 12 年里收益最高的单一资产（年化 12.3%），超过沪深300
- 逆向模式（别人恐惧我贪婪）在 A 股彻底失败——A 股阴跌特性下加仓等于接飞刀

### 美股最优配置（2005-2025，21 年）

**40% QQQ + 20% AGG + 20% GLD + 20% SHY + 阈值 10%（无危机模式）**

| 指标 | 永久组合（30% QQQ） | 最优配置 | SPY |
|------|-------------------|---------|-----|
| Sortino | 0.804 | **0.862** | 0.428 |
| 年化收益 | +8.6% | **+10.3%** | +10.6% |
| 最大回撤 | -18.9% | **-23.2%** | -54.4% |

- 美股可以更激进：40% QQQ 能多捕获上行趋势，10% 阈值避免频繁打断
- 美股不需要危机模式——大跌后反弹快，砍仓反而错过反弹
- 收益接近 SPY，回撤仅为其 43%

### 中美对比

| | A 股 | 美股 |
|--|------|------|
| 最强单一资产 | 黄金（12.3%） | QQQ（14.8%） |
| 股票 vs 黄金 | 黄金碾压股票 | 股票碾压黄金 |
| 最优调仓阈值 | 7% | **10%** |
| 危机模式 | ✅ 需要 | ❌ 不需要 |
| 逆向模式 | ❌ 失败 | ❌ 失败 |

> 详细报告见 [`reports/autonomous_experiment_report.md`](reports/autonomous_experiment_report.md)

### 红利 ETF 系列对比（2019-2025，买入持有）

| 基金 | 年化收益 | 最大回撤 | 超额收益 vs 沪深300 |
|------|---------|---------|---------------------|
| 上证红利 510880 | +8.22% | -19.96% | -0.65% |
| 中证红利 159905 | +8.05% | -49.51% | -0.82% |
| 中证红利低波 512890 | +2.37% | -49.16% | -6.50% |
| 沪深300（基准） | +8.87% | -41.75% | — |

### 永久组合 vs 定投

| 策略 | 投入方式 | 总资金年化 | 最大回撤 | 超额收益 | 沪深300 |
|------|---------|-----------|---------|---------|---------|
| 永久组合 | 一次性 | +6.11% | -12.5% | -1.86% | +7.98% |
| 股债 30/70 | 一次性 | +5.17% | -16.1% | -2.80% | +7.98% |
| 永久组合 | 定投 | +3.49% | -5.9% | -4.49% | +7.98% |
| 股债 30/70 | 定投 | +2.00% | -9.2% | -5.97% | +7.98% |

- 一次性投入始终优于定投（定投的闲置资金拖累了总收益）

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

### YAML params 完整参考

```yaml
params:
  rebalance_freq: monthly        # never|monthly|quarterly|yearly
  rebalance_threshold: 0.05      # null=off, 0.05=rebalance when any asset deviates >5%
  stop_loss: null                 # null=off, 0.15=trigger at -15% drawdown
  stop_loss_mode: clear           # clear=清仓, crisis=切换到危机权重, contrarian=逆向加仓
  crisis_weights:                 # 危机/逆向模式触发的目标权重
    510300.SS: 0.03
    511010.SS: 0.39
    518880.SS: 0.34
    511990.SS: 0.24
  recovery_threshold: 0.05       # contrarian: 回撤收窄到此值以下 → 恢复原仓位
  profit_take: 0.10               # contrarian: 从谷底反弹超过此值 → 进入止盈模式
  profit_take_weights:            # 止盈模式的目标权重（降低股票占比）
    510300.SS: 0.15
    511010.SS: 0.30
    518880.SS: 0.30
    511990.SS: 0.25
```

三种回撤管理模式：

| 模式 | 触发条件 | 行为 | 适用场景 |
|------|---------|------|---------|
| `clear` | 回撤超阈值 | 全部清仓 | 极端保守 |
| `crisis` | 回撤超阈值 | 切到防御权重（减股票） | **A 股最优** ✅ |
| `contrarian` | 回撤超阈值 | 切到进攻权重（加股票） | 实验证明无效 ❌ |

### Example 配置

| 文件 | 策略 | 投入方式 |
|------|------|---------|
| `cn_permanent.yaml` | 永久组合（股债金现 25%×4） | 一次性 |
| `cn_permanent_dca.yaml` | 永久组合 | 定投 |
| `cn_stockbond.yaml` | 股债 30/70 | 一次性 |
| `cn_stockbond_dca.yaml` | 股债 30/70 | 定投 |
| `cn_dividend.yaml` | 中证红利 ETF 买入持有 | 一次性 |
| `cn_dividend_lowvol.yaml` | 红利低波/红利/上证红利对比 | 一次性 |
| `cn_perm_best.yaml` | 永久组合 + 阈值7% + 危机模式 | 一次性 |
| `cn_perm_thresh_07.yaml` | 永久组合 + 阈值7% | 一次性 |

## 项目结构

```
btresearch/            # 核心包（SOLID 架构，只读）
  __init__.py          # 公共 API 导出
  config.py            # 配置加载、市场默认值（佣金/基准/无风险利率）
  cache.py             # CacheManager（3 层缓存：数据→基准→策略）
  data_provider.py     # 数据源协议 + 注册（Yahoo / akshare / ETF）
  metrics.py           # 指标协议 + 组合评估器（Sortino/Sharpe/Calmar/IRR）
  engine.py            # 引擎（依赖注入，3 层缓存编排）
  output.py            # CLI 输出格式化
  tracker.py           # 组合净值跟踪器（backtrader Analyzer）
  commission.py        # 佣金模型（百分比制）
  feed.py              # DataFrame → backtrader 数据转换
  strategy.py          # 策略（再平衡 + 定投 + 止损 + 危机 + 逆向 + 止盈）

engine.py              # CLI 入口（模板模式 + YAML 模式，只读）
validate.py            # 滚动窗口交叉验证（5~10 年窗口，稳健性/过拟合评估）
retro_validate.py      # 全量配置回溯验证（自动扫描所有 YAML）
progress.py            # 实验进度可视化（Sortino 曲线）

_charts.py             # 交互式图表 + 报告生成（Plotly）
_sweep.py              # 参数穷举驱动（批量 YAML）
_full_sweep.py         # 全维度参数扫描
_contrarian.py         # 逆向模式实验（A 股 54 组 + 美股 72 组参数扫描）
_gap_analysis.py       # 补盲实验（美股阈值验证 + 危机权重验证）
_final_compare.py      # 终极对比（最终资产排名）
_real_fees.py          # 真实费率修正（A 股 ETF 佣金 万2.5）

examples/              # YAML 配置文件（可修改、可新建）
reports/               # 生成的报告（HTML + MD + 图表）
results/               # 扫描结果（TSV）
results.tsv            # 实验记录（每次实验自动记录）
```

## 技术特性

- **一行命令**：`--compare`、`--stock-bond`、`--permanent` 模板模式，不需要写 YAML
- **模板化**：股债平衡和永久组合只需填"股"的位置，债/金/现内置固定
- **3 层缓存**：数据（7d）→ 基准（90d）→ 策略（90d），改指标只重算不重跑
- **SOLID 架构**：Protocol 接口、依赖注入、开闭原则（添加数据源/指标不改现有代码）
- **交互式报告**：Plotly 图表，支持 hover / zoom / pan
- **中美双市场**：A 股（yfinance + akshare）和美股（yfinance）统一框架
- **三种回撤管理**：清仓 / 危机模式（砍仓防守） / 逆向模式（加仓进攻）
- **滚动窗口验证**：5~10 年窗口自动扫描，稳健性和过拟合评估

## 依赖

```
backtrader     # 回测引擎
yfinance       # 国际/ETF 行情数据
akshare        # A 股指数行情数据
pandas         # 数据处理
numpy          # 数值计算
plotly         # 交互式图表
diskcache      # 磁盘缓存
pyyaml         # YAML 配置
```

## 费率说明

| 市场 | 交易佣金 | 说明 |
|------|---------|------|
| A 股 ETF | 万2.5（0.025%） | 净佣，无印花税 |
| 美股 ETF | 0% | Fidelity/Schwab/IBKR 免佣金 |

> ETF 管理费已内含在 yfinance 价格数据中，不需要额外扣除。
> A 股组合加权管理费约 0.40%/年，美股组合约 0.21%/年。
