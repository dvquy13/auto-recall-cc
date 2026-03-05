---
name: auto-recall-cc
description: Manage auto-recall-cc — setup, re-index, teardown, or check status. Use when user wants to configure, repair, or inspect their session vault.
argument-hint: "[setup|re-index|teardown|status]"
disable-model-invocation: true
---

# Auto-Recall-CC

Based on the user's intent in $ARGUMENTS, execute the matching task:

- **Setup / install / configure** → follow setup.md
- **Re-index / rebuild index / sync sessions** → follow re-index.md
- **Teardown / uninstall / remove** → follow teardown.md
- **Status / health / check** → follow status.md

If $ARGUMENTS is empty or the intent is unclear, show:

  Usage: /auto-recall-cc [setup|re-index|teardown|status]

    setup      Run the setup wizard
    re-index   Rebuild the QMD search index
    teardown   Remove hooks and uninstall
    status     Show recent exports and QMD health
