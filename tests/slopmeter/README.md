# Slopmeter end-to-end regressions

This suite reviews fresh, temporary Git repositories with the canonical
`plugins/slop-skills/skills/slopmeter/SKILL.md`. It does not depend on an
installed plugin copy, and it never edits a fixture in place.

The authoritative case list is `cases.json`:

| Case | Expected verdict | Regression covered |
| --- | --- | --- |
| `runtime-formatting-after-app-boot` | Clean | Application loading changes runtime formatting, so a bare-runtime result is not a finding. |
| `strict-boundary-object-rejection` | One finding | A pinned external boundary explicitly rejects the object supplied by the changed call. |
| `compatible-undocumented-route` | Clean | Pinned router source accepts a compatibility route even though public docs omit it. |
| `unproven-full-scan-cost` | Clean | A full scan has no repository-established product-volume or latency failure. |
| `indexed-translation-n-plus-one` | One finding | An app-loaded 20-product page proves one indexed translation query per product. |
| `batched-translation-preload` | Clean | The same product-name path batches translations and keeps query count constant. |
| `unbounded-first-render` | One finding | A bounded first page materializes all 50,000 repository-established records. |
| `hot-lookup-missing-index` | One finding | A representative plan proves the new lookup scans 1.2 million rows and violates its target. |
| `lost-update-registry-race` | One grouped or two findings | Split add and drain operations must both be covered when they lose, erase, or duplicate work under reachable concurrent sequences. |
| `production-shaped-replay-string-key-regression` | One finding | The correct project's bounded sanitized sample fails in the fail-closed local app replay while ordinary tests pass. |
| `production-shaped-replay-compatible` | Clean | The same correct-project sample succeeds locally with outbound work captured only by a recording fake. |
| `production-state-matrix-lost-update` | One finding | One sanitized production seed expands into a real PostgreSQL state matrix that proves a two-connection lost update while sequential tests pass. |
| `production-state-matrix-precommit-side-effect` | One finding | A transition notification escapes before commit and remains observable after the real transaction rolls back. |
| `production-state-matrix-duplicate-retry` | One finding | Redelivering one event key incorrectly increments fulfillment twice despite the unique persisted event row. |
| `production-state-matrix-stale-related-rollup` | One finding | A current-line-only rollup marks the order fulfilled while a sibling line remains pending. |
| `production-state-matrix-compatible` | Clean | The same production-derived matrix proves commit, rollback, retry, duplicate, multi-line, reload, and concurrent state invariants with exact fake outbound calls. |

Registry cases, fixtures, prompts, and expectations are owner-controlled. Add,
remove, rename, or change their semantics only when the user explicitly asks for
that test change. Runner maintenance must not weaken a verdict or skip a case.
Cases may also require or forbid command patterns so the gate proves that the
reviewer performed the safe workflow rather than merely describing it.
Cases normally materialize `fixture/base` plus `fixture/head`; an optional
registry `head` selects a named candidate directory so finding and clean
variants can share one identical production-shaped base.

Cases marked with registry `runtime: "docker"` keep the fixture repository
read-only through a named Codex permission profile when Codex runs. OMP cases
run in fresh, ephemeral sessions and the runner rejects any fixture-repository
mutation after each review. Both harnesses use only the active local Docker Unix
socket; the runner refuses remote Docker contexts, admits no production
credentials, requires the `postgres:16-alpine` image to be present already, and
never pulls an image. The disposable database publishes no port and starts with
`--network none`.

Run the mandatory Codex gate after every Slopmeter skill change. Run both gates
for OMP packaging or compatibility changes:

```bash
tests/slopmeter/run_e2e.sh
tests/slopmeter/run_e2e.sh --harness omp
```

Useful local commands:

```bash
tests/slopmeter/run_e2e.sh --list
tests/slopmeter/run_e2e.sh --validate
tests/slopmeter/run_e2e.sh --case runtime-formatting-after-app-boot
tests/slopmeter/run_e2e.sh --harness omp --case runtime-formatting-after-app-boot
```

The runner requires `git`, `jq`, Ruby, and the selected `codex` or `omp`
executable. Each case starts a fresh, ephemeral session. Expected answers are
used only by the local classifier after the review finishes; they are never
included in the review prompt.
