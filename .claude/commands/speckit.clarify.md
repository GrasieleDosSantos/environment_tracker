---
description: Identify underspecified areas in the current feature spec by asking up to 5 targeted clarification questions and encoding answers back into the spec.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Pre-Execution Checks

**Check for extension hooks (before clarification)**:
- Check if `.specify/extensions.yml` exists and look for `hooks.before_clarify`
- Filter out hooks where `enabled` is explicitly `false`
- For each executable hook: show optional ones for manual execution; auto-execute mandatory ones and wait for result
- If no hooks or file missing, skip silently

## Outline

Goal: Detect and reduce ambiguity or missing decision points in the active feature specification and record the clarifications directly in the spec file.

Note: This clarification workflow is expected to run BEFORE invoking `/speckit.plan`. If the user explicitly states they are skipping clarification, warn that downstream rework risk increases.

Execution steps:

1. Run `.specify/scripts/bash/check-prerequisites.sh --json --paths-only` from repo root. Parse `FEATURE_DIR` and `FEATURE_SPEC`. If JSON parsing fails, abort and instruct user to re-run `/speckit.specify`.

2. Load the current spec file. Perform a structured ambiguity & coverage scan across these taxonomy categories (mark each as Clear / Partial / Missing):
   - Functional Scope & Behavior
   - Domain & Data Model
   - Interaction & UX Flow
   - Non-Functional Quality Attributes (performance, scalability, reliability, security)
   - Integration & External Dependencies
   - Edge Cases & Failure Handling
   - Constraints & Tradeoffs
   - Terminology & Consistency
   - Completion Signals

3. Generate (internally) a prioritized queue of up to 5 candidate clarification questions. Only include questions whose answers materially impact architecture, data modeling, task decomposition, test design, UX behavior, or compliance. Do NOT output all at once.

4. Sequential questioning loop (interactive — one question at a time):
   - For multiple-choice questions: show **Recommended** option prominently, then present a Markdown table of options
   - For short-answer questions: show **Suggested** answer with brief reasoning
   - Accept "yes", "recommended", or "suggested" to use your proposed answer
   - Record accepted answers in working memory; do NOT write to disk until question is accepted
   - Stop when: all critical ambiguities resolved, user signals completion ("done", "good"), or 5 questions reached
   - Never reveal future queued questions in advance

5. Integration after EACH accepted answer:
   - Ensure a `## Clarifications` section exists in the spec (create under overview if missing)
   - Under it, create `### Session YYYY-MM-DD` subheading for today
   - Append bullet: `- Q: <question> → A: <final answer>`
   - Apply the clarification to the most appropriate section(s):
     - Functional ambiguity → Functional Requirements
     - Data shape → Data Model
     - Non-functional constraint → Success Criteria (convert vague term to measurable metric)
     - Edge case → Edge Cases section
     - Terminology → normalize term across spec
   - Save the spec file AFTER each integration (atomic overwrite)
   - If a clarification invalidates an earlier statement, replace it rather than duplicating

6. Validation after each write:
   - Clarifications section has exactly one bullet per accepted answer (no duplicates)
   - Total asked (accepted) questions ≤ 5
   - No contradictory earlier statements remain
   - Markdown structure valid

7. Write the updated spec back to `FEATURE_SPEC`.

8. Report completion:
   - Number of questions asked & answered
   - Path to updated spec
   - Sections touched
   - Coverage summary table (Resolved / Deferred / Clear / Outstanding per category)
   - If Outstanding or Deferred remain, recommend whether to proceed to `/speckit.plan` or run `/speckit.clarify` again

## Behavior rules

- If no meaningful ambiguities found, respond: "No critical ambiguities detected worth formal clarification." and suggest proceeding.
- If spec file missing, instruct user to run `/speckit.specify` first.
- Never exceed 5 total questions.
- Respect user early termination signals ("stop", "done", "proceed").

## Post-Execution Checks

**Check for extension hooks** after completion (look for `hooks.after_clarify` in `.specify/extensions.yml`).
