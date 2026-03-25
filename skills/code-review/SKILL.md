---
name: code-review
description: Senior engineer PR review workflow. Use when asked to review a diff or pull request for correctness, security, reliability, performance, and maintainability, using CodeRabbit as the only review source and returning structured findings from its completed output.
---

# Role and Objective

Act as a senior engineer who runs a CodeRabbit review and translates the completed output into a clean, structured review.

Use CodeRabbit as the only review source for findings. Do not add manual findings, speculative risks, or independent triage beyond organizing what CodeRabbit reported.

Prefer concise, information-dense writing. Avoid repeating the user's request.

## Review Lens

Use these lenses only to organize or clarify what CodeRabbit already reported:

- correctness
- security
- maintainability
- performance
- testing

Do not introduce a new concern, missing test, or risk unless CodeRabbit reported it.

## CLI Facts

Ground the workflow in the documented CLI behavior:

- `coderabbit review` is the review command.
- `--plain` produces detailed plain-text feedback.
- `--prompt-only` produces minimal output optimized for AI agents and implies `--plain`.
- `--type` accepts `all`, `committed`, or `uncommitted`. The documented default is `all`.
- `--config <files...>` accepts one or more existing instruction files.
- `--base <branch>` sets the comparison branch.
- `--cwd <path>` must point to an initialized Git repository.
- `coderabbit auth status` shows authentication status.

For this skill, prefer `coderabbit review --plain` because the final deliverable is a structured Markdown report that needs the detailed findings, not the minimal agent prompt.

Use `--prompt-only` only when the user explicitly asks for agent-optimized minimal output instead of a full rendered review.

## Preconditions

Verify repository state before starting the review:

```bash
git rev-parse --is-inside-work-tree >/dev/null
git rev-parse --verify HEAD >/dev/null 2>&1
command -v coderabbit >/dev/null
coderabbit auth status
```

If any of these fail:

- stop immediately
- report the specific failing precondition
- do not start CodeRabbit

## Review Scope

Choose review scope from the user's request first, then from repository state:

- if the user asks to review local WIP, unstaged work, or uncommitted changes, use `--type uncommitted`
- if the user asks to review committed branch changes or a branch diff against a base branch, use `--type committed`
- otherwise use the documented default `--type all`

Do not block just because unstaged changes exist. CodeRabbit explicitly supports `--type uncommitted` and `--type all`.

Use `git status --short` to understand current state when the scope is ambiguous.

Important limitation from CodeRabbit docs:

- CodeRabbit analyzes tracked changes
- if the repo has only untracked files and no tracked changes, warn the user that the review may return no findings

## Base Branch Rules

Only use `--base` when branch comparison matters for the requested review.

Base branch selection order:

1. If the user gave a base branch, use it.
2. Otherwise, if `git symbolic-ref --quiet --short refs/remotes/origin/HEAD` succeeds, use that resolved remote default branch.
3. Otherwise, omit `--base` and let the CLI use its default behavior unless the user explicitly asked for a branch-to-branch comparison.

When a base branch is chosen, verify it resolves before starting the review:

```bash
git rev-parse --verify --quiet "<base-branch>^{commit}" >/dev/null
```

If the requested branch does not resolve:

- stop and report that exact branch name
- do not guess a replacement branch

Do not force a Yes/No confirmation step when base branch resolution is straightforward.
Only ask the user when the requested review depends on a specific base branch and no reliable branch can be resolved locally.

## Repository Guidance Files

CodeRabbit documents `--config <files...>` for additional instructions. Only pass files that actually exist.

Search the repo root only. Use this allowlist in stable filename order:

- `AGENTS.md`
- `CLAUDE.md`
- `claude.md`

Also include any extra guidance file the user explicitly names.

Pass guidance files with the documented variadic form:

```bash
coderabbit review --plain --config AGENTS.md claude.md
```

Do not invent guidance files or search arbitrary subdirectories.

## Review Workflow

Follow this sequence:

1. Verify Git repo, `HEAD`, CLI availability, and authentication.
2. Determine review scope and choose `--type`.
3. Resolve and validate `--base` only when needed.
4. Discover root guidance files and build the optional `--config <files...>` argument.
5. Start exactly one `coderabbit review` process for this invocation.
6. Poll until the process exits, a definitive auth/service failure is reported, or the workflow timeout is reached.
7. Render the completed findings in the required Markdown format.

Reference command:

```bash
coderabbit review --plain --type <all|committed|uncommitted> --cwd <repo-root> [--base <branch>] [--config <files...>]
```

## Re-entry and Polling

Keep this skill lightweight, but do not start duplicate reviews unnecessarily.

- If you already started a `coderabbit review` process for the current user request and it is still running, reuse that running process instead of launching another one.
- Do not launch a replacement review just because no new output appeared yet.
- Poll periodically and surface the latest meaningful progress or findings.
- Treat long runtimes as normal. CodeRabbit documents that reviews may take 7 to 30+ minutes depending on scope.

Recommended polling behavior:

- run the review in a way that lets you keep checking output
- poll roughly every 30 seconds
- allow at least 30 minutes before declaring a timeout

## Completion and Failure Rules

Do not require one exact literal success line.

Treat the review as complete when either of these is true:

- CodeRabbit prints an explicit completion line such as `Review completed ...`
- the review process exits successfully and the output contains the findings needed to render the report

Treat the review as failed or blocked when any of these occurs:

- `coderabbit` is missing from `PATH`
- `coderabbit auth status` fails or reports an authentication problem
- the chosen `--cwd` is not a Git repository
- the selected base branch does not resolve
- the review command exits non-zero with a substantive error
- output clearly indicates a network, service, or rate-limit failure
- the review times out before enough output exists to render the report

If the command fails, report the last relevant CodeRabbit output lines. Do not silently retry in a loop.

## Source Policy

Use only CodeRabbit output for findings.

- Do not inspect the diff to add extra findings.
- Do not override CodeRabbit with your own review conclusions.
- Do not suppress a finding just because it looks minor unless the output is clearly malformed or duplicated.
- You may merge exact duplicates that describe the same root cause, while preserving the original substance.
- Do not invent praise, missing concerns, or extra remediation beyond what CodeRabbit supports.
- Do not escalate or downplay severity beyond what CodeRabbit output supports.

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

If CodeRabbit reports no findings, still render the summary with `Findings Count: 0` and state that no surviving findings were reported.

## Summary Section

- **Overall Verdict**: `Correct` | `Incorrect`
- **Risk Level**: `Low` | `Medium` | `High`
- **Review Source**: `CodeRabbit`
- **Findings Count**: integer

Set:

- `Incorrect` when CodeRabbit reports at least one issue-class finding such as `potential_issue`
- otherwise `Correct`
- `High` when CodeRabbit reports multiple issue-class findings or marks a finding as critical/high severity
- `Medium` when CodeRabbit reports one issue-class finding and no high-severity condition applies
- `Low` when only low-severity classifications remain, such as `nitpick`, `style`, or `info`

If CodeRabbit uses an unfamiliar classification, preserve it exactly in the finding and use the nearest conservative risk mapping supported by the output text.

When useful, present findings in descending review priority:

- issue-class findings before nits or informational items
- within the same class, higher-impact findings first when CodeRabbit output supports that ordering

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
- Make the impact line specific and concise. Infer only the nearest obvious consequence already supported by the CodeRabbit finding.
- When CodeRabbit provides a replacement snippet, place it under the matching field in a fenced code block.
- Do not invent a `Suggested Refactor` or `Proposed Fix` if CodeRabbit did not provide one.

## Stop Conditions

Stop only when one of these occurs:

- a required precondition fails
- the requested base branch cannot be resolved
- CodeRabbit authentication or CLI availability fails definitively
- the review command exits non-zero with a substantive error
- the review reports a network, service, or rate-limit failure that prevents completion
- the review times out before producing enough output to render the report
- the review completes and all surviving findings are rendered in the required format

## Final Check

Before finalizing, verify that the review:

- is grounded only in CodeRabbit output
- uses documented CLI commands and flags
- matches the required output format
- does not require the user to open a separate file to see the findings
