#!/bin/bash
# export_session.sh — SessionEnd hook for auto-recall-cc
#
# Reads SessionEnd hook JSON from stdin, converts the session JSONL to
# markdown, copies it to ~/vault/sessions/, and updates the QMD index.
#
# Hook JSON schema (Claude Code SessionEnd):
#   { "transcript_path": "...", "session_id": "...", "cwd": "..." }

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_DIR="${HOME}/vault/sessions"
PYTHON="${PYTHON:-python3}"
QMD="${QMD:-qmd}"

# Read stdin into a variable
HOOK_JSON="$(cat)"

if [[ -z "$HOOK_JSON" ]]; then
  echo "[auto-recall] No hook JSON received — skipping" >&2
  exit 0
fi

# Log raw payload on first run so we can verify field names
LOG_DIR="${HOME}/vault/.auto-recall-logs"
mkdir -p "$LOG_DIR"
echo "$HOOK_JSON" >> "$LOG_DIR/hook-payloads.jsonl"

# Extract transcript_path from JSON (portable, no jq dependency)
TRANSCRIPT_PATH="$($PYTHON -c "import sys, json; d=json.loads(sys.argv[1]); print(d.get('transcript_path',''))" "$HOOK_JSON" 2>/dev/null || true)"

if [[ -z "$TRANSCRIPT_PATH" || ! -f "$TRANSCRIPT_PATH" ]]; then
  echo "[auto-recall] transcript_path not found or file missing: ${TRANSCRIPT_PATH:-<empty>}" >&2
  exit 0
fi

echo "[auto-recall] Exporting session: $TRANSCRIPT_PATH" >&2

# Ensure vault directory exists
mkdir -p "$VAULT_DIR"

# Convert JSONL → markdown, write to vault
OUT_PATH="$($PYTHON "$SCRIPT_DIR/session_to_md.py" \
  --input "$TRANSCRIPT_PATH" \
  --output "$VAULT_DIR" \
  2>&1)"

EXIT_CODE=$?
if [[ $EXIT_CODE -ne 0 ]]; then
  echo "[auto-recall] session_to_md.py failed: $OUT_PATH" >&2
  exit 0  # Don't block session close on export failure
fi

if [[ -z "$OUT_PATH" ]]; then
  # Skipped (trivial session or already exported)
  exit 0
fi

echo "[auto-recall] Exported: $OUT_PATH" >&2

# Update QMD index (sync, fast ~100ms)
if command -v "$QMD" &>/dev/null; then
  "$QMD" update --collection sessions 2>/dev/null || "$QMD" update 2>/dev/null || true
  echo "[auto-recall] QMD index updated" >&2
else
  echo "[auto-recall] qmd not found, skipping index update" >&2
fi

# Git sync (if vault is a git repo)
if [[ -d "${HOME}/vault/.git" ]]; then
  cd "${HOME}/vault"
  git add sessions/ 2>/dev/null || true
  SESSION_DATE="$(date +%Y-%m-%d)"
  PROJECT="$(basename "$(dirname "$TRANSCRIPT_PATH")" | sed 's/-Users-dvq-frostmourne-//' | sed 's/-Users-dvq-//')"
  git commit -m "session: ${PROJECT} ${SESSION_DATE}" --quiet 2>/dev/null || true
  git push --quiet 2>/dev/null || true
  echo "[auto-recall] Git push complete" >&2
fi

echo "[auto-recall] Done" >&2
