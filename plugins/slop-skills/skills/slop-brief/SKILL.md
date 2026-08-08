---
name: slop-brief
description: "Create and maintain product-language briefs for GitHub pull requests. Use whenever a task operates on a PR or a branch with an open or intended PR: create, open, or draft it; inspect, review, explain, summarize, compare, or check status and merge readiness; push or update commits, branch, title, body, labels, reviewers, checks, or draft/ready state; address feedback; comment, approve, or request changes; merge, close, or reopen. Also use for product-language diff or commit explanations, every changed file in logical order, a dictionary before changes, explicit $slop-brief, or legacy $change-brief requests. On authorized PR mutations, synchronize the managed Slop Brief; on implicit read-only requests, produce it without writing. Do not use for explicit $slopmeter or $deslop unless $slop-brief is also invoked."
---

# Slop Brief

Make an unfamiliar pull request understandable and keep its product brief current.

## Choose the operating mode

1. **Creating or mutating a PR:** The user already authorized a scoped external
   change such as opening the PR, pushing its branch, editing it, addressing
   feedback, changing its review or draft state, merging, closing, or reopening
   it. Build or refresh the managed Slop Brief automatically as part of that
   operation.
2. **Explicit `$slop-brief`:** For an open PR, synchronize the managed section
   unless the user says to keep the task read-only or not publish it.
3. **Implicit read-only PR work:** Review, explain, compare, or report status in
   chat, but do not edit GitHub. A review request alone does not authorize a PR
   description update.
4. **Closed or merged PR:** Do not publish unless the user explicitly asks to
   update that closed or merged PR. When the user authorizes merge or close,
   refresh the section while the PR is still open, then perform the terminal
   operation.

Never turn a read-only request into a write. Preserve all PR description text
outside the managed markers.

## Inspect the real change

1. Read the repository instructions and product source of truth first.
2. Resolve the exact PR, or the current branch and intended base when the PR
   does not exist yet.
3. Inspect the actual base-to-head diff and enough surrounding code to
   understand old and new behavior.
4. Identify the product problem before explaining files.
5. Account for every changed file in a managed PR brief. Group files only when
   they implement or verify one coherent behavior.
6. Separate:
   - confirmed code behavior;
   - likely rationale or inference;
   - genuine unknowns;
   - production changes;
   - Test-only changes;
   - unrelated changes or suspicious drift;
   - current CI, review, and merge state.
7. Do not assume existing code or the proposed change is correct merely because
   someone wrote it.

## Build the brief

Start with these sections in this order:

```markdown
## Dictionary

- Term — One short product-language meaning.

## Changes in logical order

- **1. Product outcome**
  - What changes and who or what it affects.
  - Why it is needed or what risk it prevents.
  - Example: one concrete scenario when useful.
  - Files: `path/one`, `path/two`.
```

### Dictionary rules

1. Define exactly the unfamiliar terms used later in the change list.
2. Prefer one-word terms and one-sentence product meanings.
3. Explain what a term represents in the product, not merely how its class or
   table works.
4. Include technical terms such as **Migration** or **Fixture** only when they
   are used later and may be unfamiliar.
5. Use repository language and user-provided definitions. Never carry one
   project's dictionary into another project.
6. Remove unused definitions and rewrite undefined jargon in plain language.

### Change-list rules

1. Use numbered top-level bullets, not a table.
2. Order changes by dependency and product flow rather than filename. Prefer:
   - core identity and stored data;
   - preservation of existing records;
   - selection and routing;
   - customer or fulfillment flow;
   - imports and operator tools;
   - Tests;
   - unrelated drift, risks, CI, and merge status.
3. Group files only when they implement or verify one coherent behavior.
4. Explain what changed, why it matters, a concrete example when useful, and
   every affected file.
5. Explain business consequences instead of leaving mechanical statements
   alone.
6. For normalization rules, show equivalent and conflicting inputs. For
   example, say that `MENA`, `mena`, and ` mena ` become one label.
7. Say whether behavior is generic or tied to a provider, integration, customer
   type, or example.
8. Say whether an identifier, model, or rule already existed or is new. When a
   new identifier is used, explain why an existing one is insufficient; label
   an unconfirmed reason as inference.
9. Mark Test-only edits clearly because they do not change production behavior.
10. Call out unrelated files or broad generated-file drift.
11. Keep paths in backticks and never use raw HTML such as `<br>`.

## Handle design challenges

When the user asks why, proposes a simpler alternative, or challenges unfamiliar
code:

1. Inspect the relevant implementation when available.
2. State what the code confirms.
3. Explain likely rationale without presenting inference as fact.
4. Evaluate the alternative honestly and state when it would work.
5. Integrate that conclusion into the relevant change group.

## Handle PR operations

### Create or open

1. Finish the complete brief before opening the PR.
2. Create the PR with the user's normal rationale and verification text.
3. After the create command returns the PR number or URL, write the brief to a
   temporary file outside the repository and run:

   ```bash
   scripts/publish_slop_brief.py --pr <number-or-url> --brief-file <path>
   ```

4. Verify the live PR contains one managed Slop Brief section and report its
   URL plus whether the section was created, updated, migrated, or unchanged.

### Update, push, edit, review-state change, or address feedback

1. Finish the requested code or PR operation first, including its relevant
   verification.
2. Re-resolve the live base, head, files, checks, reviews, and merge state.
3. Rebuild the entire brief from the current PR rather than appending a fragment.
4. Publish it with `scripts/publish_slop_brief.py` and verify the live section.

### Merge or close

1. Rebuild and publish the final brief while the PR is still open.
2. Perform the authorized merge or close operation.
3. Verify the resulting PR state without trying to publish afterward.

### Review, explain, compare, or check status

Build the same self-contained brief in chat. Publish only when `$slop-brief`
was explicitly invoked or the user separately authorized a PR description
write. If another requested review workflow has its own output contract, keep
that contract and use Slop Brief only for PR context/synchronization allowed by
the active mode.

## Publish safely

Resolve `scripts/publish_slop_brief.py` relative to this skill directory. The
script owns only text between its hidden markers, preserves all other PR body
content, and migrates a legacy `change-brief` marker pair when present.

Publish only after the complete `## Dictionary` and
`## Changes in logical order` brief is ready. Do not publish a conversational
`## Answer` section. If authentication, permission, or PR discovery fails,
finish the local brief and report that synchronization did not occur.

Use `--allow-closed` only when the user explicitly asks to update a closed or
merged PR. Use `--dry-run` for validation that must not modify GitHub.

## Handle follow-ups

For every follow-up about the same PR:

1. Lead with `## Answer` when the user asked a direct question.
2. Reproduce the entire updated `## Dictionary` and
   `## Changes in logical order` response immediately afterward unless the user
   asks for a shorter answer.
3. Integrate the answer into the relevant numbered group and replace outdated
   wording.
4. Preserve all previously covered files and changes that remain in the live
   diff.
5. Recheck dictionary coverage, file coverage, logical order, CI, and
   production-versus-Test labels.
6. Never say “see above,” “unchanged,” or provide only a corrected fragment.
7. Synchronize again only when the chosen operating mode permits a write.

## Style

- Write for a product owner, not only an engineer.
- Keep explanations short but complete enough to support a merge decision.
- Prefer concrete product examples over abstract implementation language.
- Lead with outcomes and risks.
- Do not defend legacy code automatically.
