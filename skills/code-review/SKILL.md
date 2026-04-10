---
name: code-review
description: Deterministic CodeRabbit review workflow for reviewing a diff, branch, or pull request. Use when asked to review code, run CodeRabbit, summarize findings, or turn CodeRabbit plain-text output into a Markdown report with the bundled scripts.
---

# Code Review

Run CodeRabbit through the bundled script so the workflow stays deterministic.

Use CodeRabbit as the only review source for findings. Do not add manual findings, speculative risks, or diff-based conclusions of your own.

## Available Script

- `scripts/coderabbit_review.py`
    - `review`: preflight checks, scope selection, optional base resolution, CodeRabbit plain-text execution, artifact generation
    - `render`: convert the normalized JSON artifact into the required Markdown report

Resolve that path from the skill directory, not from the repository being reviewed.

Do not assume the target repository contains `scripts/coderabbit_review.py`.

`review` writes these artifacts into `--output-dir`:

- `progress.json`: current wrapper state for polling long-running reviews
- `normalized.json`: normalized wrapper artifact with metadata and captured CodeRabbit output
- `report.md`: rendered Markdown report when available
- `coderabbit.stdout.log`: raw CodeRabbit stdout stream
- `coderabbit.stderr.log`: raw CodeRabbit stderr stream

Run `python3 <skill-dir>/scripts/coderabbit_review.py --help` or `python3 <skill-dir>/scripts/coderabbit_review.py review --help` if you need the exact interface.

## Required Workflow

1. Create a temporary artifact directory.
2. Run the deterministic review script against the repository the user wants reviewed.
3. If the review is long-running or launched in the background, poll `progress.json` in the artifact directory instead of rerunning the command.
4. If `progress.json` reaches `state: "artifacts_ready"` or `review` returns `status: "ok"`, run `render` on the normalized artifact.
5. If `progress.json` reaches `state: "error"` or `state: "timed_out"`, report the wrapper failure and include the artifact paths it produced.
6. Return the rendered Markdown to the user when available.

Reference flow:

```bash
ARTIFACT_DIR="$(mktemp -d)"
python3 <skill-dir>/scripts/coderabbit_review.py review \
  --repo "$PWD" \
  --output-dir "$ARTIFACT_DIR"
python3 <skill-dir>/scripts/coderabbit_review.py render \
  --input "$ARTIFACT_DIR/normalized.json"
```

When polling:

- prefer `progress.json` over terminal-session liveness
- do not start a second review if the first run's `progress.json` is still updating
- treat `state: "artifacts_ready"` as the success signal for rendering
- if `state: "running"`, the task is still in progress and you must keep polling the same artifact directory
- while `state: "running"`, do not return a status-only final answer and do not summarize intermediate wrapper state unless the user explicitly asks for progress
- only stop polling when the state becomes `artifacts_ready`, `error`, or `timed_out`

## Scope Rules

Prefer explicit scope from the user:

- review local WIP or unstaged work: `--scope uncommitted`
- review committed branch changes: `--scope committed`
- otherwise let the script choose with `--scope auto`

Use `--base <branch>` only when branch comparison matters or the user explicitly names a base branch.

Only pass `--config <path>` when the user explicitly names additional instruction files that exist. Do not scan the repository and invent config arguments for auto-detected guideline files.

## Preconditions

The script already enforces the required checks:

- inside a Git repository
- `HEAD` resolves
- `coderabbit` exists on `PATH`
- `coderabbit auth status --agent` succeeds

If preflight fails, stop and report the script's error. Do not run manual fallback review logic.

## Output Contract

Return the rendered Markdown report produced by `render`.

The report contains:

- summary metadata
- the captured CodeRabbit plain-text review when available
- structured finding sections only if CodeRabbit emits machine-readable findings despite the plain-text request

If the normalized report contains zero structured findings but includes plain-text review output, return that result directly. Do not add extra concerns.

## Source Policy

- Use only CodeRabbit output for findings.
- Do not inspect the diff to add new findings.
- Do not override or suppress findings unless they are exact duplicates merged by the script.
- Keep any explanation faithful to the normalized CodeRabbit output.
