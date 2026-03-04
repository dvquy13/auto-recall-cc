# Plan: Setup Skill + Plugin Structure for auto-recall-cc

## Context
The project auto-exports Claude Code sessions to a searchable markdown vault. Currently, setup requires manual steps: clone repo, edit ~/.claude/settings.json, create vault dir, configure QMD collection.

Goal: Ship as a Claude plugin with an onboarding wizard skill + a manual export skill. Also provide a standalone `setup.sh` for non-plugin users. Both paths share the same atomic helper scripts.

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

## Architecture: Atomic Helpers + Claude Skill UX

```
scripts/
├── merge_settings.py      ← atomic: modifies ~/.claude/settings.json
├── bulk_index.sh          ← atomic: scan ~/.claude/projects/ and export JSONLs
├── export_session.sh      ← unchanged: SessionEnd hook
├── parse_session.py       ← unchanged
└── session_to_md.py       ← unchanged

plugin/skills/
├── setup/SKILL.md         ← Claude-driven onboarding wizard
└── export/SKILL.md        ← Claude-driven manual export
```

No standalone `setup.sh` — Claude handles all UX conversationally and calls the helpers directly.

---

## What Gets Built

### 1. `scripts/merge_settings.py` — Atomic Settings Helper

CLI: `python3 merge_settings.py --hook-path /abs/path/export_session.sh [--dry-run]`

Does three things in one atomic write:
1. Register SessionEnd hook
2. Add qmd marketplace (`extraKnownMarketplaces.qmd`)
3. Enable qmd plugin (`enabledPlugins["qmd@qmd"]`)

Outputs JSON diff of what changed (or would change with `--dry-run`).
Non-destructive: preserves all existing keys, skips already-present entries.

```python
# Core logic
settings = load_or_default("~/.claude/settings.json")
changes = []

# 1. Hook
hook_entry = {"type": "command", "command": hook_path}
if not hook_already_registered(settings, hook_path):
    settings["hooks"].setdefault("SessionEnd", []).append({"hooks": [hook_entry]})
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
    write_json("~/.claude/settings.json", settings)

print(json.dumps({"changes": changes, "status": "ok"}))
```

### 2. `scripts/bulk_index.sh` — Atomic Bulk Indexer

CLI: `bash bulk_index.sh --vault-dir ~/vault/sessions [--dry-run]`

- Finds all `*.jsonl` in `~/.claude/projects/`
- Calls `session_to_md.py` on each (skips trivial/already-exported)
- After all conversions: runs `qmd update --collection sessions`
- Outputs progress: `[3/47] Exported openclaw_abc12345.md`

### 3. `plugin/skills/setup/SKILL.md` — Setup Wizard Skill

Claude follows this script when user invokes `/auto-recall-cc:setup`:

**Phase 1: Recon (read-only Bash calls, no user prompts yet)**
```bash
which python3 && python3 --version
which qmd || echo "NOT_FOUND"
if which bun &>/dev/null; then echo "installer=bun"; elif which npm &>/dev/null; then echo "installer=npm"; elif which npx &>/dev/null; then echo "installer=npx"; else echo "installer=none"; fi
cat ~/.claude/settings.json | python3 -c "import sys,json; s=json.load(sys.stdin); print('hook_registered:', any(...))"
find ~/.claude/projects -name '*.jsonl' | wc -l
```
Report findings in a friendly summary.

**Phase 2: Gather preferences (conversation)**
- Vault dir? (default: `~/vault/sessions`, auto-suggest if vault/ exists)
- qmd installer is auto-selected (no user choice needed): check `bun` → `npm` → `npx` in that order; report which one will be used, or warn if none found

**Phase 3: Preview — show exact plan before acting**
```
Here's what I'll do:
  [1] Create: ~/vault/sessions
  [2] Modify ~/.claude/settings.json (dry-run output shows exact diff):
        + SessionEnd hook → ${CLAUDE_PLUGIN_ROOT}/scripts/export_session.sh
        + extraKnownMarketplaces.qmd
        + enabledPlugins[qmd@qmd]
  [3] Install qmd CLI: {bun|npm} install -g @tobilu/qmd  (auto-detected)
  [4] Register QMD collection "sessions" → ~/vault/sessions
  [5] (after) offer to bulk-index 47 existing sessions
  [6] (after) offer git vault sync

Shall I proceed?
```

**Phase 4: Execute**
1. `mkdir -p $VAULT_DIR`
2. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/merge_settings.py --hook-path ${CLAUDE_PLUGIN_ROOT}/scripts/export_session.sh`
3. `bun install -g @tobilu/qmd` (if needed)
4. `qmd collection add $VAULT_DIR --name sessions`

**Phase 5: Post-setup options (conversational)**
- Bulk-index: `bash ${CLAUDE_PLUGIN_ROOT}/scripts/bulk_index.sh --vault-dir $VAULT_DIR`
- Git sync: ask for remote URL, run `git init && git remote add origin URL && git push`

### 4. Plugin Structure

```
.claude-plugin/
└── marketplace.json           # points source to ./plugin

plugin/
├── .claude-plugin/
│   └── plugin.json
└── skills/
    └── setup/
        └── SKILL.md
```

**`plugin.json`**:
```json
{
  "name": "auto-recall-cc",
  "version": "0.1.0",
  "description": "Auto-export Claude Code sessions to a searchable markdown vault",
  "skills": ["./skills/"]
}
```

---

## Files to Create

| File | Description |
|------|-------------|
| `scripts/merge_settings.py` | Atomic settings.json merger (hook + qmd plugin) |
| `scripts/bulk_index.sh` | Batch JSONL → markdown converter |
| `plugin/skills/setup/SKILL.md` | Setup wizard skill (Claude-driven) |
| `plugin/.claude-plugin/plugin.json` | Plugin manifest |
| `.claude-plugin/marketplace.json` | Marketplace registration |

## Logging & Debugging

Hook runs during session close — stderr is invisible to the user. Logs are written to `~/vault/.auto-recall-logs/`:

| File | Contents |
|------|----------|
| `hook-payloads.jsonl` | Every raw SessionEnd hook invocation (already implemented) |
| `export.log` | Timestamped export results: path exported, skipped (trivial), errors |

Both `bulk_index.sh` and the hook (`export_session.sh`) should append to `~/vault/.auto-recall-logs/export.log`.

**`export.log` format** (one line per session):
```
2026-03-05T14:32:01Z  EXPORTED  ~/vault/sessions/2026-03-05_openclaw_abc12345.md
2026-03-05T14:35:22Z  SKIPPED   trivial (<2 user msgs)  session_xyz.jsonl
2026-03-05T14:40:10Z  ERROR     python3 not found
```

**How users access logs** (the setup skill explains this):
```bash
# Recent exports
tail -20 ~/vault/.auto-recall-logs/export.log

# All hook invocations
cat ~/vault/.auto-recall-logs/hook-payloads.jsonl | tail -5 | python3 -m json.tool

# Count of exports today
grep $(date +%Y-%m-%d) ~/vault/.auto-recall-logs/export.log | grep EXPORTED | wc -l
```

The setup skill's final message should include these commands so users know how to verify things are working.

**`export_session.sh` is modified** (minimally) to also write structured lines to `export.log` in addition to existing stderr output.

## Files Not Modified
- `scripts/parse_session.py`, `scripts/session_to_md.py`

## Files Modified (minimally)
- `scripts/export_session.sh` — add structured `export.log` writes alongside existing stderr logging

---

## Milestones

### M1: Atomic Helpers
Deliverables: `scripts/merge_settings.py` + `scripts/bulk_index.sh`

Verify:
1. `python3 scripts/merge_settings.py --hook-path /tmp/fake.sh --dry-run` prints JSON diff without modifying settings.json
2. `python3 scripts/merge_settings.py --hook-path /path/export_session.sh` → `~/.claude/settings.json` has hook + qmd entries; run again → no-op (idempotent)
3. `bash scripts/bulk_index.sh --vault-dir /tmp/test-vault` processes all JSONLs in `~/.claude/projects/` and creates markdown files

### M2: Plugin structure + Setup Skill
Deliverables: plugin files, `setup/SKILL.md`, `marketplace.json`

Verify:
1. `plugin.json` and `marketplace.json` are valid JSON — run `python3 -m json.tool plugin/.claude-plugin/plugin.json` and same for marketplace.json
2. Invoke `/auto-recall-cc:setup` → Claude walks through wizard phases, calls helpers correctly via Bash tool, settings.json ends up with correct entries
3. **End-to-end hook test** (manual): pipe a sample payload to `export_session.sh` to confirm the auto-export pipeline still works after setup:
   ```bash
   echo '{"transcript_path":"tests/fixtures/sample-session.jsonl","session_id":"test","cwd":"."}' \
     | bash scripts/export_session.sh
   # → markdown file appears in vault, qmd search returns it
   ```
