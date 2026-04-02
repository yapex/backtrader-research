# 团队协作指引 — ClawTeam + pi + tmux

用 AI Agent 探索回测组合。**最多 4 个 Worker**，避免 LLM 限速。

## 前置条件

- `clawteam` 已安装: `pip install clawteam`
- `tmux` 已安装
- 在 git 仓库根目录执行

## 两种模式

### 模式一：本地批量跑（推荐，不需要 LLM）

75 个组合是固定搜索空间，直接用脚本跑完：

```bash
bash sweep.sh          # 跑全部 75 个，结果写入 results.tsv
```

跑完看排名：
```bash
sort -t$'\t' -k2 -rn results.tsv | head -20
```

### 模式二：ClawTeam Agent 探索（用于超出 75 组合的扩展）

当基础搜索跑完后，需要 Agent 探索新方向时使用。

**最多 spawn 4 个 Worker。**

```bash
export CLAWTEAM_AGENT_ID="leader-001"
export CLAWTEAM_AGENT_NAME="leader"
export CLAWTEAM_AGENT_TYPE="leader"

clawteam team spawn-team backtrader-research \
  -d "Trading strategy research" -n leader

# 按方向分任务，最多 4 个 Worker
clawteam task create backtrader-research \
  "探索 A 股配置（510300.SS + 511260.SS）" \
  -o w-cn -d "修改 research.yaml 的 assets 和 period，跑 5比例×3频率×5止损=75组。"

clawteam task create backtrader-research \
  "探索三资产组合（SPY+TLT+GLD）" \
  -o w-3asset -d "添加 GLD，调整权重和 strategy.py 支持 3 个 data feed。跑主要组合。"

clawteam task create backtrader-research \
  "探索更细粒度的比例（55/45, 65/35）" \
  -o w-fine -d "在基础搜索结果附近做精细搜索。"

clawteam task create backtrader-research \
  "分析结果写报告" \
  -o w-report -d "汇总所有 results.tsv，分析规律，写最终推荐。"

# Spawn（最多 4 个）
for name in w-cn w-3asset w-fine w-report; do
  clawteam spawn tmux pi \
    --team backtrader-research \
    --agent-name "$name" \
    --agent-type researcher \
    --task "Read program.md. 完成你的任务。用 uv run engine.py --profile <name> > run.log 2>&1 跑回测。记录 results.tsv。"
done

# 监控
clawteam board live backtrader-research --interval 5
```

## 关闭团队

```bash
for name in w-cn w-3asset w-fine w-report; do
  clawteam lifecycle request-shutdown backtrader-research leader "$name" 2>/dev/null
done
clawteam team cleanup backtrader-research --force
```
