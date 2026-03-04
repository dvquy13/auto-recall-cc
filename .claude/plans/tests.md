# Plan: Automated Tests for auto-recall-cc

## Context
The plugin has zero test infrastructure. All core logic lives in two Python files with clean, pure-function interfaces — ideal for unit testing. The existing `sample-session.jsonl` fixture provides a real-world baseline. Setting up tests now will catch regressions as the plugin moves toward publishing.

## Approach: pytest with fixture-driven tests

### Setup
- Add `tests/conftest.py` with shared fixtures (paths, parsed session data)
- No `pyproject.toml` or extra deps — just `pytest` (already available or `pip install pytest`)
- Tests use stdlib + pytest only

### Files to create

**`tests/conftest.py`** — shared fixtures
- `fixture_dir` — path to `tests/fixtures/`
- `sample_jsonl` — path to the sample JSONL
- `parsed_session` — pre-parsed result from `parse_session(sample_jsonl)`

**`tests/test_parse_session.py`** — unit tests for `scripts/parse_session.py`
- `summarize_tool_input`: Read/Write/Edit (file_path), Bash (command), Glob (pattern), Grep (pattern + path), Agent/Explore/Plan (prompt), generic fallback, empty input
- `extract_user_text`: plain string, meta-prefixed strings (`<local-command`, `<command-name`, `<system`), list with tool_result (skipped), list with text, list with interrupted text, empty/None
- `extract_assistant_content`: text blocks, thinking blocks (skipped), tool_use blocks, mixed content
- `parse_session` with fixture: correct metadata fields (session_id, cwd, git_branch, version, timestamps), correct message count, role distribution, skips isMeta/file-history-snapshot/progress/system lines
- Edge cases: empty file, malformed JSON lines

**`tests/test_session_to_md.py`** — unit tests for `scripts/session_to_md.py`
- `_project_from_cwd`: normal path → leaf dir name, empty → "unknown"
- `_date_from_ts`: ISO timestamp → "YYYY-MM-DD", empty → "unknown"
- `_is_trivial`: 0 user msgs → True, 1 → True, 2 → False
- `output_filename`: format `{date}_{safe_project}_{id8}.md`, special chars sanitized
- `render_markdown`: has YAML frontmatter delimiters, `# Session:` heading, `## User`/`## Assistant` sections, `> **Tool:**` blocks, italicized first user message
- CLI integration (subprocess): stdout mode prints markdown, file mode creates file + prints path, `--no-skip-trivial` flag, idempotent re-export

**`tests/fixtures/trivial-session.jsonl`** — new minimal fixture
- Session with only 1 user message → triggers trivial-skip logic

### Critical files to modify
- None modified — all new files under `tests/`

### Key reuse
- `scripts/parse_session.py:parse_session()` — imported directly in tests
- `scripts/session_to_md.py` functions — imported directly (need `sys.path` or conftest fixture)
- `tests/fixtures/sample-session.jsonl` — existing fixture, verified to produce 10 messages

### Verification
- `python -m pytest tests/ -v` — all tests pass
- Coverage of all pure functions in both scripts
- At least one integration test exercises the CLI end-to-end
