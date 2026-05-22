---
description: Perform a non-destructive cross-artifact consistency and quality analysis across spec.md, plan.md, and tasks.md after task generation.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Pre-Execution Checks

**Check for extension hooks (before analysis)**:
- Check if `.specify/extensions.yml` exists and look for `hooks.before_analyze`
- Filter out hooks where `enabled` is explicitly `false`
- For each executable hook: show optional ones for manual execution; auto-execute mandatory ones and wait for result
- If no hooks or file missing, skip silently

## Goal

Identify inconsistencies, duplications, ambiguities, and underspecified items across `spec.md`, `plan.md`, and `tasks.md` before implementation. This command MUST run only after `/speckit.tasks` has successfully produced a complete `tasks.md`.

## Operating Constraints

**STRICTLY READ-ONLY**: Do **not** modify any files. Output a structured analysis report only. Offer an optional remediation plan (user must explicitly approve before any edits would be made).

**Constitution Authority**: The project constitution (`.specify/memory/constitution.md`) is **non-negotiable**. Constitution conflicts are automatically CRITICAL.

## Execution Steps

### 1. Initialize Analysis Context

Run `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` once from repo root and parse JSON for FEATURE_DIR and AVAILABLE_DOCS. Derive absolute paths:

- SPEC = FEATURE_DIR/spec.md
- PLAN = FEATURE_DIR/plan.md
- TASKS = FEATURE_DIR/tasks.md

Abort with an error message if any required file is missing.

### 2. Load Artifacts

**From spec.md:** Overview/Context, Functional Requirements, Success Criteria, User Stories, Edge Cases

**From plan.md:** Architecture/stack choices, Data Model references, Phases, Technical constraints

**From tasks.md:** Task IDs, Descriptions, Phase grouping, Parallel markers [P], Referenced file paths

**From constitution:** Load `.specify/memory/constitution.md` for principle validation

### 3. Build Semantic Models

- **Requirements inventory**: For each FR-### and SC-### record a stable key
- **Task coverage mapping**: Map each task to one or more requirements or stories
- **Constitution rule set**: Extract principle names and MUST/SHOULD normative statements

### 4. Detection Passes

Focus on high-signal findings. Limit to 50 findings total.

#### A. Duplication Detection
- Near-duplicate requirements; mark lower-quality phrasing for consolidation

#### B. Ambiguity Detection
- Vague adjectives (fast, scalable, secure, intuitive, robust) lacking measurable criteria
- Unresolved placeholders (TODO, TKTK, ???)

#### C. Underspecification
- Requirements with verbs but missing object or measurable outcome
- Tasks referencing files or components not defined in spec/plan

#### D. Constitution Alignment
- Any requirement or plan element conflicting with a MUST principle
- Missing mandated sections or quality gates

#### E. Coverage Gaps
- Requirements with zero associated tasks
- Tasks with no mapped requirement/story
- Success Criteria requiring buildable work not reflected in tasks

#### F. Inconsistency
- Terminology drift (same concept named differently across files)
- Data entities referenced in plan but absent in spec (or vice versa)
- Conflicting requirements

### 5. Severity Assignment

- **CRITICAL**: Violates constitution MUST, missing core spec artifact, requirement with zero coverage blocking baseline functionality
- **HIGH**: Duplicate or conflicting requirement, ambiguous security/performance attribute
- **MEDIUM**: Terminology drift, missing non-functional task coverage
- **LOW**: Style/wording improvements, minor redundancy

### 6. Produce Compact Analysis Report

Output a Markdown report with:

```markdown
## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|

**Coverage Summary Table:**
| Requirement Key | Has Task? | Task IDs | Notes |

**Constitution Alignment Issues:** (if any)

**Unmapped Tasks:** (if any)

**Metrics:**
- Total Requirements / Total Tasks / Coverage % / Ambiguity Count / Critical Issues Count
```

### 7. Provide Next Actions

- If CRITICAL issues exist: Recommend resolving before `/speckit.implement`
- If only LOW/MEDIUM: User may proceed with improvement suggestions
- Provide explicit command suggestions

### 8. Offer Remediation

Ask: "Would you like me to suggest concrete remediation edits for the top N issues?" (Do NOT apply them automatically.)

### 9. Check for extension hooks

After reporting (look for `hooks.after_analyze` in `.specify/extensions.yml`).

## Operating Principles

- **NEVER modify files** (read-only analysis)
- **NEVER hallucinate missing sections** (if absent, report them accurately)
- **Prioritize constitution violations** (always CRITICAL)
- **Report zero issues gracefully** (emit success report with coverage statistics)
