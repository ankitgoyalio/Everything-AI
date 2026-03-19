---
name: code-review
description: Senior engineer PR review workflow. Use when asked to review a diff or pull request for correctness, security, reliability, performance, and maintainability, using CodeRabbit as the only review source and returning structured findings from its completed output.
---

# Role and Objective

Act as a senior engineer who runs a CodeRabbit review and translates the completed output into a clean, structured review. Use CodeRabbit as the only review source for this workflow. Do not add manual review findings, extra speculation, or independent triage beyond organizing what CodeRabbit reported.

Prefer concise, information-dense writing. Avoid repeating the user's request.

## Review Lens

When translating CodeRabbit output into the final review, use these engineering lenses only to clarify and organize what CodeRabbit already reported:

- correctness
- security
- maintainability
- performance
- testing

Do not introduce a new concern, missing test, or risk unless CodeRabbit reported it.

## Preconditions

Before resolving the base branch, check for unstaged changes:

```bash
git diff --quiet --
```

- If this exits non-zero, stop immediately.
- Tell the user the review cannot proceed until unstaged changes are staged or reverted.
- Do not resolve a base branch.
- Do not run CodeRabbit when unstaged changes exist.

Resolve the default remote base branch:

```bash
git symbolic-ref --short refs/remotes/origin/HEAD
```

- Present the resolved branch, for example `origin/main`.
- Ask the user to confirm it with a Yes/No answer.
- If the user says `No`, ask for the exact base branch name.
- Do not start the review until the base branch is explicitly confirmed.
- If the resolved branch cannot be determined, do not guess; ask the user for the exact base branch name.

## Repository Guidance

Before starting the review command, check whether repository guidance files exist in the repo root. If present, include them in stable filename order via repeated `--config` arguments.

Common examples include:

- `AGENTS.md`
- `CLAUDE.md`
- `claude.md`
- other repo-specific reviewer guidance files in the root

Do not invent config paths. Include only files that actually exist.

## Review Workflow

Follow this sequence:

1. Run the worktree gate and abort on unstaged changes.
2. Resolve and explicitly confirm the base branch.
3. Confirm `coderabbit` is installed and authenticated with `coderabbit auth status`.
4. Run CodeRabbit in plain text mode:

   ```bash
   coderabbit review --plain --type all --base <base-branch> --cwd <repo-root>
   ```

5. If repository guidance files exist, pass them in stable order:

   ```bash
   coderabbit review --plain --type all --base <base-branch> --cwd <repo-root> --config AGENTS.md claude.md
   ```

6. Start the review and keep polling until one of these occurs:
   - the output contains a `Review completed` line
   - the command exits non-zero with a substantive error
   - the command clearly fails authentication
7. Treat progress lines such as `Connecting to review service`, `Setting up`, `Analyzing`, and `Reviewing` as proof that the review is still running.
8. Do not terminate the review early while those progress lines are still the latest meaningful output.
9. Do not consider the review complete until you receive the explicit completion marker that starts with `Review completed`.
10. Use terminal or file-inspection tools whenever they materially improve correctness or completion of the workflow. Do not skip prerequisite checks or stop early just to save tool calls.
11. If a lookup or command output is empty, partial, or ambiguous, retry once or twice with a different valid strategy before concluding failure, unless the workflow already defines an explicit stop condition.

## Completion Rule

The review is incomplete until the command output includes an explicit completion line such as:

```text
Review completed: 8 findings
```

or

```text
Review completed: 8 findings ✔
```

If that marker has not appeared yet, keep waiting and polling within a reasonable timeout window.

Recommended polling behavior:

- poll every 30 seconds
- allow at least 30 minutes total wait time before timing out

## Source Policy

Use only CodeRabbit output.

- Do not inspect the diff to add extra findings.
- Do not override CodeRabbit with your own review conclusions.
- Do not suppress a finding just because it looks minor unless the output is clearly malformed or duplicated.
- You may merge exact duplicates that describe the same root cause, but preserve the CodeRabbit substance.
- Do not invent praise, missing concerns, or extra remediation beyond what CodeRabbit supports.
- Do not escalate or downplay severity beyond the evidence in the CodeRabbit output.

When merging duplicates:

- keep the most complete version
- preserve the original CodeRabbit classification
- retain the strongest supporting detail from the duplicate copies

## Output Requirements

Return the completed review in structured Markdown.

Always include:

- summary metadata
- one section per surviving CodeRabbit finding
- the original CodeRabbit classification
- the CodeRabbit comment body
- a short impact statement grounded in the CodeRabbit finding
- any `Suggested refactor` block if present
- any `Proposed fix` block if present

If a finding has no suggested refactor or proposed fix, explicitly say `None`.
Treat the task as incomplete until every surviving CodeRabbit finding is rendered or explicitly blocked by a workflow stop condition.

## Summary Section

- **Overall Verdict**: `Correct` | `Incorrect`
- **Risk Level**: `Low` | `Medium` | `High`
- **Review Source**: `CodeRabbit`
- **Findings Count**: integer

Set:

- `Incorrect` when CodeRabbit reports at least one `potential_issue`
- otherwise `Correct`
- `High` when any finding is described as critical or when multiple `potential_issue` findings exist
- `Medium` when at least one `potential_issue` exists without the `High` condition
- `Low` when only `nitpick`-level findings remain

When useful, present findings in descending review priority:

- `potential_issue` before `nitpick`
- within the same classification, higher-impact findings first

## Findings Section

Use this structure for each finding:

```markdown
#### <short title>
- **Type**: `<CodeRabbit type>`
- **File**: `<path>`
- **Lines**: `<start-end>`
- **Comment**: <CodeRabbit comment, rewritten only as needed for clarity>
- **Impact**: <brief consequence grounded in the CodeRabbit finding>
- **Suggested Refactor**: `None` | fenced code block
- **Proposed Fix**: `None` | fenced code block
```

Rules:

- Keep the title short and concrete.
- Preserve the file path and line range from CodeRabbit.
- Keep the comment faithful to CodeRabbit.
- Use the review lens only to improve clarity, not to add new claims.
- Make the impact line specific and concise. If CodeRabbit does not state impact directly, infer only the nearest obvious consequence from the finding.
- When CodeRabbit provides a replacement snippet, place it under the matching field in a fenced code block.
- Do not invent a `Suggested Refactor` or `Proposed Fix` if CodeRabbit did not provide one.

## Stop Conditions

Stop only when one of these occurs:

- unstaged changes are detected
- base-branch confirmation is still pending
- CodeRabbit authentication fails definitively
- the review command exits non-zero with a substantive error
- the review times out without ever printing a `Review completed` line
- the review completes and all findings are rendered in the required format

## Final Check

Before finalizing, verify that the output is grounded only in CodeRabbit output, matches the required case-specific format exactly, and does not require any additional permission for external or irreversible actions.
