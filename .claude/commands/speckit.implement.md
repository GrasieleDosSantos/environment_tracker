---
description: Execute the implementation plan by processing and executing all tasks defined in tasks.md.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Pre-Execution Checks

**Check for extension hooks (before implementation)**:
- Check if `.specify/extensions.yml` exists and look for `hooks.before_implement`
- Filter out hooks where `enabled` is explicitly `false`
- For each executable hook: show optional ones for manual execution; auto-execute mandatory ones and wait for result
- If no hooks or file missing, skip silently

## Outline

1. Run `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` from repo root and parse FEATURE_DIR and AVAILABLE_DOCS list. All paths must be absolute.

2. **Check checklists status** (if FEATURE_DIR/checklists/ exists):
   - Scan all checklist files and count completed vs incomplete items
   - Display a status table: `| Checklist | Total | Completed | Incomplete | Status |`
   - **If any checklist is incomplete**: STOP and ask "Some checklists are incomplete. Do you want to proceed with implementation anyway? (yes/no)"
   - **If all checklists are complete**: Automatically proceed to step 3

3. Load and analyze the implementation context:
   - **REQUIRED**: tasks.md and plan.md
   - **IF EXISTS**: data-model.md, contracts/, research.md, .specify/memory/constitution.md, quickstart.md

4. **Project Setup Verification**:
   - Verify/create ignore files based on project type (.gitignore, .dockerignore, etc.)
   - Check if files already exist before creating; append missing patterns only

5. Parse tasks.md and extract task phases, dependencies, task IDs, descriptions, file paths, and parallel markers [P].

6. Execute implementation following the task plan:
   - **Phase-by-phase execution**: Complete each phase before moving to the next
   - **Respect dependencies**: Run sequential tasks in order; parallel tasks [P] can run together
   - **File-based coordination**: Tasks affecting the same files must run sequentially
   - **Validation checkpoints**: Verify each phase completion before proceeding

7. Implementation execution rules:
   - **Setup first**: Initialize project structure, dependencies, configuration
   - **Core development**: Implement models, services, CLI commands, endpoints
   - **Integration work**: Database connections, middleware, logging, external services
   - **Polish and validation**: Tests, performance optimization, documentation

8. Progress tracking:
   - Report progress after each completed task
   - Halt execution if any non-parallel task fails
   - For parallel tasks [P], continue with successful tasks, report failed ones
   - **IMPORTANT**: Mark each completed task as `[X]` in tasks.md

9. Completion validation:
   - Verify all required tasks are completed
   - Check that implemented features match the original specification
   - Confirm the implementation follows the technical plan
   - Report final status with summary of completed work

Note: If tasks.md is incomplete or missing, run `/speckit.tasks` first.

10. **Check for extension hooks** after completion (look for `hooks.after_implement` in `.specify/extensions.yml`).
