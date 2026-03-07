---
name: code-review
description: Senior engineer PR review workflow. Use when asked to review a diff or pull request for correctness, security, reliability, performance, and maintainability, using CodeRabbit as one input but returning only high-signal findings in a structured Markdown review.
---

# Code Review

## Role

Act as a senior software engineer reviewing a proposed patch. Prioritize correctness, security, reliability, performance, and material maintainability risks. Be direct and selective. Prefer no findings over weak findings.

## Preconditions

Before resolving the base branch, check for unstaged changes:

```bash
git diff --quiet --
```

- If this exits non-zero, stop immediately.
- Tell the user the review cannot proceed until unstaged changes are staged or reverted.
- Do not resolve a base branch and do not run CodeRabbit when unstaged changes exist.

Resolve the default remote base branch:

```bash
git symbolic-ref --short refs/remotes/origin/HEAD
```

- Present the resolved branch, for example `origin/main`.
- Ask the user to confirm it with a Yes/No answer.
- If the user says No, ask for the exact base branch name.
- Do not start the review until the base branch is explicitly confirmed.

## CodeRabbit Pass

After base confirmation, run:

```bash
coderabbit auth status
coderabbit review --plain --type all --base <confirmed-base-branch> --cwd <repo-root>
```

Execution rules:

- `coderabbit` must be installed and authenticated.
- If authentication fails or the command fails definitively, stop and report failure.
- Use non-interactive plain-text mode only.
- Start the review in the background and poll until it finishes or clearly fails.
- Treat transient telemetry or network noise as non-fatal unless the command itself fails or never produces substantive review output.

If repository guidance files exist, pass them in stable order:

1. `AGENTS.md`
2. `claude.md`

Example:

```bash
coderabbit review --plain --type all --base <confirmed-base-branch> --cwd <repo-root> --config AGENTS.md claude.md
```

## Source Hierarchy

Use CodeRabbit as an input, not as the final authority.

- The patch itself is primary.
- CodeRabbit findings are secondary evidence.
- Repository instructions are binding.

You must independently filter, merge, and reword CodeRabbit output before returning findings.

## Review Standard

Report only issues a strong author would likely fix before merging.

Qualifying findings must be:

- Introduced by the patch, or made materially worse by the patch.
- Actionable and specific.
- Supported by the changed code path.
- Important enough to affect merge readiness or near-term follow-up.

Flag findings only when they materially affect:

- Correctness
- Security or privacy
- Reliability or lifecycle safety
- Performance or scalability
- Maintainability, but only when the patch introduces real future defect risk

## Default Exclusions

Do not report these unless the repo instructions explicitly require them or the impact is truly material:

- Style, naming, formatting, and comment cleanup
- Pure refactor suggestions
- Idiomatic-preference feedback tied only to language style
- “Consider using `let`” or similar immutability nits
- Dead commented code unless it hides active behavior
- Placeholder resource cleanup with no user-visible or build impact
- Duplication complaints without a concrete defect risk
- Large parameter lists without a demonstrated maintenance hazard in this patch
- Generic “use structured logging” advice
- Suggestions to replace an API with a more idiomatic language-specific pattern
- Weak memory-leak speculation without a real retention path

By default, suppress CodeRabbit categories such as `nitpick` and `refactor_suggestion`.

Only promote one of those comments into a finding if the explanation demonstrates a real bug or material risk introduced by the patch.

## Materiality Tests

Before keeping any finding, verify all of the following:

1. The issue is in the patch or directly caused by the patch.
2. The failing or risky behavior is plausible, not hypothetical.
3. The severity is meaningful enough that the author should act on it.
4. The finding is not a duplicate of another finding.

If any check fails, drop the finding.

## CodeRabbit Filtering Rules

For each CodeRabbit comment:

1. Classify it as `keep`, `downgrade`, or `drop`.
2. Drop comments that are primarily taste, cleanup, or broad architecture advice.
3. Downgrade comments that are directionally correct but overstated; keep them only if a concrete patch-local risk remains.
4. Merge duplicate comments that describe the same root problem across multiple lines or files.
5. Reword the surviving finding in your own words; do not simply restate CodeRabbit.

Examples of comments that are usually dropped:

- “Consider renaming this key for consistency”
- “Use `let` instead of `var`”
- “Remove commented-out code”
- “Consider a request parameter struct”
- “This could be more idiomatic for the language”

Examples of comments that are often worth keeping if the patch clearly supports them:

- Crash risk from unsafe indexing or force unwraps introduced by the patch
- Broken theme or resource values affecting real UI behavior
- Malformed URL, path, query, or request construction that can fail or misencode input
- Operation lifecycle bugs that can leave async work incomplete
- Corrupted project file entries that can break builds
- Injection or query-construction risk with unsanitized dynamic input
- Missing validation or escaping around user-controlled data

## Deduping Rules

Return one finding per distinct root cause.

- If the same issue appears in multiple CodeRabbit comments, merge them into one finding.
- If one issue causes another downstream symptom, report the root cause only.
- Prefer the smallest line range that proves the issue.
- Avoid repeating the same concern in multiple files unless separate fixes are required.

## Severity Mapping

Use:

- `P0`: merge blocker, certain severe breakage or security impact
- `P1`: high-priority bug or risk likely to cause failure in realistic usage
- `P2`: meaningful but non-urgent defect risk
- `P3`: small but still legitimate issue worth fixing

Do not use `Unmapped`. If severity is too unclear to map, the finding is probably too weak to keep.

## Confidence

Assign a confidence score from `0.0` to `1.0`.

- High confidence requires a direct code-path argument.
- Lower confidence is acceptable only when the issue is still concrete and patch-local.
- Do not keep speculative findings merely to preserve coverage.

## Review Process

Follow this sequence:

1. Run the worktree gate and abort on unstaged changes.
2. Resolve and explicitly confirm the base branch.
3. Run CodeRabbit and wait for completion.
4. Read the diff yourself for any comment you may keep.
5. Filter CodeRabbit output aggressively using the default exclusions and materiality tests.
6. Merge duplicates by root cause.
7. Assign priority and confidence.
8. Decide whether the patch is overall `Correct` or `Incorrect`.

Mark the patch `Incorrect` when at least one finding is serious enough that the author should address it before merge. Otherwise mark it `Correct`.

## Output

Return only the structured Markdown review below. Do not add preamble, notes about process, or any extra sections.

### Summary

- **Overall Verdict**: `Correct` | `Incorrect`
- **Risk Level**: `Low` | `Medium` | `High`
- **Review Source**: `CodeRabbit + manual triage`
- **Confidence**: <0.0-1.0 float>

### Findings

For each issue:

#### [P0|P1|P2|P3] <Title, <=80 chars>

- **File**:
- **Lines**: <start-end>
- **Why this matters**:
- **Confidence**: <0.0-1.0 float>

Rules:

- One section per distinct issue.
- Each explanation must be one short paragraph.
- Use your own wording.
- Include only findings that survive filtering.
- If no qualifying findings remain, output:
  `No qualifying issues found.`

If a tiny replacement snippet is unusually helpful, include one fenced code block with no commentary and at most 3 lines of replacement code.

## Stop Conditions

Stop when any of these occurs:

- Unstaged changes are detected.
- Base-branch confirmation is still pending.
- CodeRabbit authentication or execution fails definitively.
- The review is complete and all surviving findings are listed.

Do not pad the output to match the number of CodeRabbit comments. The goal is a high-signal review, not parity with raw tool output.
