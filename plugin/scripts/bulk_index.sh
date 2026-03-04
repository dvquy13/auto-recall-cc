#!/bin/bash
# bulk_index.sh — Batch JSONL → markdown converter for auto-recall-cc.
#
# Scans ~/.claude/projects/ for all *.jsonl session files, converts each to
# markdown via session_to_md.py (idempotent), then re-indexes QMD once.
#
# CLI: bash bulk_index.sh --vault-dir ~/vault/sessions [--dry-run]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"
QMD="${QMD:-qmd}"
VAULT_DIR="${HOME}/vault/sessions"
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --vault-dir) VAULT_DIR="$2"; shift 2 ;;
    --dry-run)   DRY_RUN=1; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

VAULT_DIR="${VAULT_DIR/#\~/$HOME}"
LOG_DIR="$(dirname "$VAULT_DIR")/.auto-recall-logs"
mkdir -p "$LOG_DIR"

# Discover all JSONL files (bounded depth to avoid runaway traversal)
JSONL_FILES=$(find "${HOME}/.claude/projects" -maxdepth 4 -name '*.jsonl' 2>/dev/null || true)

if [[ -z "$JSONL_FILES" ]]; then
  echo "No JSONL files found in ~/.claude/projects/" >&2
  exit 0
fi

TOTAL=$(echo "$JSONL_FILES" | wc -l | tr -d ' ')
echo "Found $TOTAL session file(s) to process" >&2

if [[ $DRY_RUN -eq 1 ]]; then
  echo "[dry-run] Would process $TOTAL files into $VAULT_DIR" >&2
  exit 0
fi

mkdir -p "$VAULT_DIR"

# Counter for progress (written to shared temp file, then read)
COUNTER_FILE=$(mktemp)
echo 0 > "$COUNTER_FILE"

# Worker function: convert one JSONL file
process_one() {
  local jsonl="$1"
  local vault_dir="$2"
  local log_dir="$3"
  local python="$4"
  local script_dir="$5"
  local total="$6"
  local counter_file="$7"

  OUT_PATH=$("$python" "$script_dir/session_to_md.py" \
    --input "$jsonl" \
    --output "$vault_dir" \
    2>>"$log_dir/export.log") || true

  # Increment counter (best-effort, may have minor races but display only)
  COUNT=$(cat "$counter_file" 2>/dev/null || echo 0)
  COUNT=$((COUNT + 1))
  echo "$COUNT" > "$counter_file"

  if [[ -n "$OUT_PATH" ]]; then
    FNAME=$(basename "$OUT_PATH")
    echo "[$COUNT/$total] Exported $FNAME" >&2
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)  EXPORTED  $OUT_PATH" >> "$log_dir/export.log"
  else
    echo "[$COUNT/$total] Skipped $(basename "$jsonl")" >&2
  fi
}

export -f process_one

# Parallelized conversion
NCPU=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
echo "$JSONL_FILES" | xargs -P"$NCPU" -I{} bash -c \
  'process_one "$@"' _ {} "$VAULT_DIR" "$LOG_DIR" "$PYTHON" "$SCRIPT_DIR" "$TOTAL" "$COUNTER_FILE"

rm -f "$COUNTER_FILE"

EXPORTED=$(grep -c "EXPORTED" "$LOG_DIR/export.log" 2>/dev/null || echo 0)
echo "Done. $EXPORTED file(s) exported to $VAULT_DIR" >&2

# Re-index QMD once after all conversions
if command -v "$QMD" &>/dev/null; then
  echo "Updating QMD index..." >&2
  "$QMD" update --collection sessions 2>/dev/null || "$QMD" update 2>/dev/null || true
  echo "QMD index updated." >&2
else
  echo "qmd not found — skipping index update" >&2
fi
