# A 股资产配置回测

帮用户回答：手上有 100 万，怎么投收益最高、回撤最小。

## 使用方法

```bash
cd /Users/yapex/workspace/backtrader-research
uv sync

# === 模板模式（推荐，无需写 YAML） ===

# 多只基金横向对比
uv run engine.py --compare 159905.SZ 510880.SS --period 2019-2025

# 股债 30/70（只填"股"，债自动用国债ETF）
uv run engine.py --stock-bond 159905.SZ 510880.SS

# 永久组合（只填"股"，债/金/现自动固定）
uv run engine.py --permanent 159905.SZ 510880.SS

# 加定投 / 换调仓频率 / 换时间窗口
uv run engine.py --stock-bond 159905.SZ --dca --rebalance quarterly --period 2019-2025

# === 传统 YAML 模式 ===
uv run engine.py --config examples/cn_permanent.yaml

# === 报告 ===
uv run python _charts.py
```

## 核心结论

### 永久组合 / 股债平衡（沪深300 作为股，2014-2025）

- 永久组合年化 +6.11%，回撤 -12.5%（沪深300 回撤 -45%）
- 一次性投入始终优于定投

### 红利 ETF 系列（2019-2025）

- 买入持有：上证红利（510880）回撤最小（-20%），接近沪深300收益
- 永久组合：所有红利 ETF 回撤降至 -5~-13%，年化 7.7~8.5%

## 已完成

- [x] 永久组合 vs 股债平衡（4 资产：股/债/金/现金）
- [x] 一次性投入 vs 定投（总资金年化回报，非 IRR）
- [x] 滚动窗口验证（3 个 10 年）
- [x] 再平衡频率对比（月/季/年）
- [x] 红利 ETF 系列对比（中证红利 / 上证红利 / 红利低波 / 红利质量）
- [x] 模板模式 CLI（--compare / --stock-bond / --permanent / --dca）
- [x] SOLID 重构（Protocol 接口、依赖注入、开闭原则）
- [x] 交互式 HTML 报告
