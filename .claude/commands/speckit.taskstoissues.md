---
description: Convert existing tasks.md into GitHub issues for the feature repository.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Pre-Execution Checks

**Check for extension hooks (before tasks-to-issues conversion)**:
- Check if `.specify/extensions.yml` exists and look for `hooks.before_taskstoissues`
- Filter out hooks where `enabled` is explicitly `false`
- For each executable hook: show optional ones for manual execution; auto-execute mandatory ones and wait for result
- If no hooks or file missing, skip silently

## Outline

1. Run `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` from repo root and parse FEATURE_DIR and AVAILABLE_DOCS list. All paths must be absolute.

2. From the executed script, extract the path to **tasks.md**.

3. Get the Git remote by running:
   ```bash
   git config --get remote.origin.url
   ```

   > **CAUTION**: ONLY PROCEED IF THE REMOTE IS A GITHUB URL.

4. For each task in tasks.md, create a GitHub issue using the `gh` CLI:
   ```bash
   gh issue create --title "T### Description" --body "..."
   ```
   Use the task ID, description, phase, and any file paths as issue content.

   > **CAUTION**: UNDER NO CIRCUMSTANCES CREATE ISSUES IN REPOSITORIES THAT DO NOT MATCH THE REMOTE URL.

## Post-Execution Checks

**Check for extension hooks** after completion (look for `hooks.after_taskstoissues` in `.specify/extensions.yml`).
