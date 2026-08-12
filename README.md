# Slop Skills

Four focused Codex skills:

- `$deslop` simplifies changed code and applies behavior-preserving fixes.
- `$slopmeter` researches and reviews product-impacting defects without modifying code.
- `$slop-fix` verifies and repairs P-level findings that belong to the pull
  request, and reports repairs that would widen its scope.
- `$slop-brief` explains pull requests in product language and automatically
  maintains a managed brief during authorized PR operations.

## Source of truth

For skill and plugin behavior, edit and commit only the canonical plugin source
in this repository:

- `plugins/slop-skills/skills/deslop/`
- `plugins/slop-skills/skills/slopmeter/`
- `plugins/slop-skills/skills/slop-fix/`
- `plugins/slop-skills/skills/slop-brief/`
- `plugins/slop-skills/.codex-plugin/plugin.json`
- `.agents/plugins/marketplace.json`

The owner-controlled Slopmeter regression registry and its self-contained
fixtures live under `tests/slopmeter/`. Slop Fix contract tests live under
`tests/slop-fix/`. Slop Brief publisher and trigger-contract tests live under
`tests/slop-brief/`. Repository agents must
follow `AGENTS.md`:
registry semantics change only on explicit user request, every Slopmeter skill
change must pass the full suite, and Slop Brief changes must pass their complete
test suite plus fresh-session activation probes.

Do not edit generated Codex copies under `~/.codex/plugins/cache/` or
`~/.codex/.tmp/marketplaces/`. Do not install or copy these skills separately
under `~/.codex/skills/` while the plugin is enabled.

The update path is:

```text
GitHub source -> marketplace upgrade -> plugin reinstall/cache -> new Codex thread
```

A GitHub push does not directly rewrite an already installed Codex cache.

## Install

Install Slop Skills as a plugin only. Do not also copy `deslop`, `slopmeter`,
`slop-fix`, or `slop-brief` into `~/.codex/skills`; Codex treats standalone and
plugin-bundled skills as separate registrations, so installing both creates
duplicate entries.

```bash
codex plugin marketplace add poweroftrue/slop-skills --ref main
codex plugin add slop-skills@slop-skills
```

Start a new Codex thread, then run:

```text
$deslop pr #39
$slopmeter pr #39
$slop-fix pr #39
$slop-brief pr #39
```

`$slop-fix` is explicit-only. It authorizes local source and test edits, but it
does not authorize a commit, push, rebase, PR update, review comment, merge, or
deployment. It fixes verified P-level findings whose smallest correct repair
belongs to the PR and reports findings that would require unrelated behavior.

The canonical `slop-fix` skill also works with Prime Agent and Claude Code. For
a local development checkout, link the same source directory instead of copying
it:

```bash
ln -s "$PWD/plugins/slop-skills/skills/slop-fix" ~/.prime/agent/skills/slop-fix
ln -s "$PWD/plugins/slop-skills/skills/slop-fix" ~/.claude/skills/slop-fix
```

Use `/skill:slop-fix` in Prime Agent and `/slop-fix` in Claude Code. These links
keep one canonical skill source. Codex should continue to use the plugin install
above, not a standalone link.

`$slop-brief` is also eligible for implicit activation across the pull-request
lifecycle. Creating a PR, pushing an update to a branch with an open PR,
addressing review feedback, editing PR metadata, or merging/closing/reopening a
PR refreshes its managed section when that mutation is already authorized.
Review, explanation, comparison, and status requests remain read-only unless
the user explicitly authorizes a PR-description edit.

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

If `$deslop`, `$slopmeter`, `$slop-fix`, or `$slop-brief` appears twice, keep
the plugin and disable old standalone registrations in `~/.codex/config.toml`
using absolute paths:

```toml
[[skills.config]]
path = "/Users/you/.codex/skills/deslop/SKILL.md"
enabled = false

[[skills.config]]
path = "/Users/you/.codex/skills/slopmeter/SKILL.md"
enabled = false

[[skills.config]]
path = "/Users/you/.codex/skills/slop-fix/SKILL.md"
enabled = false

[[skills.config]]
path = "/Users/you/.codex/skills/change-brief/SKILL.md"
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
find ~/.codex -type f -path '*/slop-fix/SKILL.md' -print
find ~/.codex -type f -path '*/deslop/SKILL.md' -print
find ~/.codex -type f \( -path '*/slop-brief/SKILL.md' -o -path '*/change-brief/SKILL.md' \) -print
codex plugin list
```

Codex does not merge skills with the same `name`; every discovered registration
can appear in the skill selector.

## Maintainer release runbook

### 1. Edit only canonical source

Change files under `plugins/slop-skills/`. Never edit the installed cache or
recreate standalone copies under `~/.codex/skills/`.

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
"$PYTHON_BIN" ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  plugins/slop-skills/skills/slop-fix
"$PYTHON_BIN" ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  plugins/slop-skills/skills/slop-brief
"$PYTHON_BIN" ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  plugins/slop-skills

"$PYTHON_BIN" -m unittest discover -s tests/slop-fix -p 'test_*.py'
"$PYTHON_BIN" -m unittest discover -s tests/slop-brief -p 'test_*.py'

git diff --check
```

If `/usr/bin/python3` is unavailable, choose another interpreter only after
`<python> -c 'import yaml'` succeeds.

### 3. Run the regression gates

After any Slopmeter skill change, run every owner-approved end-to-end case
against the canonical source skill:

```bash
tests/slopmeter/run_e2e.sh
```

A partial `--case` run does not satisfy this release gate. Do not alter case
fixtures or expectations to make a skill change pass unless the user explicitly
requests that test change.

For Slop Brief changes, run the full deterministic suite shown above. For
trigger-description changes, also install the candidate plugin and use fresh,
read-only Codex sessions to verify implicit selection for representative create,
review, update, and merge prompts. Confirm explicit `$slopmeter` and `$deslop`
requests do not select Slop Brief unless it is also named.

### 4. Cachebust plugin payload changes

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

### 5. Review, commit, and push

Before committing, confirm that only intended source files and the generated
manifest version changed:

```bash
git diff --check
git diff -- AGENTS.md README.md plugins/slop-skills tests
git status --short --branch
```

Commit the skill and manifest changes together, then push `main`:

```bash
git add AGENTS.md README.md plugins/slop-skills tests
git commit -m "Describe the Slop Skills change"
git push origin main
git status --short --branch
```

Do not use the example commit message blindly; describe the actual change.

### 6. Refresh the installed plugin

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
- `~/.codex/skills/deslop`, `~/.codex/skills/slopmeter`,
  `~/.codex/skills/slop-fix`, and legacy
  `~/.codex/skills/change-brief` registrations are absent or disabled with
  `[[skills.config]]` entries.
- The repository is clean and synchronized with `origin/main`.
- A new Codex thread shows exactly one `$deslop`, one `$slopmeter`, one
  `$slop-fix`, and one `$slop-brief`.

If the selector is stale, restart Codex before changing installation state
again.
