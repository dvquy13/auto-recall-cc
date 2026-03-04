#!/usr/bin/env python3
"""
merge_settings.py — Atomic Claude settings.json merger for auto-recall-cc.

CLI: python3 merge_settings.py --hook-path /abs/path/export_session.sh
                               [--vault-dir ~/vault/sessions]
                               [--dry-run]

Does three things in one atomic write:
  1. Register SessionEnd hook (with VAULT_DIR env var in the hook command)
  2. Add qmd marketplace entry (extraKnownMarketplaces.qmd)
  3. Enable qmd plugin (enabledPlugins["qmd@qmd"])

Outputs JSON: {"changes": [...], "status": "ok"}
Non-destructive: preserves all existing keys, skips already-present entries.
"""

import argparse
import json
import os
import sys
import tempfile


SETTINGS_PATH = os.path.expanduser("~/.claude/settings.json")
DEFAULT_VAULT_DIR = os.path.expanduser("~/vault/sessions")


def load_or_default(path):
    """Load settings.json, returning {} if missing. Raises on malformed JSON."""
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        content = f.read().strip()
    if not content:
        return {}
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"malformed settings.json: {e}", "status": "error"}))
        sys.exit(1)


def hook_already_registered(settings, hook_path):
    """Check if hook_path substring appears in any existing SessionEnd hook command."""
    for group in settings.get("hooks", {}).get("SessionEnd", []):
        for hook in group.get("hooks", []):
            if hook_path in hook.get("command", ""):
                return True
    return False


def write_atomic(path, data):
    """Write JSON atomically using a temp file + rename."""
    dir_ = os.path.dirname(path)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=dir_, suffix=".tmp", delete=False
    ) as f:
        json.dump(data, f, indent=2)
        f.write("\n")
        tmp_path = f.name
    os.rename(tmp_path, path)


def main():
    parser = argparse.ArgumentParser(description="Merge auto-recall-cc settings into ~/.claude/settings.json")
    parser.add_argument("--hook-path", required=True, help="Absolute path to export_session.sh")
    parser.add_argument("--vault-dir", default=DEFAULT_VAULT_DIR, help="Vault directory for exported sessions")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args()

    hook_path = os.path.expanduser(args.hook_path)
    vault_dir = os.path.expanduser(args.vault_dir)

    # Ensure ~/.claude exists
    claude_dir = os.path.dirname(SETTINGS_PATH)
    os.makedirs(claude_dir, exist_ok=True)

    settings = load_or_default(SETTINGS_PATH)
    changes = []

    # 1. SessionEnd hook (with VAULT_DIR env var prefix)
    hook_cmd = f"VAULT_DIR={vault_dir} {hook_path}"
    if not hook_already_registered(settings, hook_path):
        hook_entry = {"type": "command", "command": hook_cmd}
        settings.setdefault("hooks", {}).setdefault("SessionEnd", []).append(
            {"hooks": [hook_entry]}
        )
        changes.append(f"+ SessionEnd hook → {hook_path}")

    # 2. qmd marketplace
    if "qmd" not in settings.get("extraKnownMarketplaces", {}):
        settings.setdefault("extraKnownMarketplaces", {})["qmd"] = {
            "source": {"source": "github", "repo": "tobi/qmd"}
        }
        changes.append("+ extraKnownMarketplaces.qmd")

    # 3. qmd plugin
    if not settings.get("enabledPlugins", {}).get("qmd@qmd"):
        settings.setdefault("enabledPlugins", {})["qmd@qmd"] = True
        changes.append("+ enabledPlugins[qmd@qmd]")

    if changes and not args.dry_run:
        write_atomic(SETTINGS_PATH, settings)

    print(json.dumps({"changes": changes, "status": "ok"}))


if __name__ == "__main__":
    main()
