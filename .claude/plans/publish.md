# Plan: Setup Skill + Plugin Structure for auto-recall-cc

## Context
The project auto-exports Claude Code sessions to a searchable markdown vault. Currently, setup requires manual steps: clone repo, edit ~/.claude/settings.json, create vault dir, configure QMD collection.

Goal: Ship as a Claude plugin with an onboarding wizard skill. Claude handles all UX conversationally and calls atomic helper scripts directly.

## Installation Flow

```
1. User installs plugin:
     claude plugin marketplace add dvq/auto-recall-cc

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

- [M1: Move scripts + Atomic Helpers + export_session.sh fixes](./publish/m1-scripts.md)
- [M2: Plugin structure + Setup Skill + README](./publish/m2-plugin.md)
