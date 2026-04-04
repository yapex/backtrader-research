#!/usr/bin/env bash
# Sweep driver: single Python process with 3-layer caching.
#
# Usage:
#   bash sweep.sh [config.yaml]         # run sweep
#   bash sweep.sh --clear               # clear all caches
#   bash sweep.sh --clear=strategy      # clear strategy cache only
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
uv run python "$SCRIPT_DIR/_sweep.py" "$@"
