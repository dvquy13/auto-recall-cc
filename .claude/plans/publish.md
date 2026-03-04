# Plan: Setup Skill + Plugin Structure for auto-recall-cc

## Context
The project auto-exports Claude Code sessions to a searchable markdown vault. Currently, setup requires manual steps: clone repo, edit ~/.claude/settings.json, create vault dir, configure QMD collection.

Goal: Ship as a Claude plugin with an onboarding wizard skill. Claude handles all UX conversationally and calls atomic helper scripts directly.

## Installation Flow

```
1. User installs plugin:
     claude marketplace add dvq/auto-recall-cc

2. User starts a new Claude Code session

3. User invokes: /auto-recall-cc:setup
   → Claude runs the onboarding wizard conversationally
   → Claude calls atomic helper scripts via Bash tool

4. After setup, future sessions auto-export on close
```

---

## Architecture: Two-Tier Plugin + Atomic Helpers

Follows knowhub's pattern: root marketplace catalog → `plugin/` subdirectory with manifest + skills + scripts. Non-plugin files (tests, docs) stay at repo root.

```
.claude-plugin/
└── marketplace.json           ← marketplace catalog (source: "./plugin")

plugin/
├── .claude-plugin/
│   └── plugin.json            ← plugin manifest (name, version, skills)
├── skills/
│   └── setup/
│       └── SKILL.md           ← Claude-driven onboarding wizard
└── scripts/
    ├── merge_settings.py      ← atomic: modifies ~/.claude/settings.json
    ├── bulk_index.sh          ← atomic: scan ~/.claude/projects/ and export JSONLs
    ├── export_session.sh      ← modified: configurable vault dir, structured logging, background git push
    ├── parse_session.py       ← unchanged (moved from scripts/)
    └── session_to_md.py       ← unchanged (moved from scripts/)

# Non-plugin files stay at root:
tests/
docs/
README.md
```

Scripts move from `scripts/` → `plugin/scripts/` so `${CLAUDE_PLUGIN_ROOT}/scripts/...` resolves correctly when installed via marketplace. `CLAUDE_PLUGIN_ROOT` points to the `plugin/` directory.

---

## What Gets Built

### 1. `scripts/merge_settings.py` — Atomic Settings Helper

CLI: `python3 merge_settings.py --hook-path /abs/path/export_session.sh [--vault-dir ~/vault/sessions] [--dry-run]`

Does three things in one atomic write:
1. Register SessionEnd hook (with `VAULT_DIR` env var set in the hook command)
2. Add qmd marketplace (`extraKnownMarketplaces.qmd`)
3. Enable qmd plugin (`enabledPlugins["qmd@qmd"]`)

Outputs JSON diff of what changed (or would change with `--dry-run`).
Non-destructive: preserves all existing keys, skips already-present entries.

Error handling:
- `mkdir -p ~/.claude` if it doesn't exist
- `try/except` around JSON parse (report "malformed settings.json" and exit 1)
- Atomic write: write to `settings.json.tmp`, then `os.rename()` to avoid partial writes

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

### 2. `scripts/bulk_index.sh` — Atomic Bulk Indexer

CLI: `bash bulk_index.sh --vault-dir ~/vault/sessions [--dry-run]`

- Finds all `*.jsonl` in `~/.claude/projects/` (bounded: `find -maxdepth 4`)
- Delegates to `session_to_md.py` for each — all skip/idempotency logic lives there, not duplicated
- Parallelized with `xargs -P$(nproc || sysctl -n hw.ncpu || echo 4)`
- After all conversions: runs `qmd update --collection sessions` once
- Outputs progress: `[3/47] Exported openclaw_abc12345.md`
- Appends structured lines to `$VAULT_DIR/../.auto-recall-logs/export.log`

### 3. `plugin/skills/setup/SKILL.md` — Setup Wizard Skill

Claude follows this script when user invokes `/auto-recall-cc:setup`:

**Phase 1: Recon (read-only Bash calls, no user prompts yet)**
```bash
# All probes in one block
python3 --version 2>&1 || echo "MISSING"
command -v qmd && qmd --version || echo "QMD_MISSING"
for cmd in bun npm npx; do command -v $cmd &>/dev/null && echo "installer=$cmd" && break; done || echo "installer=none"
find ~/.claude/projects -maxdepth 4 -name '*.jsonl' 2>/dev/null | wc -l
```

Report findings conversationally:
- "python3 3.9.6 — ready"
- "qmd not installed — I'll install it"
- "Found 47 existing sessions to import"

**Hard stops** — if python3 is missing, stop and tell user to install it. If no package manager (bun/npm/npx), stop and explain qmd requires one.

**Phase 2: Gather preferences (conversation)**
- Vault dir? (default: `~/vault/sessions`, auto-detect if `~/vault/` exists)

**Phase 3: Preview — show user-friendly plan before acting**
```
Here's what I'll do:
  [1] Create vault directory: ~/vault/sessions
  [2] Register auto-export hook (runs on every session close)
  [3] Enable QMD search plugin (semantic search over your sessions)
  [4] Install qmd CLI via bun (auto-detected)
  [5] Register QMD collection "sessions"
  [6] (after) offer to bulk-import 47 existing sessions
  [7] (after) offer git vault sync

Shall I proceed?
```

No internal key names (`extraKnownMarketplaces`, `enabledPlugins`) — just describe what each step does in plain English. Use `merge_settings.py --dry-run` output internally to verify, but show the user-friendly version.

**Phase 4: Execute**
1. `mkdir -p $VAULT_DIR`
2. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/merge_settings.py --hook-path ${CLAUDE_PLUGIN_ROOT}/scripts/export_session.sh --vault-dir $VAULT_DIR`
3. `command -v qmd &>/dev/null || bun install -g @tobilu/qmd` (execution-time guard, not based on recon memory)
4. `qmd collection add $VAULT_DIR --name sessions`

Note: `qmd pull` is NOT run during setup. Models (~2GB total) auto-download on first use of `qmd embed` or `qmd query`. The SessionEnd hook already runs `qmd embed` in background, which triggers the embedding model download (~300MB) on first session close. The reranker (~640MB) and query expansion (~1.1GB) models download lazily on first `qmd query`. This avoids blocking setup with a 2GB download.

**Phase 5: Post-setup options (conversational)**
- Bulk-import: `bash ${CLAUDE_PLUGIN_ROOT}/scripts/bulk_index.sh --vault-dir $VAULT_DIR`
- Git sync: ask for remote URL, run `git init && git remote add origin URL && git push`

**Phase 6: Done — show verification commands**
```
Setup complete! Here's how to verify:

# Check recent exports
tail -20 ~/vault/.auto-recall-logs/export.log

# View hook invocations
tail -5 ~/vault/.auto-recall-logs/hook-payloads.jsonl | python3 -m json.tool

# Count today's exports
grep $(date +%Y-%m-%d) ~/vault/.auto-recall-logs/export.log | grep EXPORTED | wc -l

# Search your sessions
qmd search "what I worked on yesterday"

For full docs, see: https://github.com/dvq/auto-recall-cc#readme
```

### 4. Plugin Structure

Two-tier layout following knowhub's pattern (confirmed working). Root marketplace catalog points to `plugin/` subdirectory where the actual plugin manifest lives.

```
.claude-plugin/
└── marketplace.json           # marketplace catalog → source: "./plugin"

plugin/
├── .claude-plugin/
│   └── plugin.json            # plugin manifest
├── skills/
│   └── setup/
│       └── SKILL.md
└── scripts/
    └── ...
```

**`.claude-plugin/marketplace.json`** (marketplace catalog, repo root):
```json
{
  "name": "auto-recall-cc",
  "owner": {
    "name": "dvq"
  },
  "plugins": [
    {
      "name": "auto-recall-cc",
      "source": "./plugin",
      "description": "Auto-export Claude Code sessions to a searchable markdown vault",
      "version": "0.1.0",
      "author": { "name": "dvq" },
      "repository": "https://github.com/dvq/auto-recall-cc",
      "license": "MIT",
      "keywords": ["sessions", "memory", "recall", "qmd"]
    }
  ]
}
```

**`plugin/.claude-plugin/plugin.json`** (plugin manifest):
```json
{
  "name": "auto-recall-cc",
  "version": "0.1.0",
  "description": "Auto-export Claude Code sessions to a searchable markdown vault",
  "skills": [
    "./skills/setup"
  ]
}
```

Why two-tier (not qmd's single-file pattern):
- qmd IS a marketplace (its repo root IS the plugin). auto-recall-cc is a plugin that self-hosts its marketplace.
- knowhub uses this exact pattern and it works: `marketplace.json` → `source: "./plugin"` → `plugin/.claude-plugin/plugin.json`
- Keeps non-plugin files (tests/, docs/, .claude/) out of the installed plugin
- `CLAUDE_PLUGIN_ROOT` resolves to `<install_dir>/plugin/`, so `${CLAUDE_PLUGIN_ROOT}/scripts/export_session.sh` works

### 5. `README.md` — User-Facing Documentation

Top-level README for end users. Covers:

```markdown
# auto-recall-cc

Auto-export Claude Code sessions to a searchable markdown vault.

## What it does
Every time a Claude Code session ends, auto-recall-cc converts the raw JSONL
transcript to clean markdown and indexes it with QMD for instant search.

## Quick start
1. Install: `claude marketplace add dvq/auto-recall-cc`
2. Run: `/auto-recall-cc:setup` in any Claude Code session
3. Done — future sessions auto-export on close

## How it works
- **SessionEnd hook** converts JSONL → markdown → vault directory
- **QMD** indexes the vault for keyword search, semantic search, and hybrid search
- **Git sync** (optional) pushes vault to a remote for backup

## Pipeline
Session JSONL → parse_session.py → session_to_md.py → ~/vault/sessions/ → qmd update → qmd embed

## Prerequisites
- python3 (3.9+)
- bun, npm, or npx (for qmd installation)

## Configuration
| Setting | Default | Description |
|---------|---------|-------------|
| Vault dir | `~/vault/sessions` | Where markdown files are written |
| QMD collection | `sessions` | Name of the QMD search collection |

## Logs & Troubleshooting
Logs are written to `~/vault/.auto-recall-logs/`:

| File | Contents |
|------|----------|
| `export.log` | Timestamped results: EXPORTED, SKIPPED, ERROR |
| `hook-payloads.jsonl` | Raw SessionEnd hook invocations |
| `embed.log` | QMD embedding progress |

### Common commands
  tail -20 ~/vault/.auto-recall-logs/export.log     # Recent exports
  qmd search "authentication"                        # Search sessions
  qmd query "what did I work on yesterday"           # Semantic search

## Manual setup (without plugin)
If you prefer not to use the marketplace plugin:
1. Clone this repo
2. Run: python3 plugin/scripts/merge_settings.py --hook-path $(pwd)/plugin/scripts/export_session.sh --vault-dir ~/vault/sessions
3. Install qmd: bun install -g @tobilu/qmd
4. Register collection: qmd collection add ~/vault/sessions --name sessions

## Platform support
macOS and Linux. Windows is untested (WSL should work).
```

---

## Files to Create

| File | Description |
|------|-------------|
| `plugin/scripts/merge_settings.py` | Atomic settings.json merger (hook + qmd plugin) |
| `plugin/scripts/bulk_index.sh` | Batch JSONL → markdown converter (parallelized) |
| `plugin/skills/setup/SKILL.md` | Setup wizard skill (Claude-driven) |
| `plugin/.claude-plugin/plugin.json` | Plugin manifest |
| `.claude-plugin/marketplace.json` | Marketplace catalog |
| `README.md` | User-facing documentation |

## Files Moved

| From | To |
|------|-----|
| `scripts/export_session.sh` | `plugin/scripts/export_session.sh` |
| `scripts/parse_session.py` | `plugin/scripts/parse_session.py` |
| `scripts/session_to_md.py` | `plugin/scripts/session_to_md.py` |

Scripts move into `plugin/` so `${CLAUDE_PLUGIN_ROOT}/scripts/...` resolves correctly when installed via marketplace.

## Files Modified

### `plugin/scripts/export_session.sh` — Three targeted changes (after move):

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

## Files NOT Modified (content unchanged, only moved)
- `plugin/scripts/parse_session.py`, `plugin/scripts/session_to_md.py`

---

## Logging & Debugging

Hook runs during session close — stderr is invisible to the user. Persistent logs in `~/vault/.auto-recall-logs/`:

| File | Contents |
|------|----------|
| `hook-payloads.jsonl` | Every raw SessionEnd hook invocation (already implemented) |
| `export.log` | Timestamped export results: EXPORTED, SKIPPED, ERROR |
| `embed.log` | QMD embedding progress (already implemented) |

**`export.log` format** (one line per session):
```
2026-03-05T14:32:01Z  EXPORTED  ~/vault/sessions/2026-03-05_openclaw_abc12345.md
2026-03-05T14:35:22Z  SKIPPED   trivial/duplicate  /path/to/session.jsonl
2026-03-05T14:40:10Z  ERROR     session_to_md.py failed  /path/to/session.jsonl
```

Both `bulk_index.sh` and `export_session.sh` append to the same `export.log`.

---

## Milestones

### M1: Move scripts + Atomic Helpers + export_session.sh fixes
Deliverables: `plugin/scripts/` (all scripts moved), `merge_settings.py`, `bulk_index.sh`, updated `export_session.sh`

Verify:
1. `python3 plugin/scripts/merge_settings.py --hook-path /tmp/fake.sh --dry-run` prints JSON diff without modifying settings.json
2. `python3 plugin/scripts/merge_settings.py --hook-path /path/export_session.sh --vault-dir /tmp/test` → `~/.claude/settings.json` has hook with VAULT_DIR + qmd entries; run again → no-op (idempotent)
3. `VAULT_DIR=/tmp/test-vault bash plugin/scripts/export_session.sh` with piped JSON → markdown in /tmp/test-vault, structured line in export.log
4. `bash plugin/scripts/bulk_index.sh --vault-dir /tmp/test-vault` processes JSONLs in parallel, creates markdown files

### M2: Plugin structure + Setup Skill + README
Deliverables: `marketplace.json`, `plugin.json`, `plugin/skills/setup/SKILL.md`, `README.md`

Verify:
1. `python3 -m json.tool .claude-plugin/marketplace.json` and `python3 -m json.tool plugin/.claude-plugin/plugin.json` — both valid JSON
2. Invoke `/auto-recall-cc:setup` → Claude walks through wizard phases, calls helpers via `${CLAUDE_PLUGIN_ROOT}/scripts/...`, settings.json ends up correct
3. **End-to-end hook test**:
   ```bash
   echo '{"transcript_path":"tests/fixtures/sample-session.jsonl","session_id":"test","cwd":"."}' \
     | VAULT_DIR=/tmp/test-vault bash plugin/scripts/export_session.sh
   # → markdown file appears in /tmp/test-vault, export.log has EXPORTED line
   ```
4. README.md renders correctly and covers quick start, manual setup, troubleshooting
