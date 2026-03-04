# auto-recall-cc

> Auto-export Claude Code sessions to a searchable markdown vault.

## Structure

- `scripts/` — pipeline scripts (parse, render, export hook)
- `tests/fixtures/` — real session JSONL for testing
- `docs/ext/qmd/` — QMD source (git subtree, do not modify directly)
- `.claude/plans/publish.md` — plugin/onboarding ship plan

## Key Concepts

- **Session JSONL** — Claude Code writes one JSON line per event to `~/.claude/projects/…/*.jsonl`
- **Vault** — `~/vault/sessions/` holds the exported markdown; QMD indexes it
- **QMD** — local search engine over markdown; BM25 + optional vector search

## Entry Points

- `scripts/export_session.sh` — SessionEnd hook; reads stdin JSON, calls converters, updates QMD
- `scripts/session_to_md.py` — orchestrates `parse_session.py` + renders final markdown
- `scripts/parse_session.py` — parses JSONL into typed message list

## Data Flow

1. Claude Code session ends → hook fires with `{ transcript_path, session_id, cwd }`
2. `session_to_md.py` converts JSONL → markdown with YAML frontmatter → writes to vault
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
- Models (~500MB total): `embeddinggemma-300M-Q8_0`, `qwen3-reranker-0.6b-q8_0`, `Qwen3-0.6B-Q8_0`
- Run `qmd pull` once to download models before embedding works

## Logs

All hook logs in `~/vault/.auto-recall-logs/`:

| File | Contents |
|---|---|
| `hook-payloads.jsonl` | Raw SessionEnd hook payloads |
| `embed.log` | Background `qmd embed` output |

## Decisions

- **Background embed** — `qmd embed` is forked after `qmd update` so session close is not blocked `(2026-03-05)`
- **Skip trivial sessions** — sessions with <2 user messages are not exported (reduce noise)
- **Idempotent export** — re-running `session_to_md.py` on the same JSONL is safe (checks output hash)
