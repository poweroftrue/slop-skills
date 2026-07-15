# Slop Skills

Two focused Codex skills:

- `$deslop` simplifies changed code and applies behavior-preserving fixes.
- `$slopmeter` researches and reviews product-impacting defects without modifying code.

## Source of truth

Edit and commit only the plugin source in this repository:

- `plugins/slop-skills/skills/deslop/`
- `plugins/slop-skills/skills/slopmeter/`
- `plugins/slop-skills/.codex-plugin/plugin.json`
- `.agents/plugins/marketplace.json`

Do not edit generated Codex copies under `~/.codex/plugins/cache/` or
`~/.codex/.tmp/marketplaces/`. Do not install or copy these skills separately
under `~/.codex/skills/` while the plugin is enabled.

The update path is:

```text
GitHub source -> marketplace upgrade -> plugin reinstall/cache -> new Codex thread
```

A GitHub push does not directly rewrite an already installed Codex cache.

## Install

Install Slop Skills as a plugin only. Do not also copy `deslop` or `slopmeter`
into `~/.codex/skills`; Codex treats standalone and plugin-bundled skills as
separate registrations, so installing both creates duplicate `$deslop` and
`$slopmeter` entries.

```bash
codex plugin marketplace add poweroftrue/slop-skills --ref main
codex plugin add slop-skills@slop-skills
```

Start a new Codex thread, then run:

```text
$deslop pr #39
$slopmeter pr #39
```

## Update an installed copy

After a new plugin version is pushed to GitHub, run:

```bash
codex plugin marketplace upgrade slop-skills
codex plugin add slop-skills@slop-skills
codex plugin list
```

Confirm that `slop-skills@slop-skills` is `installed, enabled` and shows the
new manifest version. Start a new Codex thread after upgrading. If the old
version still appears, restart Codex and check again.

## Migrate an older standalone install

If `$deslop` or `$slopmeter` appears twice, keep the plugin and disable the old
standalone registrations in `~/.codex/config.toml` using absolute paths:

```toml
[[skills.config]]
path = "/Users/you/.codex/skills/deslop/SKILL.md"
enabled = false

[[skills.config]]
path = "/Users/you/.codex/skills/slopmeter/SKILL.md"
enabled = false
```

Replace `/Users/you` with your home directory, then start a new thread. If the
selector is still cached, restart Codex.

This setting is local to each machine. GitHub and the plugin installer cannot
delete or disable a pre-existing standalone skill automatically. Do not remove
these `skills.config` entries during future plugin updates unless the standalone
directories have also been removed or moved outside Codex's skill discovery
locations.

To diagnose duplicates, compare the standalone and plugin registrations:

```bash
find ~/.codex -type f -path '*/slopmeter/SKILL.md' -print
find ~/.codex -type f -path '*/deslop/SKILL.md' -print
codex plugin list
```

Codex does not merge skills with the same `name`; every discovered registration
can appear in the skill selector.

## Maintainer release runbook

### 1. Edit only canonical source

Change files under `plugins/slop-skills/`. Never edit the installed cache or
recreate `~/.codex/skills/deslop` or `~/.codex/skills/slopmeter`.

### 2. Validate the skills and plugin

Use a Python interpreter with PyYAML. On the current maintainer Mac,
`/usr/bin/python3` has the required module:

```bash
PYTHON_BIN=/usr/bin/python3
"$PYTHON_BIN" -c 'import yaml'

"$PYTHON_BIN" ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  plugins/slop-skills/skills/deslop
"$PYTHON_BIN" ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  plugins/slop-skills/skills/slopmeter
"$PYTHON_BIN" ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  plugins/slop-skills

git diff --check
```

If `/usr/bin/python3` is unavailable, choose another interpreter only after
`<python> -c 'import yaml'` succeeds.

### 3. Cachebust plugin payload changes

When a bundled skill, manifest capability, or other plugin payload changes,
update the manifest cachebuster exactly once:

```bash
"$PYTHON_BIN" \
  ~/.codex/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py \
  plugins/slop-skills

"$PYTHON_BIN" ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  plugins/slop-skills
```

The helper preserves the base version and replaces the existing `+codex.*`
suffix. Do not append multiple cachebusters or manually edit a cached plugin.

README-only or repository-documentation changes do not alter the plugin payload,
so they do not require a cachebuster or local plugin reinstall.

### 4. Review, commit, and push

Before committing, confirm that only intended source files and the generated
manifest version changed:

```bash
git diff --check
git diff -- plugins/slop-skills README.md
git status --short --branch
```

Commit the skill and manifest changes together, then push `main`:

```bash
git add README.md plugins/slop-skills
git commit -m "Describe the Slop Skills change"
git push origin main
git status --short --branch
```

Do not use the example commit message blindly; describe the actual change.

### 5. Refresh the installed plugin

For plugin payload releases, refresh the Git marketplace and reinstall from the
configured `slop-skills` marketplace:

```bash
codex plugin marketplace upgrade slop-skills
codex plugin add slop-skills@slop-skills
codex plugin list
```

Verify all of the following before declaring the update complete:

- `slop-skills@slop-skills` is `installed, enabled`.
- Its installed version matches `plugins/slop-skills/.codex-plugin/plugin.json`.
- `~/.codex/skills/deslop` and `~/.codex/skills/slopmeter` are absent or disabled
  with `[[skills.config]]` entries.
- The repository is clean and synchronized with `origin/main`.
- A new Codex thread shows exactly one `$deslop` and one `$slopmeter`.

If the selector is stale, restart Codex before changing installation state
again.
