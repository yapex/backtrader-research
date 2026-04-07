# A 股资产配置研究

LLM 自主研究：手上有 100 万，怎么投收益最高、回撤最小。

## Setup

1. **Agree on a run tag**: propose a tag based on today's date (e.g. `apr5`). The branch `research/<tag>` must not already exist.
2. **Create the branch**: `git checkout -b research/<tag>` from current main.
3. **Read the in-scope files**:
   - `btresearch/` — 回测引擎（只读，不可修改）
   - `engine.py` — CLI 入口（只读）
   - `examples/*.yaml` — YAML 配置文件（可修改、可新建）
   - `validate.py` — 交叉验证工具（只读）
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
- Run cross-window validation: `uv run python validate.py examples/cn_perm_best.yaml`
- Update `_charts.py` to generate new reports when you find interesting results.
- Commit new config files, new example YAMLs, updated reports.

**What you CANNOT do:**
- Modify `btresearch/` package code. It is read-only — the engine, strategy, metrics, cache, data providers are all fixed.
- Modify `engine.py` (the CLI facade). It is also read-only.
- Modify `validate.py`. It is also read-only.
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
uv run engine.py --config examples/cn_permanent.yaml --json 2>/dev/null
```

Or use template CLI:

```bash
uv run engine.py --permanent 510300.SS --period 2014-2025 --json 2>/dev/null
```

## Logging results

Log every experiment to `results.tsv` (tab-separated).

The TSV has a header row and 9 columns:

```
commit	sortino	annual_return	max_drawdown	calmar	robustness	overfit_score	status	description
```

1. git commit hash (short, 7 chars)
2. sortino ratio achieved — use 0.000000 for crashes
3. annual return — use 0.000000 for crashes
4. max drawdown (as positive decimal, e.g. 0.1245 for -12.45%) — use 0.000000 for crashes
5. calmar ratio — use 0.000000 for crashes
6. robustness: min_window_sortino / mean_window_sortino across 6 validation windows — use 0.000000 if validation not run
7. overfit_score: train_sortino / mean_validation_sortino — use 0.000000 if validation not run
8. status: `keep`, `discard`, `crash`, or `dca_skip`
9. short text description of what this experiment tried

Example:

```
commit	sortino	annual_return	max_drawdown	calmar	robustness	overfit_score	status	description
a1b2c3d	0.724512	0.0611	0.1245	0.4907	0.720000	1.100000	keep	baseline: permanent portfolio monthly rebalance
b2c3d4e	0.680000	0.0580	0.1100	0.5273	0.650000	1.400000	discard	permanent portfolio quarterly rebalance (overfit risk)
```

## Cross-Window Validation (MANDATORY)

**Every keep candidate MUST be validated across multiple time windows before keeping.**

Run validation after each promising experiment:
```bash
uv run python validate.py examples/<config>.yaml --train-sortino <sortino> --tsv
```

This sweeps 5, 7, and 10-year rolling windows (step=6mo, ~25 windows total) and computes:
- **robustness** = min(sortino across windows) / mean(sortino across windows)
  - > 40% = ✅ robust (A-share reality: 40-50% is the practical ceiling)
  - 30-40% = 🟡 acceptable
  - < 30% = 🔴 fragile (strategy only works in specific periods)
- **overfit_score** = training_sortino / mean(validation_sortino)
  - < 1.5 = ✅ no overfitting
  - 1.5-2.0 = 🟡 likely overfit
  - > 2.0 = 🔴 definitely overfit
- **pass_rate** = % of windows where Sortino > 0.28 (沪深300 baseline)
  - > 80% = ✅ consistently beats baseline
  - < 50% = 🔴 unreliable

**Validation gate**: A config must have `overfit_score < 2.0` AND `robustness > 0.30` AND `pass_rate > 0.50` to be kept.

These thresholds are calibrated from retroactive validation of all existing configs.
No existing config passes all three — this is the starting point for improvement.

## The experiment loop

The experiment runs on a dedicated branch (e.g. `research/apr5`).

LOOP FOREVER:

1. Look at the git state: the current branch/commit we're on.
2. **Analyze previous results**: Read `results.tsv`. For discarded experiments, identify WHY they failed. Group failures by root cause:
   - Parametric sensitivity (small change → big result swing)
   - Time-period dependency (works only in bull/bear market)
   - Diminishing returns (similar configs, similar scores)
   - Crash (bad ticker, invalid config)
3. Design an experiment based on failure analysis. Ideas include but are not limited to:
   - Different stock ETFs (红利、低波、质量、成长、创业板……）
   - Different weight splits (20/40/20/20, 15/35/25/25……）
   - Different rebalance thresholds instead of fixed frequency
   - Adding stop-loss rules (clear or crisis mode)
   - Different bond allocations (纯债、转债、信用债……）
   - Time window variations to test robustness
   - DCA with different initial percentages
   - Multi-period validation (rolling windows)
   - Contrarian mode (跌→加仓) or profit-take (涨→减仓)
4. git commit the new/modified config.
5. Run the experiment: `uv run engine.py --config examples/<config>.yaml --json 2>/dev/null > run.log`
6. Read out the results: `grep "^sortino:\|^annual_return:\|^max_drawdown:\|^crash:" run.log`
7. If `crash: 1` appears, the run crashed. Check stderr for details, fix or skip.
8. **If sortino improved**, run cross-window validation:
   ```bash
   uv run python validate.py examples/<config>.yaml --train-sortino <sortino> --tsv > validation.log
   ```
9. Check validation results. Record `robustness` and `overfit_score` in results.tsv.
10. **Keep/Discard rules** (apply ALL three):
    - sortino must be higher than current best → keep
    - overfit_score must be < 2.0 → keep
    - robustness must be > 0.50 → keep
    - If any condition fails → discard
11. If keeping, commit. If discarding, `git reset` back.

**Batch mode**: To test multiple configs at once:
`uv run engine.py --batch examples/a.yaml examples/b.yaml examples/c.yaml 2>/dev/null > batch.tsv`
This outputs a TSV with one row per config, crashes show as zero-metrics.

**Crashes**: If a run crashes (bad ticker, OOM, etc.), use your judgment. If it's a typo in the YAML, fix it and re-run. If the idea is fundamentally broken, skip it and move on. In --json mode, crashes output `crash: 1` and zero-metrics — just like autoresearch.

## Failure Analysis

When diagnosing discarded experiments, categorize the failure:

| Failure type | Pattern | What to try |
|---|---|---|
| **Parametric cliff** | threshold 7% → Sortino 0.81, threshold 8% → 0.67 | The parameter space has sharp cliffs. Sweep finer around promising regions. |
| **Diminishing returns** | configs differ only slightly, scores cluster | You've exhausted this dimension. Try a completely different axis (new asset class, new logic). |
| **Time-period fragility** | high Sortino on 2014-2025 but fails on 2018-2023 | Strategy is overfitting to a specific market regime. Add robustness requirements. |
| **No effect** | adding a feature doesn't change the score | The feature doesn't apply in this market. Try a different feature or different market. |
| **Crash** | error in execution | Fix the config or skip. |

**Rule**: Prefer changes that fix a CLASS of failures, not a single experiment.

## Overfitting Rule

Do NOT add configuration that only works for a specific market regime.

Use this test: "If the 2015-2016 bear market and the 2020 COVID crash disappeared, would this still be a worthwhile improvement?"

If the answer is no, it is probably overfitting to a specific crisis period.

**Specifically**: Crisis-mode weights that are optimized for a single drawdown event (e.g., exactly the 2015 crash) are likely overfit. The cross-window validation gate catches this.

## Anti-Patterns (what NOT to do)

1. **Tuning crisis_weights to match one crash**: This is the most common overfitting trap. The 2015 crash, 2018 correction, and 2020 COVID crash had very different characteristics.
2. **Adding more assets to chase marginal Sortino gains**: Going from 4 to 6 assets for +0.02 Sortino is usually not worth the complexity.
3. **Trying every ETF in existence**: Focus on understanding WHY a particular asset class helps (risk diversification? inflation hedge? low correlation?).
4. **Ignoring the simplicity criterion**: If two configs have similar Sortino, the simpler one wins. Always.
5. **Contrarian mode (跌→加仓)**: Already tested extensively (54 A-share + 72 US sweeps). Failed in both markets. Threshold rebalance already implements "buy the dip" automatically.
6. **One-size-fits-all thresholds**: A-share optimal threshold is 7%, US is 10%. Do not assume parameters transfer across markets.

## NEVER STOP

Once the experiment loop has begun, do NOT pause to ask the human. Do NOT ask "should I keep going?" You are autonomous. If you run out of ideas, think harder — try different asset classes, different weight schemes, different time periods, look at what worked and what didn't in results.tsv, try combining the best elements of previous experiments. The loop runs until the human interrupts you.

## Research directions (starting ideas)

- **Stock selection**: 沪深300 vs 红利ETF vs 低波ETF vs 创业板 vs 纳斯达克 vs 标普500
- **Weight optimization**: equal-weight vs risk-parity vs min-variance vs custom splits
- **Rebalance strategy**: monthly vs quarterly vs threshold-based (rebalance when deviation > 5%)
- **Asset classes**: add 商品(CTA)、REITs、海外市场、信用债
- **Risk management**: stop-loss levels, crisis-mode rebalancing (shift to conservative weights instead of clearing)
- **Time robustness**: test across multiple windows (2014-2023, 2015-2024, 2016-2025)
- **Contrarian strategies**: buy the dip instead of selling (别人恐惧我贪婪)
- **Profit-taking**: reduce equity allocation after strong recoveries (别人贪婪我恐惧)
- **Fee sensitivity**: test impact of commission rates (A-stock ETF: 万2.5 vs 万10)
- **US market**: QQQ vs SPY, different equity weights (30% vs 40% vs 50%)

## YAML params reference

All strategy behavior is controlled via `params:` in YAML — no code changes needed.

```yaml
params:
  rebalance_freq: monthly        # never|monthly|quarterly|yearly
  rebalance_threshold: 0.05      # null=off, 0.05=rebalance when any asset deviates >5%
  stop_loss: null                 # null=off, 0.15=trigger at -15% drawdown
  stop_loss_mode: clear           # clear|crisis|contrarian
  crisis_weights:                 # target weights when crisis/contrarian triggers
    510300.SS: 0.10               #   (crisis=defensive, contrarian=aggressive)
    511010.SS: 0.50               #
    518880.SS: 0.20               #
    511990.SS: 0.20               #
  recovery_threshold: 0.05       # contrarian: exit when drawdown < 5%
  profit_take: 0.10               # contrarian: profit-take when gain from trough > 10%
  profit_take_weights: {...}      # weights during profit-take (reduce equity)
```

### stop_loss_mode 详解

| 模式 | 触发条件 | 行为 | 恢复逻辑 |
|------|---------|------|---------|
| `clear` | dd < -stop_loss | 清仓所有资产 | 永久清仓 |
| `crisis` | dd < -stop_loss | 切到 crisis_weights | 永久切换（不恢复） |
| `contrarian` | dd < -stop_loss | 切到 crisis_weights（进攻） | dd > -recovery_threshold → 恢复原仓位；或反弹 > profit_take → 进入止盈 |

### commission（顶层配置）

```yaml
commission: 0.00025  # A 股 ETF 万2.5（默认 CNY=万10，USD=0）
```

## Fee reference

| Market | Trading commission | Notes |
|--------|-------------------|-------|
| A-share ETF | 0.025% (万2.5) | Net commission, no stamp duty |
| US ETF | 0% | Fidelity/Schwab/IBKR zero commission |
| Default (config.py) | CNY: 0.10% (万10), USD: 0% | Override via `commission:` in YAML |

ETF management fees are embedded in yfinance price data — no additional deduction needed.
