# M1: Move scripts + Atomic Helpers + export_session.sh fixes

**Status:** completed (2026-03-05)

## Deliverables
- `plugin/scripts/` — all scripts moved from `scripts/`
- `plugin/scripts/merge_settings.py` — atomic settings.json merger
- `plugin/scripts/bulk_index.sh` — batch JSONL → markdown converter (parallelized)
- `plugin/scripts/export_session.sh` — updated with 3 fixes

---

## Files Moved (content unchanged)

| From | To |
|------|-----|
| `scripts/export_session.sh` | `plugin/scripts/export_session.sh` |
| `scripts/parse_session.py` | `plugin/scripts/parse_session.py` |
| `scripts/session_to_md.py` | `plugin/scripts/session_to_md.py` |

Scripts move into `plugin/` so `${CLAUDE_PLUGIN_ROOT}/scripts/...` resolves correctly when installed via marketplace.

---

## `plugin/scripts/export_session.sh` — Three targeted changes (after move)

**1. Configurable vault dir** (currently hardcoded):
```bash
# Before:
VAULT_DIR="${HOME}/vault/sessions"

# After:
VAULT_DIR="${VAULT_DIR:-${HOME}/vault/sessions}"
```
This lets `merge_settings.py` set `VAULT_DIR` as an env var in the hook command, while preserving the default for manual usage.

**2. Fix `2>&1` stdout/stderr conflation bug**:
```bash
# Before (bug: stderr captured as OUT_PATH):
OUT_PATH="$($PYTHON "$SCRIPT_DIR/session_to_md.py" \
  --input "$TRANSCRIPT_PATH" \
  --output "$VAULT_DIR" \
  2>&1)"

# After (stderr goes to export.log, stdout captured cleanly):
OUT_PATH="$($PYTHON "$SCRIPT_DIR/session_to_md.py" \
  --input "$TRANSCRIPT_PATH" \
  --output "$VAULT_DIR" \
  2>>"$LOG_DIR/export.log")"
```

**3. Structured export.log + background git push**:
```bash
# After successful export, append structured log line:
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)  EXPORTED  $OUT_PATH" >> "$LOG_DIR/export.log"

# After skip (empty OUT_PATH):
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)  SKIPPED   trivial/duplicate  $TRANSCRIPT_PATH" >> "$LOG_DIR/export.log"

# Git push moved to background (was blocking hot path):
nohup git push --quiet 2>/dev/null &
```

---

## `plugin/scripts/merge_settings.py` — Atomic Settings Helper

CLI: `python3 merge_settings.py --hook-path /abs/path/export_session.sh [--vault-dir ~/vault/sessions] [--dry-run]`

Does three things in one atomic write:
1. Register SessionEnd hook (with `VAULT_DIR` env var set in the hook command)
2. Add qmd marketplace (`extraKnownMarketplaces.qmd`)
3. Enable qmd plugin (`enabledPlugins["qmd@qmd"]`)

Outputs JSON diff of what changed (or would change with `--dry-run`).
Non-destructive: preserves all existing keys, skips already-present entries.

```python
# Core logic
settings = load_or_default("~/.claude/settings.json")
changes = []

# 1. Hook (with vault dir as env var)
hook_cmd = f"VAULT_DIR={vault_dir} {hook_path}"
if not hook_already_registered(settings, hook_path):
    hook_entry = {"type": "command", "command": hook_cmd}
    settings.setdefault("hooks", {}).setdefault("SessionEnd", []).append({"hooks": [hook_entry]})
    changes.append(f"+ SessionEnd hook → {hook_path}")

# 2. qmd marketplace
if "qmd" not in settings.get("extraKnownMarketplaces", {}):
    settings.setdefault("extraKnownMarketplaces", {})["qmd"] = {
        "source": {"source": "github", "repo": "tobi/qmd"}
    }
    changes.append("+ extraKnownMarketplaces.qmd")

# 3. qmd plugin
if not settings.get("enabledPlugins", {}).get("qmd@qmd"):
    settings.setdefault("enabledPlugins", {})["qmd@qmd"] = True
    changes.append("+ enabledPlugins[qmd@qmd]")

if changes and not dry_run:
    write_atomic("~/.claude/settings.json", settings)

print(json.dumps({"changes": changes, "status": "ok"}))
```

`hook_already_registered` checks all entries in `hooks.SessionEnd[*].hooks[*].command` for the hook_path substring (not exact match, since env prefix varies).

Error handling:
- `mkdir -p ~/.claude` if it doesn't exist
- `try/except` around JSON parse (report "malformed settings.json" and exit 1)
- Atomic write: write to `settings.json.tmp`, then `os.rename()` to avoid partial writes

---

## `plugin/scripts/bulk_index.sh` — Atomic Bulk Indexer

CLI: `bash bulk_index.sh --vault-dir ~/vault/sessions [--dry-run]`

- Finds all `*.jsonl` in `~/.claude/projects/` (bounded: `find -maxdepth 4`)
- Delegates to `session_to_md.py` for each — all skip/idempotency logic lives there, not duplicated
- Parallelized with `xargs -P$(nproc || sysctl -n hw.ncpu || echo 4)`
- After all conversions: runs `qmd update --collection sessions` once
- Outputs progress: `[3/47] Exported openclaw_abc12345.md`
- Appends structured lines to `$VAULT_DIR/../.auto-recall-logs/export.log`

---

## Verification

1. `python3 plugin/scripts/merge_settings.py --hook-path /tmp/fake.sh --dry-run` prints JSON diff without modifying settings.json
2. `python3 plugin/scripts/merge_settings.py --hook-path /path/export_session.sh --vault-dir /tmp/test` → `~/.claude/settings.json` has hook with VAULT_DIR + qmd entries; run again → no-op (idempotent)
3. `VAULT_DIR=/tmp/test-vault bash plugin/scripts/export_session.sh` with piped JSON → markdown in /tmp/test-vault, structured line in export.log
4. `bash plugin/scripts/bulk_index.sh --vault-dir /tmp/test-vault` processes JSONLs in parallel, creates markdown files
