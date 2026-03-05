# Re-index

Re-export all JSONL sessions to markdown and rebuild the QMD index.

1. Run bulk export:
   bash ${CLAUDE_PLUGIN_ROOT}/scripts/bulk_index.sh --vault-dir ~/vault/sessions

2. Update QMD collection:
   qmd update --collection sessions

3. Start background embed:
   nohup qmd embed >> ~/vault/.auto-recall-logs/embed.log 2>&1 &

Report counts from bulk_index.sh output. Tell the user embed runs in the background.
