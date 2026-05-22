---
description: Generate a custom requirements-quality checklist for the current feature. Checklists are "unit tests for requirements" — they validate the quality, clarity, and completeness of requirements, not the implementation.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Pre-Execution Checks

**Check for extension hooks (before checklist generation)**:
- Check if `.specify/extensions.yml` exists and look for `hooks.before_checklist`
- Filter out hooks where `enabled` is explicitly `false`
- For each executable hook: show optional ones for manual execution; auto-execute mandatory ones and wait for result
- If no hooks or file missing, skip silently

## Checklist Purpose: "Unit Tests for English"

**CRITICAL CONCEPT**: Checklists validate the quality, clarity, and completeness of REQUIREMENTS — not the implementation.

- ❌ NOT "Verify the button clicks correctly"
- ❌ NOT "Test error handling works"
- ✅ "Are visual hierarchy requirements defined for all card types?" (completeness)
- ✅ "Is 'prominent display' quantified with specific sizing/positioning?" (clarity)

## Execution Steps

1. **Setup**: Run `.specify/scripts/bash/check-prerequisites.sh --json` from repo root and parse JSON for FEATURE_DIR and AVAILABLE_DOCS list.

2. **Clarify intent**: Derive up to 3 contextual clarifying questions (generated from user phrasing + spec/plan signals). Ask only if the answer materially changes checklist content. Ask Q4/Q5 only if ≥2 high-impact areas remain unresolved; never exceed 5 total.

3. **Understand user request**: Combine `$ARGUMENTS` + clarifying answers to derive checklist theme, must-have items, and focus areas.

4. **Load feature context**: Read spec.md, plan.md (if exists), tasks.md (if exists) — load only portions relevant to active focus areas.

5. **Generate checklist**:
   - Create `FEATURE_DIR/checklists/` if it doesn't exist
   - Use short, descriptive filename based on domain (e.g., `ux.md`, `api.md`, `security.md`)
   - If file does NOT exist: create new file, start IDs at CHK001
   - If file exists: append new items, continuing from the last CHK ID
   - Never delete or replace existing content

   **CORE PRINCIPLE**: Every item MUST evaluate REQUIREMENTS THEMSELVES for completeness, clarity, consistency, measurability, and coverage.

   **Item format**:
   ```
   - [ ] CHK### Question about requirement quality [Dimension, Spec §X.Y or Gap/Ambiguity/Conflict]
   ```

   **Required patterns**:
   - ✅ "Are [requirement type] defined/specified/documented for [scenario]?"
   - ✅ "Is [vague term] quantified/clarified with specific criteria?"
   - ✅ "Are requirements consistent between [section A] and [section B]?"
   - ✅ "Can [requirement] be objectively measured/verified?"

   **Absolutely prohibited**:
   - ❌ Items starting with "Verify", "Test", "Confirm" + implementation behavior
   - ❌ References to code execution, user actions, system behavior
   - ❌ Implementation details (frameworks, APIs, algorithms)

   **Category structure**:
   - Requirement Completeness
   - Requirement Clarity
   - Requirement Consistency
   - Acceptance Criteria Quality
   - Scenario Coverage
   - Edge Case Coverage
   - Non-Functional Requirements
   - Dependencies & Assumptions
   - Ambiguities & Conflicts

   Minimum 80% of items must include a traceability reference (`[Spec §X.Y]`, `[Gap]`, `[Ambiguity]`, `[Conflict]`, or `[Assumption]`).

6. **Structure**: Follow `.specify/templates/checklist-template.md` for title, meta section, category headings, and ID formatting.

7. **Report**: Output full path to checklist file, item count, whether it was created or appended, focus areas selected, and depth level.

## Post-Execution Checks

**Check for extension hooks** after completion (look for `hooks.after_checklist` in `.specify/extensions.yml`).
