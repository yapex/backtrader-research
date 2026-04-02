# backtrader-research

通用自动研究框架 — 让 AI Agent 自主探索最优交易策略。

## 设计理念

Agent 改 `strategy.py` → `engine.py` 跑回测 → 记录 `results.tsv` → 改进或回退 → 永不停止。

```
engine.py      ← 固定引擎，不修改
strategy.py    ← Agent 改这个
research.yaml ← 实验配置（标的、权重、时间范围）
program.md     ← Agent 指令
results.tsv    ← 实验日志
```

## 特性

- **任意资产组合** — 2 只到 N 只 ETF，通过 research.yaml 配置
- **跨市场** — 美股（SPY/TLT）、A 股（510300.SS/511260.SS）等
- **单一指标** — score（基于夏普，惩罚大回撤，奖励超额收益）
- **Git 分支推进** — score 提升就前进，下降就 reset

## 快速开始

```bash
uv sync

# 编辑 research.yaml 配置标的，然后跑
uv run engine.py

# Agent 自主研究：指向 program.md 开始
```

## 输出示例

```
---
score:             0.607000
sharpe:            0.507000
annual_return:     0.083400
max_drawdown:      -0.240400
calmar:            0.347000
beat_benchmark:    True
excess_return:     0.000900
benchmark_return:  0.082500
benchmark_drawdown:-0.530000
---
```
