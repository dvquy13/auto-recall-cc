# Re-index

Re-export all JSONL sessions to markdown and rebuild the QMD index.

Before running any commands, resolve the plugin root from the skill's base directory (shown in the skill header as "Base directory for this skill") by going two levels up:
```bash
PLUGIN_ROOT=$(dirname $(dirname "/path/shown/in/skill/header"))
```
Substitute the actual path from the header.

1. Run bulk export:
   bash "$PLUGIN_ROOT/scripts/bulk_index.sh" --vault-dir ~/vault/sessions

2. Update QMD collection:
   qmd update --collection sessions

3. Start background embed:
   nohup qmd embed >> ~/vault/.auto-recall-logs/embed.log 2>&1 &

Report counts from bulk_index.sh output. Tell the user embed runs in the background.
