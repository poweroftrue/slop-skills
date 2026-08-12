# Repository Instructions

## Slopmeter regression gate

- Treat `tests/slopmeter/cases.json`, its referenced prompts, fixtures, and expected verdicts as an owner-controlled regression registry.
- Do not add, remove, rename, or semantically change a registry case unless the user explicitly asks for that test change.
- Infrastructure-only fixes may change the runner, but must not skip cases or weaken expected verdicts.
- After any change under `plugins/slop-skills/skills/slopmeter/`, run `tests/slopmeter/run_e2e.sh` before declaring the work complete, committing, cachebusting, or publishing.
- If another plugin change can affect Slopmeter behavior, run the same full suite.
- A partial `--case` run is useful while iterating, but it does not satisfy the release gate.

## Slop Brief regression gate

- Keep `$slop-brief` implicitly invocable for general pull-request operations,
  including creation, review, branch updates, review-state changes, merge, close,
  and reopen requests.
- Preserve the authorization boundary: implicit read-only PR work must not edit
  GitHub, while an already authorized PR mutation refreshes the managed brief as
  part of that mutation.
- After any change under `plugins/slop-skills/skills/slop-brief/`, run all tests
  under `tests/slop-brief/` before committing, cachebusting, or publishing.
- Before publishing trigger-contract changes, test implicit activation in fresh
  Codex sessions. Use dry-run or read-only prompts so activation tests cannot
  mutate a real pull request.

## Slop Fix regression gate

- Keep `$slop-fix` explicit-only. It may edit local source and tests, but it
  must not commit, push, rebase, update a pull request, post a review, merge, or
  deploy without separate explicit authorization.
- Scope repairs by the pull request's intended behavior and the smallest correct
  fix, not only by changed-file membership.
- Fix every verified in-scope P-level finding, and report findings whose repair
  would change unrelated product behavior.
- After any change under `plugins/slop-skills/skills/slop-fix/`, run all tests
  under `tests/slop-fix/` before committing, cachebusting, or publishing.
