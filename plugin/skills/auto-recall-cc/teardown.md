# Teardown

Remove the SessionEnd hook and optionally the QMD collection.

Before running any commands, resolve the plugin root from the skill's base directory (shown in the skill header as "Base directory for this skill") by going two levels up:
```bash
PLUGIN_ROOT=$(dirname $(dirname "/path/shown/in/skill/header"))
```
Substitute the actual path from the header.

1. Remove hook from ~/.claude/settings.json:
   python3 "$PLUGIN_ROOT/scripts/update_claude_settings.py" --remove-hook

2. Ask user (AskUserQuestion): "Also remove the QMD sessions collection?" Yes/No
   If yes: qmd collection remove sessions

3. Confirm what was removed. Vault files are NOT deleted.
