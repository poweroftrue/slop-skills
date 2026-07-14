# Slop Skills

Two focused Codex skills:

- `$deslop` simplifies changed code and applies behavior-preserving fixes.
- `$slopmeter` researches and reviews product-impacting defects without modifying code.

## Install

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
