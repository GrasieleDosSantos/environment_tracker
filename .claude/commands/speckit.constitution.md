---
description: Create or update the project constitution, ensuring all dependent templates stay in sync.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Pre-Execution Checks

**Check for extension hooks (before constitution update)**:
- Check if `.specify/extensions.yml` exists and look for `hooks.before_constitution`
- Filter out hooks where `enabled` is explicitly `false`
- For each executable hook: show optional ones for manual execution; auto-execute mandatory ones and wait for result
- If no hooks or file missing, skip silently

## Outline

You are updating the project constitution at `.specify/memory/constitution.md`. This file is a TEMPLATE containing placeholder tokens in square brackets (e.g. `[PROJECT_NAME]`, `[PRINCIPLE_1_NAME]`). Your job is to (a) collect/derive concrete values, (b) fill the template precisely, and (c) propagate any amendments across dependent artifacts.

**Note**: If `.specify/memory/constitution.md` does not exist yet, copy `.specify/templates/constitution-template.md` first.

Follow this execution flow:

1. Load the existing constitution at `.specify/memory/constitution.md`.
   - Identify every placeholder token of the form `[ALL_CAPS_IDENTIFIER]`.
   - **IMPORTANT**: The user might require less or more principles than the ones in the template. Respect that number and update the doc accordingly.

2. Collect/derive values for placeholders:
   - If user input supplies a value, use it.
   - Otherwise infer from existing repo context (README, docs, prior constitution versions).
   - For governance dates: `RATIFICATION_DATE` is the original adoption date; `LAST_AMENDED_DATE` is today if changes are made.
   - `CONSTITUTION_VERSION` must increment according to semantic versioning:
     - MAJOR: Backward incompatible governance/principle removals or redefinitions
     - MINOR: New principle/section added or materially expanded guidance
     - PATCH: Clarifications, wording, typo fixes

3. Draft the updated constitution content:
   - Replace every placeholder with concrete text (no bracketed tokens left)
   - Ensure each Principle section has: succinct name, rules, explicit rationale
   - Ensure Governance section lists amendment procedure, versioning policy, and compliance review

4. Consistency propagation checklist:
   - Read `.specify/templates/plan-template.md` and ensure "Constitution Check" aligns with updated principles
   - Read `.specify/templates/spec-template.md` for scope/requirements alignment
   - Read `.specify/templates/tasks-template.md` and ensure task categorization reflects new/removed principle-driven task types
   - Read any runtime guidance docs (README.md, quickstart.md) and update references to changed principles

5. Produce a Sync Impact Report (prepend as HTML comment at top of constitution file):
   - Version change: old → new
   - List of modified principles
   - Added/removed sections
   - Templates requiring updates (✅ updated / ⚠ pending)
   - Follow-up TODOs for deferred placeholders

6. Validation before final output:
   - No remaining unexplained bracket tokens
   - Version line matches report
   - Dates in ISO format YYYY-MM-DD
   - Principles are declarative and free of vague language

7. Write the completed constitution back to `.specify/memory/constitution.md` (overwrite).

8. Output a final summary with:
   - New version and bump rationale
   - Any files flagged for manual follow-up
   - Suggested commit message

## Post-Execution Checks

**Check for extension hooks** after completion (look for `hooks.after_constitution` in `.specify/extensions.yml`).
