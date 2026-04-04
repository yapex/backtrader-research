# A 股永久组合回测

帮用户回答：手上有 100 万，怎么投收益最高、回撤最小。

## 核心结论

永久组合（沪深300 + 国债 + 黄金 + 货币基金，各 25%）月度再平衡，一次性投入。

## 使用方法

```bash
cd /Users/yapex/workspace/backtrader-research
uv sync

# 跑单个配置
uv run engine.py --config examples/cn_permanent.yaml

# 生成报告（HTML + MD + 图表）
uv run python _charts.py
```

## 已完成

- [x] 永久组合 vs 股债平衡（4 资产：股/债/金/现金）
- [x] 一次性投入 vs 定投（总资金年化回报，非 IRR）
- [x] 滚动窗口验证（3 个 10 年）
- [x] 再平衡频率对比（月/季/年）
- [x] 交互式 HTML 报告
