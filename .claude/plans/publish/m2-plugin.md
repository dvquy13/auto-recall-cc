# M2: Plugin Structure + Setup Skill + README

**Status:** completed (2026-03-05)

## Deliverables
- `plugin/.claude-plugin/plugin.json` — plugin manifest
- `.claude-plugin/marketplace.json` — marketplace catalog
- `plugin/skills/setup/SKILL.md` — setup wizard skill
- `README.md` — user-facing documentation

---

## Plugin Structure

Two-tier layout following knowhub's pattern. Root marketplace catalog points to `plugin/` subdirectory where the actual plugin manifest lives.

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

Why two-tier (not qmd's single-file pattern):
- qmd IS a marketplace (its repo root IS the plugin). auto-recall-cc is a plugin that self-hosts its marketplace.
- knowhub uses this exact pattern and it works: `marketplace.json` → `source: "./plugin"` → `plugin/.claude-plugin/plugin.json`
- Keeps non-plugin files (tests/, docs/, .claude/) out of the installed plugin
- `CLAUDE_PLUGIN_ROOT` resolves to `<install_dir>/plugin/`, so `${CLAUDE_PLUGIN_ROOT}/scripts/export_session.sh` works

---

## `.claude-plugin/marketplace.json`

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

## `plugin/.claude-plugin/plugin.json`

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

---

## `plugin/skills/setup/SKILL.md` — Setup Wizard Skill

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

---

## `README.md` — User-Facing Documentation

```markdown
# auto-recall-cc

Auto-export Claude Code sessions to a searchable markdown vault.

## What it does
Every time a Claude Code session ends, auto-recall-cc converts the raw JSONL
transcript to clean markdown and indexes it with QMD for instant search.

## Quick start
1. Install: `claude plugin marketplace add dvq/auto-recall-cc`
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

## Verification

1. `python3 -m json.tool .claude-plugin/marketplace.json` and `python3 -m json.tool plugin/.claude-plugin/plugin.json` — both valid JSON
2. Invoke `/auto-recall-cc:setup` → Claude walks through wizard phases, calls helpers via `${CLAUDE_PLUGIN_ROOT}/scripts/...`, settings.json ends up correct
3. **End-to-end hook test**:
   ```bash
   echo '{"transcript_path":"tests/fixtures/sample-session.jsonl","session_id":"test","cwd":"."}' \
     | VAULT_DIR=/tmp/test-vault bash plugin/scripts/export_session.sh
   # → markdown file appears in /tmp/test-vault, export.log has EXPORTED line
   ```
4. README.md renders correctly and covers quick start, manual setup, troubleshooting
