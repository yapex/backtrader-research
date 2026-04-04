# A 股资产配置研究

LLM 自主研究：手上有 100 万，怎么投收益最高、回撤最小。

## Setup

1. **Agree on a run tag**: propose a tag based on today's date (e.g. `apr4`). The branch `research/<tag>` must not already exist.
2. **Create the branch**: `git checkout -b research/<tag>` from current main.
3. **Read the in-scope files**:
   - `btresearch/` — 回测引擎（只读，不可修改）
   - `engine.py` — CLI 入口（只读）
   - `examples/*.yaml` — YAML 配置文件（可修改、可新建）
   - `_full_sweep.py` / `_sweep.py` — 批量扫描脚本（可修改）
   - `_charts.py` — 报告生成（可修改）
4. **Verify dependencies**: `uv sync` should complete without errors.
5. **Run a smoke test**: `uv run engine.py --config examples/cn_permanent.yaml` should produce results.
6. **Initialize results.tsv**: Create `results.tsv` with the header row. Record every experiment.

## Experimentation

**What you CAN do:**
- Create new YAML config files in `examples/` — this is your primary lever. Everything is fair game: tickers, weights, rebalance frequency, stop loss, deposit schedules, time windows, etc.
- Modify existing YAML config files.
- Use template CLI for quick experiments: `uv run engine.py --permanent 159905.SZ --period 2019-2025 --dca`
- Run batch sweeps via `_full_sweep.py` or `_sweep.py`.
- Update `_charts.py` to generate new reports when you find interesting results.
- Commit new config files, new example YAMLs, updated reports.

**What you CANNOT do:**
- Modify `btresearch/` package code. It is read-only — the engine, strategy, metrics, cache, data providers are all fixed.
- Modify `engine.py` (the CLI facade). It is also read-only.
- Install new packages or add dependencies. You can only use what's already in `pyproject.toml`.

**The goal: find the portfolio with the best risk-adjusted return.** Primary metric is **Sortino ratio** (downside-focused risk-adjusted return). Secondary metrics: annual return, max drawdown, Calmar ratio.

**Simplicity criterion**: A portfolio with fewer assets and simpler logic that achieves similar Sortino is better than a complex one. A 4-asset equal-weight portfolio beating a 10-asset optimized one? Keep the simple one.

**Each experiment runs in seconds.** There is no time budget per run — the cache makes repeated configs nearly instant. The constraint is your creativity in designing portfolio configurations.

## Output format

After each run, `engine.py` prints a summary like:

```
  sortino:             0.724512  ❌ 未跑赢基准
  年化收益:         +6.11%
  最大回撤:         -12.45%

  【vs 基准（纯买 510300.SS）】
  基准年化:         +7.98%
  基准回撤:         -45.32%
  跑赢基准:         否 ❌
  超额收益:         -1.86%
```

Extract metrics programmatically:

```bash
uv run engine.py --config examples/cn_permanent.yaml 2>&1
```

Or use template CLI:

```bash
uv run engine.py --permanent 510300.SS --period 2014-2025
```

## Logging results

Log every experiment to `results.tsv` (tab-separated).

The TSV has a header row and 7 columns:

```
commit	sortino	annual_return	max_drawdown	calmar	status	description
```

1. git commit hash (short, 7 chars)
2. sortino ratio achieved — use 0.000000 for crashes
3. annual return — use 0.000000 for crashes
4. max drawdown (as positive decimal, e.g. 0.1245 for -12.45%) — use 0.000000 for crashes
5. calmar ratio — use 0.000000 for crashes
6. status: `keep`, `discard`, or `crash`
7. short text description of what this experiment tried

Example:

```
commit	sortino	annual_return	max_drawdown	calmar	status	description
a1b2c3d	0.724512	0.0611	0.1245	0.4907	keep	baseline: permanent portfolio monthly rebalance
b2c3d4e	0.680000	0.0580	0.1100	0.5273	discard	permanent portfolio quarterly rebalance
c3d4e5f	0.000000	0.000000	0.000000	0.000000	crash	invalid ticker 999999.SS
```

## The experiment loop

The experiment runs on a dedicated branch (e.g. `research/apr4`).

LOOP FOREVER:

1. Look at the git state: the current branch/commit we're on.
2. Design an experiment: create a new YAML config or modify an existing one. Ideas include but are not limited to:
   - Different stock ETFs (红利、低波、质量、成长、创业板……）
   - Different weight splits (20/40/20/20, 15/35/25/25……）
   - Different rebalance thresholds instead of fixed frequency
   - Adding stop-loss rules (clear or crisis mode)
   - Different bond allocations (纯债、转债、信用债……）
   - Time window variations to test robustness
   - DCA with different initial percentages
   - Multi-period validation (rolling windows)
3. git commit the new/modified config.
4. Run the experiment: `uv run engine.py --config examples/<config>.yaml --json 2>/dev/null > run.log`
5. Read out the results: `grep "^sortino:\|^annual_return:\|^max_drawdown:\|^crash:" run.log`
6. If `crash: 1` appears, the run crashed. Check stderr for details, fix or skip.
7. Record the results in results.tsv (do NOT commit results.tsv).
8. If sortino improved (higher), keep the commit — you've advanced the branch.
9. If sortino is equal or worse, `git reset` back to where you started.

**Batch mode**: To test multiple configs at once:
`uv run engine.py --batch examples/a.yaml examples/b.yaml examples/c.yaml 2>/dev/null > batch.tsv`
This outputs a TSV with one row per config, crashes show as zero-metrics.

**Crashes**: If a run crashes (bad ticker, OOM, etc.), use your judgment. If it's a typo in the YAML, fix it and re-run. If the idea is fundamentally broken, skip it and move on. In --json mode, crashes output `crash: 1` and zero-metrics — just like autoresearch.

**NEVER STOP**: Once the experiment loop has begun, do NOT pause to ask the human. Do NOT ask "should I keep going?" You are autonomous. If you run out of ideas, think harder — try different asset classes, different weight schemes, different time periods, look at what worked and what didn't in results.tsv, try combining the best elements of previous experiments. The loop runs until the human interrupts you.

## Research directions (starting ideas)

- **Stock selection**: 沪深300 vs 红利ETF vs 低波ETF vs 创业板 vs 纳斯达克 vs 标普500
- **Weight optimization**: equal-weight vs risk-parity vs min-variance vs custom splits
- **Rebalance strategy**: monthly vs quarterly vs threshold-based (rebalance when deviation > 5%)
- **Asset classes**: add 商品(CTA)、REITs、海外市场、信用债
- **Risk management**: stop-loss levels, crisis-mode rebalancing (shift to conservative weights instead of clearing)
- **Time robustness**: test across multiple windows (2014-2023, 2015-2024, 2016-2025)

## Known results (baseline)

These are the baselines you should try to beat:

| Config | Sortino | Annual Return | Max Drawdown |
|--------|---------|---------------|--------------|
| 永久组合 一次性 月度再平衡 | ~0.72 | +6.11% | -12.5% |
| 股债30/70 一次性 年度再平衡 | ~0.55 | +5.17% | -16.1% |
| 沪深300 买入持有（基准） | ~0.28 | +7.98% | -45.3% |

## YAML params reference

All strategy behavior is controlled via `params:` in YAML — no code changes needed.

```yaml
params:
  rebalance_freq: monthly        # never|monthly|quarterly|yearly
  rebalance_threshold: 0.05      # null=off, 0.05=rebalance when any asset deviates >5%
  stop_loss: null                 # null=off, 0.15=trigger at -15% drawdown
  stop_loss_mode: clear           # clear=清仓, crisis=切换到 crisis_weights
  crisis_weights:                 # only used when stop_loss_mode=crisis
    510300.SS: 0.10               #   股票降到 10%
    511010.SS: 0.50               #   债券升到 50%
    518880.SS: 0.20               #   黄金维持 20%
    511990.SS: 0.20               #   现金维持 20%
```
