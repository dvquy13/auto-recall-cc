- docs/ext/qmd: QMD source (git subtree, do not modify directly)
- Plugin structure: two-tier (knowhub pattern) — root `marketplace.json` → `source: "./plugin"` → `plugin/.claude-plugin/plugin.json`
- `CLAUDE_PLUGIN_ROOT` is injected in hook commands and MCP config only — it is NOT available as an env var when skills run bash commands
- To reference plugin scripts from a skill, derive the plugin root from the skill header ("Base directory for this skill") by going two levels up: `$(dirname $(dirname "/path/from/header"))`
- Installed cache layout: `{cache}/scripts/` (not `{cache}/plugin/scripts/`)
- GitHub: https://github.com/dvquy13/auto-recall-cc
- Release: `export GITHUB_TOKEN=$(gh auth token) && npm run release`

Git commit MUST follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/#summary) standards.
