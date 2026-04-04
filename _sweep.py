"""Single-process sweep driver with caching.

Uses engine's 3-layer cache:
  - strategy results: keyed by (strategy.py hash, config hash)
  - benchmark results: keyed by (ticker, period, cash, commission)
  - metrics: recomputed from cached series (instant)
"""

import sys
import os
import time
from pathlib import Path

# Ensure local imports work
sys.path.insert(0, str(Path(__file__).parent))

from engine import (
    load_config,
    run_backtest,
    _get_strategy_hash,
    _execution_config_hash,
    clear_cache,
)


def main():
    # Parse args
    config_path = "research.yaml"
    clear = None
    for arg in sys.argv[1:]:
        if arg.startswith("--clear"):
            layer = arg.split("=", 1)[1] if "=" in arg else None
            clear_cache(layer)
            sys.exit(0)
        else:
            config_path = arg

    config = load_config(config_path)
    profiles = list(config.get("profiles", {}).keys())
    if not profiles:
        print("[ERROR] No profiles found")
        sys.exit(1)

    # Output paths
    base = Path(config_path).stem
    result_dir = Path("results")
    result_file = result_dir / f"{base}.tsv"
    result_dir.mkdir(exist_ok=True)

    # Header
    print(f"[sweep] config:        {config_path}")
    print(f"[sweep] profiles:      {len(profiles)}")
    print(f"[sweep] strategy_hash: {_get_strategy_hash()}")
    print()

    # Run
    t0 = time.time()
    strat_hits = 0
    strat_misses = 0
    bench_hits = 0
    bench_misses = 0
    results = []
    errors = []

    # Redirect engine cache logs to count hits/misses
    import io

    _orig_stdout = sys.stdout

    for i, name in enumerate(profiles):
        profile = config["profiles"][name]

        # Capture cache hit/miss output
        buf = io.StringIO()
        sys.stdout = buf

        try:
            m = run_backtest(config, profile)
        except Exception as e:
            sys.stdout = _orig_stdout
            errors.append((name, str(e)))
            results.append(
                {
                    "profile": name,
                    "sortino": "CRASH",
                    "irr": "-",
                    "max_drawdown": "-",
                    "total_return": "-",
                    "deposit_count": "-",
                    "beat_benchmark": "-",
                    "passed": "❌",
                }
            )
            print(f"\r[{i+1}/{len(profiles)}] {name:<20s} CRASH", flush=True)
            continue

        sys.stdout = _orig_stdout
        log = buf.getvalue()

        # Count cache events
        for line in log.splitlines():
            if "[strat:hit]" in line:
                strat_hits += 1
            elif "[strat:miss]" in line:
                strat_misses += 1
            elif "[bench:hit]" in line:
                bench_hits += 1
            elif "[bench:miss]" in line:
                bench_misses += 1

        is_dca = m.get("deposit_count", 0) > 0
        ret_val = m["irr"] if is_dca else m["annual_return"]
        passed = "✅" if m.get("passed") else "❌"
        beat = "是" if m.get("beat_benchmark") else "否"

        results.append(
            {
                "profile": name,
                "sortino": f"{m['sortino']:.6f}",
                "irr": f"{ret_val*100:+.2f}",
                "max_drawdown": f"{m['max_drawdown']*100:.2f}",
                "total_return": f"{m['total_return']*100:+.2f}",
                "deposit_count": str(m["deposit_count"]),
                "beat_benchmark": beat,
                "passed": passed,
            }
        )

        # Progress (overwrite line)
        tag = "✅" if passed == "✅" else "❌"
        print(
            f"\r[{i+1}/{len(profiles)}] {name:<20s} {tag} "
            f"sortino={results[-1]['sortino']:>10s}  irr={results[-1]['irr']:>6s}%",
            end="",
            flush=True,
        )

    sys.stdout = _orig_stdout
    elapsed = time.time() - t0

    # Write TSV
    cols = [
        "profile",
        "sortino",
        "irr",
        "max_drawdown",
        "total_return",
        "deposit_count",
        "beat_benchmark",
        "passed",
    ]
    with open(result_file, "w") as f:
        f.write("\t".join(cols) + "\n")
        for r in results:
            f.write("\t".join(r[c] for c in cols) + "\n")

    # Summary
    passed_list = [r for r in results if r["passed"] == "✅"]
    failed_list = [
        r for r in results if r["passed"] != "✅" and r["sortino"] != "CRASH"
    ]

    print()
    print()
    print(f"[done] {len(profiles)} profiles in {elapsed:.1f}s")
    print(
        f"[cache] strategy: {strat_hits} hit, {strat_misses} miss | "
        f"benchmark: {bench_hits} hit, {bench_misses} miss"
    )
    print(f"[result] {result_file}")
    print()

    if passed_list:
        print(f"=== 跑赢基准 ({len(passed_list)}/{len(results)}) ===")
        for r in sorted(passed_list, key=lambda x: float(x["sortino"]), reverse=True):
            print(
                f"  {r['profile']:<16s}  sortino={r['sortino']:>10s}  "
                f"irr={r['irr']:>7s}%  dd={r['max_drawdown']:>7s}%  "
                f"ret={r['total_return']:>7s}%"
            )

    if failed_list:
        print(f"\n=== 未跑赢基准 ({len(failed_list)}/{len(results)}) ===")
        for r in sorted(failed_list, key=lambda x: float(x["sortino"]), reverse=True):
            print(
                f"  {r['profile']:<16s}  sortino={r['sortino']:>10s}  "
                f"irr={r['irr']:>7s}%  dd={r['max_drawdown']:>7s}%  "
                f"ret={r['total_return']:>7s}%"
            )

    if errors:
        print(f"\n=== CRASH ({len(errors)}) ===")
        for name, err in errors:
            print(f"  {name}: {err}")

    # Exit 1 if nothing passed
    sys.exit(1 if not passed_list else 0)


if __name__ == "__main__":
    main()
