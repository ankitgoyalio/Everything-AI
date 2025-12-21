# Generate an AGENTS.md

## Role

You are a senior staff software engineer and “coding-agent wrangler.” Write clear, operational documentation for coding agents and human reviewers. Maintain strict scope control, safeguard the repository, and ensure reproducibility.

## Task

Create an `AGENTS.md` file for this codebase defining:

-   Agent permissions and prohibitions
-   Required workflow (planning, implementation, testing, explanation)
-   Standards and quality gates (tests, patterns, style, PR hygiene)
-   How agents should ask clarifying questions and stop if uncertain

### Critical Requirement (must appear first in the file)

Before any repo-specific rules, `AGENTS.md` must require the agent to ask:

-   “Is this a single repo or a monorepo?”
    And update guidance accordingly.

## Context

Apply the following fixed constraints:

### Allowed Actions

-   Agents may modify code and refactor architecture
-   Agents may use `git`, test runners, linters, and formatters

### Hard Prohibitions

Agents must never:

-   Add, remove, or change dependencies (including any package manager changes, lockfiles, Podfile, SPM package, etc.)
-   Edit .env files or secrets
-   Modify CI/CD configuration files (e.g., GitHub Actions, Bitrise, CircleCI, Jenkins, etc.)

If a task requires a prohibited action, the agent must stop and request human approval.

### Quality Requirements (Mandatory)

-   Always add or update tests for code changes (or explain and seek guidance if not possible)
-   Clearly explain changes for human reviewers
-   Prioritize existing repository patterns over external “best practices”
-   When uncertain, stop and ask; do not assume

### Audience

`AGENTS.md` must serve:

-   Coding agents
-   Human reviewers

## Reasoning

Internally validate that `AGENTS.md`:

-   Requires “single repo vs monorepo” prompt first
-   States permissions and prohibitions clearly
-   Provides a workflow mandating tests, explanations, repository pattern adherence
-   Contains stop/ask rules for uncertainty and prohibited actions
-   Supplies concrete, actionable steps

## Output

Return only the `AGENTS.md` Markdown content.

### Format Rules

-   Use descriptive headings and bullet lists
-   Include a concise “Quick Start for Agents” section
-   Include an “Allowed / Not Allowed” section with explicit examples
-   Add a “Workflow Checklist” for every agent task
-   Add a “When to Stop and Ask” section with specific examples
-   Add a “Testing & Verification” section specifying expected behaviors. If commands or tools are `Unknown`, require agents to ask the user or inspect the repo; never guess.

## Stop Conditions

Completion is achieved when:

-   The complete `AGENTS.md` file is present
-   All constraints are included
-   No placeholders remain except “Unknown” fields, labeled with “ask or inspect” guidance
-   No commentary is present beyond the `AGENTS.md` Markdown content
