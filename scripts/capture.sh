#!/usr/bin/env bash
# Manual capture (local/dev use; automated capture runs in GitHub Actions:
# .github/workflows/jobspy_capture.yml every 30 min, .github/workflows/spe_12h.yml
# every 12h — both push to Hugging Face).
#
# Usage: ./scripts/capture.sh [jobspy|spe|all]   (default: all)
#
# - Restores the published corpus from Hugging Face first (without that step
#   there is no accumulation: persistent memory lives on HF, not on disk).
# - jobspy: general search on the active boards -> data/store/jobspy.parquet.
# - spe: official full export -> data/store/spe.parquet.
# - Emits data/spe/ + data/jobspy/ and uploads them.
set -euo pipefail

cd "$(dirname "$0")/.."
PY=.venv/bin/python
WHAT="${1:-all}"

case "$WHAT" in
  jobspy|spe|all) ;;
  *) echo "usage: $0 [jobspy|spe|all]" >&2; exit 2 ;;
esac

echo "[$(date '+%Y-%m-%d %H:%M:%S')] pulling published corpus ($WHAT)..."
"$PY" -m pipeline pull --dataset "$WHAT"

if [ "$WHAT" != "spe" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] capturing jobspy boards..."
  "$PY" -m pipeline capture --source jobspy --results 100
fi

if [ "$WHAT" != "jobspy" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] capturing SPE export..."
  "$PY" -m pipeline capture --source spe
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] emitting and uploading ($WHAT)..."
"$PY" -m pipeline emit --dataset "$WHAT" --upload

echo "[$(date '+%Y-%m-%d %H:%M:%S')] done."
