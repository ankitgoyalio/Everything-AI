# Skill Creator

This guide outlines best practices for building effective Skills—modular packages that extend AI Chatbot functionality with specialized workflows, knowledge, and tools.

## About Skills

Skills are self-contained packages that optimize and specialize AI Chatbot behavior for specific domains or tasks. They transform the agent into a domain expert, supplying procedural and domain-specific capabilities that pretrained models alone lack.

### What Skills Provide

1. **Specialized workflows:** Multi-step procedures for targeted domains
2. **Tool integrations:** File formats, scripts, or APIs
3. **Domain expertise:** Company knowledge, schemas, business logic
4. **Bundled resources:** Scripts, references, or assets for complex/repetitive tasks

## Core Principles

### Conciseness

Skills share a finite context window with other system components. Only include context missing from the Chatbot. Justify each addition’s token cost, and favor concise examples over lengthy explanations.

### Calibrate Degrees of Freedom

Match instruction specificity to task requirements:

-   **High freedom:** Text instructions for flexible, context-dependent tasks
-   **Medium freedom:** Pseudocode or scripts with configurable parameters
-   **Low freedom:** Concrete scripts with minimal parameters for strict or fragile tasks

Apply these levels to set appropriate guardrails or allow flexibility as needed.

### Anatomy of a Skill

Each skill must have a `SKILL.md` file and may contain:

```
skill-name/
├── SKILL.md           (required)
│   ├── YAML frontmatter (name, description required)
│   └── Markdown instructions (procedures, guidance)
├── scripts/           (optional – executable code)
├── references/        (optional – documentation loaded as needed)
└── assets/            (optional – output files: templates, icons, etc.)
```

#### SKILL.md (required)

-   **Frontmatter (YAML):**
    -   `name`: the skill’s name
    -   `description`: what the skill does and when the AI Chatbot should use it
-   **Body (Markdown):**
    -   Instructions and procedural guidance; loaded after the skill is triggered

#### Bundled Resources (optional)

-   **Scripts:** Deterministic code (e.g., `rotate_pdf.py`)—include if code reuse or reliability is important
-   **References:** Documentation (schemas, policies, guides); keep SKILL.md lean, centralize details here. For files >10k words, add grep search patterns in SKILL.md. Avoid duplicating information.
-   **Assets:** Files for outputs (e.g., templates), not loaded into context

**Do not include extra files** such as `README.md` or installation guides. Only add files directly supporting skill execution.

### Progressive Disclosure

Skills manage context via three levels:

1. **Metadata**: name + description (~100 words)
2. **SKILL.md body**: workflows/procedures (<5k words)
3. **Bundled resources**: loaded as needed

**Reference patterns:**

-   Keep core workflows in SKILL.md, link variants as references.
-   Separate references by domain or framework; organize and link from SKILL.md with usage notes.
-   For large references (>100 lines), include a table of contents for orientation.

## Skill Creation Process

Follow these steps:

1. **Clarify requirements with concrete examples**
2. **Plan reusable contents**
3. **Initialize the skill (scaffold, add stubs)**
4. **Edit the skill (implement, clarify, prune resources)**
5. **Package the skill (.skill ZIP file)**
6. **Iterate based on real usage feedback**

> **Note:** Skip steps only if obviously unnecessary. All resources should serve execution, not just documentation.

### Step Details

#### Step 1: Clarifying Examples

Collect concrete use cases. Limit questions to avoid overwhelming stakeholders. Confirm supported functionality before continuing.

#### Step 2: Planning

For each example, note needed code, documentation, and assets. List resources before developing them.

#### Step 3: Initialization

Scaffold the directory structure, SKILL.md (with required fields), and placeholder resource folders/files. Adjust or remove irrelevant stubs.

#### Step 4: Editing

-   Remember: target audience is other AI Chatbot instances
-   Include non-obvious workflows or references
-   Use supporting guides as needed
-   Implement reusable resources and involve users for assets/references when needed
-   Test at least a representative set of scripts
-   Remove unused examples

**SKILL.md authoring:**

-   Frontmatter: only `name` and `description`. State triggers and purpose in the description.
-   Body: stepwise usage and resource documentation, using imperative or infinitive tense.

#### Step 5: Packaging

Run the packaging script:

-   **Validation:** YAML frontmatter, structure, description quality, organization, and references
-   **Packaging:** Generates a `.skill` file (ZIP format) if valid. Fix errors and retry if not.

#### Step 6: Iterate

After use, resolve workflow issues and update SKILL.md or resources as needed.
