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
| `lost-update-registry-race` | One finding | Split read/write state updates lose data under a reachable concurrent sequence. |

Registry cases, fixtures, prompts, and expectations are owner-controlled. Add,
remove, rename, or change their semantics only when the user explicitly asks for
that test change. Runner maintenance must not weaken a verdict or skip a case.

Run the mandatory full gate after every Slopmeter skill change:

```bash
tests/slopmeter/run_e2e.sh
```

Useful local commands:

```bash
tests/slopmeter/run_e2e.sh --list
tests/slopmeter/run_e2e.sh --validate
tests/slopmeter/run_e2e.sh --case runtime-formatting-after-app-boot
```

The runner requires `codex`, `git`, `jq`, and Ruby. Each case starts a fresh,
ephemeral, read-only Codex session. Expected answers are used only by the local
classifier after the review finishes; they are never included in the review
prompt.
