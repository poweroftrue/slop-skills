# Slop Skills

Two focused Codex skills:

- `$deslop` simplifies changed code and applies behavior-preserving fixes.
- `$slopmeter` researches and reviews product-impacting defects without modifying code.

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

Update later with:

```bash
codex plugin marketplace upgrade slop-skills
codex plugin add slop-skills@slop-skills
```

Updating GitHub alone does not replace an already cached plugin. The two
commands above refresh the marketplace snapshot and reinstall the version
declared by the plugin manifest. Start a new Codex thread after upgrading.

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

## Maintainer release checklist

Edit the skills under `plugins/slop-skills/skills`; never edit Codex's plugin
cache or install another standalone copy. After changing a bundled skill:

```bash
python3 ~/.codex/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py plugins/slop-skills
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/slop-skills
```

Commit and push both the skill change and the generated manifest version. Then
run the normal update commands above to refresh the local Codex installation.
