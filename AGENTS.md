# Repository Instructions

## Slopmeter regression gate

- Treat `tests/slopmeter/cases.json`, its referenced prompts, fixtures, and expected verdicts as an owner-controlled regression registry.
- Do not add, remove, rename, or semantically change a registry case unless the user explicitly asks for that test change.
- Infrastructure-only fixes may change the runner, but must not skip cases or weaken expected verdicts.
- After any change under `plugins/slop-skills/skills/slopmeter/`, run `tests/slopmeter/run_e2e.sh` before declaring the work complete, committing, cachebusting, or publishing.
- If another plugin change can affect Slopmeter behavior, run the same full suite.
- A partial `--case` run is useful while iterating, but it does not satisfy the release gate.
