#!/usr/bin/env node
// Called by release-it after:bump to keep plugin manifests in sync with package.json
import fs from 'fs';

const version = process.argv[2];
if (!version) {
  console.error('Usage: sync-plugin-version.mjs <version>');
  process.exit(1);
}

// Update plugin/.claude-plugin/plugin.json
const pluginPath = 'plugin/.claude-plugin/plugin.json';
const plugin = JSON.parse(fs.readFileSync(pluginPath, 'utf8'));
plugin.version = version;
fs.writeFileSync(pluginPath, JSON.stringify(plugin, null, 2) + '\n');
console.log(`Updated ${pluginPath} to version ${version}`);

// Update .claude-plugin/marketplace.json (plugins[0].version)
const marketplacePath = '.claude-plugin/marketplace.json';
const marketplace = JSON.parse(fs.readFileSync(marketplacePath, 'utf8'));
marketplace.plugins[0].version = version;
fs.writeFileSync(marketplacePath, JSON.stringify(marketplace, null, 2) + '\n');
console.log(`Updated ${marketplacePath} to version ${version}`);
