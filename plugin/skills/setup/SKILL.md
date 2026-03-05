# auto-recall-cc Setup Wizard

When invoked, guide the user through setting up auto-recall-cc to auto-export their Claude Code sessions to a searchable markdown vault.

---

## Phase 1: Recon (run all probes silently before saying anything)

Run these checks in a single Bash call:

```bash
python3 --version 2>&1 || echo "PYTHON_MISSING"
command -v qmd && qmd --version 2>&1 || echo "QMD_MISSING"
for cmd in bun npm npx; do command -v $cmd &>/dev/null && echo "installer=$cmd" && break; done 2>/dev/null || echo "installer=none"
find ~/.claude/projects -maxdepth 4 -name '*.jsonl' 2>/dev/null | wc -l
test -d ~/vault && echo "vault_exists=1" || echo "vault_exists=0"
```

Then report findings conversationally (no bullet lists, just natural sentences):
- "python3 3.9.6 — ready" or stop with "python3 is required but wasn't found. Please install it (python.org) and re-run setup."
- "qmd not installed — I'll install it" or "qmd 0.x.x — ready"
- "Found 47 existing sessions to bulk-import after setup" (or nothing if 0)

**Hard stops:**
- python3 missing → stop, tell user to install python3 (3.9+)
- no package manager (bun/npm/npx) AND qmd not installed → stop, explain qmd requires bun, npm, or npx

---

## Phase 2: Gather preferences

Use AskUserQuestion with two options:
- `~/vault/sessions` (default)
- "Other — I'll type a path"

If the user picks "Other", follow up with another AskUserQuestion for the custom path (free-text).

If `~/vault/` already exists (from recon), suggest `~/vault/sessions` as the default. Otherwise suggest `~/vault/sessions` anyway.

Expand `~` to the full home path. Store as `VAULT_DIR`.

---

## Phase 3: Preview — show plan before acting

Show this user-friendly plan (no internal key names like `extraKnownMarketplaces`):

```
Here's what I'll do:

  [1] Create vault directory: {VAULT_DIR}
  [2] Register auto-export hook (runs automatically when each session closes)
  [3] Enable QMD search over your sessions
  [4] {Install qmd CLI via {installer} | qmd already installed — skip}
  [5] Register QMD collection "sessions" pointing to {VAULT_DIR}

  After setup (optional):
  [6] Bulk-import {N} existing sessions
  [7] Set up git sync for your vault

Shall I proceed? (yes/no)
```

Use `merge_settings.py --dry-run` to verify the settings changes internally if needed, but show only the plain-English version above to the user. Do not show internal key names.

Then use AskUserQuestion with options: "Yes, proceed" / "No, cancel".

---

## Phase 4: Execute (only after user says yes)

Run each step, reporting progress:

**Step 1** — Create vault directory:
```bash
mkdir -p {VAULT_DIR}
```

**Step 2** — Register hook + enable QMD search:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/merge_settings.py \
  --hook-path ${CLAUDE_PLUGIN_ROOT}/scripts/export_session.sh \
  --vault-dir {VAULT_DIR}
```
Show the changes output. If empty `changes: []`, say "already configured — nothing to change."

**Step 3** — Install qmd if needed:
```bash
command -v qmd &>/dev/null || {installer} install -g @tobilu/qmd
```
(Use execution-time check, not the recon result — guard at runtime.)

**Step 4** — Register QMD collection:
```bash
qmd collection add {VAULT_DIR} --name sessions
```
If it errors with "already exists" or similar, treat as success.

**Note on QMD models:** Do NOT run `qmd pull` during setup. The ~2GB of models (embedding, reranker, query expansion) download automatically on first use. The hook will trigger the first download (~300MB) on the next session close.

---

## Phase 5: Post-setup options (conversational)

Ask each question separately:

**Bulk import:**

Use AskUserQuestion: "I found {N} existing sessions. Want me to import them now? This will run in the foreground and may take a few minutes."
Options: "Yes, import now" / "No, skip"

If yes:
```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/bulk_index.sh --vault-dir {VAULT_DIR}
```

**Git sync:**

Use AskUserQuestion: "Want to back up your vault to a git remote?"
Options: "Yes, set it up" / "No, skip"

If yes, use another AskUserQuestion to collect the remote URL (free-text). Then:
```bash
cd $(dirname {VAULT_DIR})
git init
git remote add origin {REMOTE_URL}
git add .
git commit -m "initial vault"
git push -u origin main
```

---

## Phase 6: Done — show verification commands

```
Setup complete! Your sessions will auto-export from now on.

To verify everything is working:

  # Check recent exports
  tail -20 ~/vault/.auto-recall-logs/export.log

  # Search your sessions
  qmd search "authentication bug"
  qmd query "what did I work on last week"

  # View QMD status
  qmd status

Note: QMD search models (~300MB) will download automatically on your next session close.

For full docs: https://github.com/dvq/auto-recall-cc#readme
```

---

## Error handling

- If any step fails, show the exact error and stop. Do not silently swallow errors.
- For `merge_settings.py` errors: show the JSON error field and tell the user to check `~/.claude/settings.json`.
- For `qmd collection add` errors: check if the collection already exists with `qmd status`; if so, continue.
- After any failure, tell the user which step failed and what to try next.
