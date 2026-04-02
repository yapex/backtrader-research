# 交易策略自主研究

让 AI Agent 自主探索最优的资产配置策略。

## 目标

**最大化 score。越高越好。**

score 的计算方式：
- 基础分 = 夏普比率
- 最大回撤 > 30%: score -= 0.1
- 最大回撤 > 40%: score -= 0.3
- 跑赢基准: score += 0.05
- 超额收益 > 1%: score += 0.05

**核心追求**：中长期（5-10 年）超越基准标的收益，下跌时跌得少，上涨时能跟上。

## Setup

1. **约定 run tag**: 根据日期提议（如 `apr2`），分支 `research/<tag>` 不能已存在。
2. **创建分支**: `git checkout -b research/<tag>`
3. **阅读文件**:
   - `README.md` — 框架说明
   - `engine.py` — 固定引擎。**不要修改。**
   - `strategy.py` — 你修改的唯一文件。
   - `research.yaml` — 当前实验配置（标的、权重、时间范围）。
4. **验证**: 首次运行会自动下载数据并缓存。
5. **初始化 results.tsv**: 创建仅含表头的空文件。
6. **确认并开始**。

## 实验

每次实验运行 `uv run engine.py`，约 10-30 秒。

**你可以做的：**
- 修改 `strategy.py` — 策略参数、买卖逻辑、技术指标、仓位管理，一切。
- 修改 `research.yaml` — 切换标的、调整权重、改变时间范围。但每次只改一个维度，方便定位。

**你不能做的：**
- 修改 `engine.py`。
- 安装新包。

**简单性原则**: score 相近时更简单的策略更好。

## 输出格式

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

提取：`grep "^score:" run.log`

## 记录结果

`results.tsv`（制表符分隔）：

```
commit	score	sharpe	drawdown	ann_ret	status	description
```

## 实验循环

**无限循环：**

1. 查看当前 git 状态
2. 修改 `strategy.py` 或 `research.yaml`
3. git commit
4. 运行: `uv run engine.py > run.log 2>&1`
5. 读取结果: `grep "^score:" run.log`
6. 崩溃就修，修不好就跳过
7. 记录到 results.tsv
8. score 提升就保留 commit
9. score 下降就 git reset

**永不停止。** 没想法了就回顾 results.tsv，组合接近的方案，尝试更激进的改变。

## 跨市场研究

通过修改 `research.yaml` 切换市场和标的：

**美股 SPY + TLT：**
```yaml
assets:
  - ticker: SPY
    role: equity
    weight: 0.5
  - ticker: TLT
    role: bond
    weight: 0.5
benchmark: SPY
period:
  start: "2003-01-01"
  end: "2024-12-31"
```

**A 股沪深300 + 国债：**
```yaml
assets:
  - ticker: 510300.SS
    role: equity
    weight: 0.5
  - ticker: 511260.SS
    role: bond
    weight: 0.5
benchmark: 510300.SS
period:
  start: "2017-08-01"
  end: "2024-12-31"
```

**三资产组合（股+债+黄金）：**
```yaml
assets:
  - ticker: SPY
    role: equity
    weight: 0.5
  - ticker: TLT
    role: bond
    weight: 0.3
  - ticker: GLD
    role: custom
    weight: 0.2
benchmark: SPY
period:
  start: "2006-01-01"
  end: "2024-12-31"
```

注意：修改 research.yaml 后 strategy.py 可能需要相应调整（data feed 数量、权重分配等）。

## 想法方向

- 技术指标辅助（MA 交叉、RSI、MACD）
- 动态仓位（根据波动率或趋势调整权重）
- 阈值再平衡（偏差超过 X% 才调仓，减少交易）
- 多资产扩展（加入 GLD、VNQ 等）
- 波动率反向加权（波动大的配少点）
- 趋势跟随 + 股债平衡的组合
- 移动止损、时间止损、ATR 止损
- 季节性策略（如sell in May）
- 跨市场轮动
