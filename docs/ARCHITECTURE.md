# auto-recall-cc

> Auto-export Claude Code sessions to a searchable markdown vault.

## Structure

- `plugin/scripts/` — pipeline scripts (parse, render, export hook, atomic helpers)
- `plugin/skills/auto-recall-cc/` — unified dispatcher skill with sub-commands (setup, re-index, teardown, status)
- `plugin/.claude-plugin/plugin.json` — plugin manifest
- `.claude-plugin/marketplace.json` — marketplace catalog (two-tier root)
- `scripts/sync-plugin-version.mjs` — post-bump hook; syncs version to both `plugin.json` and `marketplace.json`
- `tests/fixtures/` — real session JSONL for testing
- `docs/ext/qmd/` — QMD source (git subtree, do not modify directly)

## Key Concepts

- **Session JSONL** — Claude Code writes one JSON line per event to `~/.claude/projects/…/*.jsonl`
- **Vault** — `~/vault/sessions/YYYY-MM-DD/` holds the exported markdown grouped by day; QMD indexes it
- **QMD** — local search engine over markdown; BM25 + optional vector search

## Entry Points

- `plugin/scripts/export_session.sh` — SessionEnd hook; reads stdin JSON, calls converters, updates QMD
- `plugin/scripts/session_to_md.py` — orchestrates `parse_session.py` + renders final markdown
- `plugin/scripts/parse_session.py` — parses JSONL into typed message list
- `plugin/scripts/update_claude_settings.py` — atomic `~/.claude/settings.json` merger (hook + qmd plugin registration; `--remove-hook` for teardown)
- `plugin/scripts/bulk_index.sh` — parallelized batch import of all existing sessions

## Data Flow

1. Claude Code session ends → hook fires with `{ transcript_path, session_id, cwd }`
2. `session_to_md.py` converts JSONL → markdown with YAML frontmatter → writes to `vault/YYYY-MM-DD/<filename>.md`
3. `qmd update --collection sessions` re-indexes changed files (incremental, hash-based)
4. `qmd embed` runs in background → generates vectors for new content only (incremental)
5. QMD MCP serves search results to Claude in future sessions

## JSONL Schema

Line types: `user`, `assistant`, `file-history-snapshot`, `progress`, `system`

- `isMeta: true` lines = local command echoes → skip
- `assistant` thinking blocks → skip
- `assistant` tool_use → render as `> **Tool:** Name: input`

## QMD Internals (verified)

- `qmd update` — incremental: skips docs whose content hash is unchanged
- `qmd embed` — incremental: only processes hashes not yet in the vector table (`getHashesForEmbedding`)
- Models (~2GB total): `embeddinggemma-300M-Q8_0` (~300MB), `qwen3-reranker-0.6b-q8_0` (~640MB), `Qwen3-0.6B-Q8_0` (~1.1GB)
- Models auto-download on first use (`qmd embed` triggers embedding model, `qmd query` triggers reranker + expansion)

## Logs

All hook logs in `~/vault/.auto-recall-logs/`:

| File | Contents |
|---|---|
| `hook-payloads.jsonl` | Raw SessionEnd hook payloads |
| `export.log` | Timestamped results: `EXPORTED`, `SKIPPED`, `ERROR` (one line per session) |
| `embed.log` | Background `qmd embed` output |

`export.log` format: `2026-03-05T14:32:01Z  EXPORTED  ~/vault/sessions/2026-03-05/2026-03-05_openclaw_abc12345.md`

## Release

- Tool: `release-it` + `@release-it/conventional-changelog` (angular preset)
- npm publish disabled — this is not an npm package
- `after:bump` hook runs `scripts/sync-plugin-version.mjs` to keep both manifest files in sync
- GitHub Releases created automatically; requires `GITHUB_TOKEN` env var (`gh auth token`)
- PR titles enforced as conventional commits via `.github/workflows/pr-title.yml`

## Gotchas

- **No automated tests** — `tests/` contains only `tests/fixtures/sample-session.jsonl`. A pytest plan exists (was designed but never implemented). Core logic in `parse_session.py` and `session_to_md.py` is currently untested outside the fixture.
- **`AskUserQuestion` requires ≥2 options** — for free-text input (e.g. git remote URL), use `"Enter value in the notes field below"` + `"Skip"` as the two options; read the value from the notes field on the first option.

## Decisions

- **Background embed** — `qmd embed` is forked after `qmd update` so session close is not blocked `(2026-03-05)`
- **Background git push** — `git push` backgrounded with `nohup` to avoid blocking session close `(2026-03-05)`
- **Skip trivial sessions** — sessions with <2 user messages are not exported (reduce noise)
- **Idempotent export** — re-running `session_to_md.py` on the same JSONL is safe (checks output hash)
- **Configurable VAULT_DIR** — `export_session.sh` reads `$VAULT_DIR` env var (default: `~/vault/sessions`); `update_claude_settings.py` injects it as `VAULT_DIR=<path>` prefix in the hook command `(2026-03-05)`
- **Two-tier plugin structure** — root `marketplace.json` → `source: "./plugin"` → `plugin.json`. Not qmd's single-file pattern (qmd IS a marketplace; we're a plugin self-hosting our marketplace). `(2026-03-05)`
- **Skill-to-scripts path** — `CLAUDE_PLUGIN_ROOT` is only injected for hooks/MCP configs, not when skills run bash commands. Skills derive the plugin root from the "Base directory for this skill" header: `$(dirname $(dirname "/path/from/header"))`. Installed cache flattens the `plugin/` prefix: scripts live at `{cache}/{version}/scripts/`, not `{cache}/{version}/plugin/scripts/`. `(2026-03-05)`
- **Defer model download** — `qmd pull` not run during setup; ~2GB of models download lazily on first `qmd embed`/`qmd query` to avoid blocking setup `(2026-03-05)`
- **Day-folder grouping** — `session_to_md.py` creates `vault/YYYY-MM-DD/` subfolders per session date; callers pass only the base `VAULT_DIR`, date subfolder is created internally `(2026-03-05)`
