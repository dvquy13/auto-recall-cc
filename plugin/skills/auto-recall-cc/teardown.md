# Teardown

Remove the SessionEnd hook and optionally the QMD collection.

1. Remove hook from ~/.claude/settings.json:
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/update_claude_settings.py --remove-hook

2. Ask user (AskUserQuestion): "Also remove the QMD sessions collection?" Yes/No
   If yes: qmd collection remove sessions

3. Confirm what was removed. Vault files are NOT deleted.
