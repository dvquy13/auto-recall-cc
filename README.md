# auto-recall-cc

Auto-export Claude Code sessions to a searchable markdown vault.

## What it does

Every time a Claude Code session ends, auto-recall-cc converts the raw JSONL
transcript to clean markdown and indexes it with QMD for instant search.

## Quick start

1. Add marketplace: `claude plugin marketplace add dvquy13/auto-recall-cc`
2. Install plugin: `claude plugin install auto-recall-cc@auto-recall-cc`
3. Run: `/auto-recall-cc:setup` in any Claude Code session
4. Done — future sessions auto-export on close

## How it works

- **SessionEnd hook** converts JSONL → markdown → vault directory
- **QMD** indexes the vault for keyword search, semantic search, and hybrid search
- **Git sync** (optional) pushes vault to a remote for backup

## Pipeline

```
Session JSONL → parse_session.py → session_to_md.py → ~/vault/sessions/ → qmd update → qmd embed
```

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

```bash
tail -20 ~/vault/.auto-recall-logs/export.log     # Recent exports
qmd search "authentication"                        # Search sessions
qmd query "what did I work on yesterday"           # Semantic search
```

## Manual setup (without plugin)

If you prefer not to use the marketplace plugin:

```bash
git clone https://github.com/dvquy13/auto-recall-cc
cd auto-recall-cc
python3 plugin/scripts/merge_settings.py \
  --hook-path $(pwd)/plugin/scripts/export_session.sh \
  --vault-dir ~/vault/sessions
bun install -g @tobilu/qmd
qmd collection add ~/vault/sessions --name sessions
```

## Platform support

macOS and Linux. Windows is untested (WSL should work).
