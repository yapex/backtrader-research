#!/usr/bin/env bash
# 批量跑全部 75 个 profile，输出 results.tsv
# 用法: bash sweep.sh

set -euo pipefail

RESULT_FILE="results.tsv"
LOG_DIR="logs"
mkdir -p "$LOG_DIR"

# 写表头（如果文件不存在或为空）
# Backup existing results
if [ -s "$RESULT_FILE" ]; then
    mv "$RESULT_FILE" "${RESULT_FILE%.tsv}-$(date +%Y%m%d%H%M%S).tsv"
fi

echo -e "profile\tscore\tsharpe\tdrawdown\tann_ret\tbeat\texcess" > "$RESULT_FILE"

# 从 research.yaml 提取所有 profile 名
profiles=$(python3 -c "
import yaml
with open('research.yaml') as f:
    cfg = yaml.safe_load(f)
for name in cfg.get('profiles', {}):
    print(name)
")

count=0
total=$(echo "$profiles" | wc -l | tr -d ' ')

for p in $profiles; do
    count=$((count + 1))
    printf "\r[%d/%d] %-20s" "$count" "$total" "$p"

    log="$LOG_DIR/${p}.log"
    uv run engine.py --profile "$p" > "$log" 2>&1 || true

    score=$(grep "^score:" "$log" | awk '{print $2}')
    sharpe=$(grep "^sharpe:" "$log" | awk '{print $2}')
    dd=$(grep "^max_drawdown:" "$log" | awk '{print $2}')
    ann=$(grep "^annual_return:" "$log" | awk '{print $2}')
    beat=$(grep "^beat_benchmark:" "$log" | awk '{print $2}')
    exc=$(grep "^excess_return:" "$log" | awk '{print $2}')

    if [ -n "$score" ]; then
        echo -e "${p}\t${score}\t${sharpe}\t${dd}\t${ann}\t${beat}\t${exc}" >> "$RESULT_FILE"
    else
        echo -e "${p}\tCRASH\t-\t-\t-\t-\t-" >> "$RESULT_FILE"
    fi
done

echo ""
echo ""
echo "=== TOP 10 by score ==="
sort -t$'\t' -k2 -rn "$RESULT_FILE" | head -11
