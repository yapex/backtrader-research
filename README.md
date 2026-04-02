# backtrader-research

帮普通用户找最优资产配置的回测框架。

## 核心问题

> 选好 ETF 和债券后，**按什么比例、多久调一次、要不要止损**，收益最高、回撤最小？

## 使用

```bash
uv sync

# 用默认配置跑（美股股债平衡）
uv run engine.py

# 跑特定 profile
uv run engine.py --profile 6040_Q_none

# 跑 example 配置
uv run engine.py --config examples/cn_dividend.yaml

# 批量穷举所有 profile
bash sweep.sh
```

## 策略

面向普通用户，简单到可以手动执行：
1. 按比例买入
2. 定期再平衡（月/季/年）
3. 可选：组合从高点回撤超过阈值就全清仓

## Example 配置

| 文件 | 市场 | 标的 |
|------|------|------|
| `examples/us_stockbond.yaml` | 美股 | SPY + TLT |
| `examples/us_permanent.yaml` | 美股 | SPY + TLT + GLD + MINT |
| `examples/cn_stockbond.yaml` | A 股 | 沪深300 + 国债 |
| `examples/cn_permanent.yaml` | A 股 | 沪深300 + 国债 + 黄金 |
| `examples/cn_dividend.yaml` | A 股 | 红利ETF + 国债 |

## 项目结构

| 文件 | 说明 |
|------|------|
| `engine.py` | 回测引擎（固定，不可修改） |
| `strategy.py` | 策略实现（配置驱动） |
| `research.yaml` | 默认实验配置 |
| `program.md` | 研究指引 |
| `team.md` | ClawTeam 多 Agent 并行指引 |
| `sweep.sh` | 批量穷举脚本 |
| `summary.md` | 回测结果汇总 |
| `examples/` | 各市场示例配置 |
| `results/` | 实验结果数据 |
