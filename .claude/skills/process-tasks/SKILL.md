# Skill: process-tasks

## Purpose

Process all pending task files in `Needs_Action/` through the complete Bronze Tier lifecycle: validate, reason, execute, complete, archive, and update system state. The cycle ends when `Needs_Action/` is empty.

## Execution Steps

1. Read `Company_Handbook.md` to load current operational policies.
2. List all `.md` files in `Needs_Action/` (exclude hidden files and `.gitkeep`).
3. If no task files exist, report no pending tasks and stop.
4. For each task file, invoke the `validate-task-schema` skill logic:
   - Check for required frontmatter fields: `type`, `priority`, `status`, `created`, `source`.
   - Check for required sections: `## Task Description`, `## Required Outcome`, `## Processing Checklist` with at least one `- [ ]` item.
   - If validation fails: leave the file in `Needs_Action/`, log an alert in `Dashboard.md` under `## Alerts` with the filename and missing fields/sections, skip to the next file.
5. Sort all valid tasks by `priority` (high → medium → low), then by `created` timestamp (oldest first).
6. For each valid task in sorted order:
   a. Read the full file content.
   b. Parse `## Task Description` and `## Required Outcome`.
   c. Reason through the objective and produce a concrete result satisfying the Required Outcome.
   d. Write the result into the task file under a new `## Result` section placed before `## Processing Checklist`.
   e. Mark every checklist item from `- [ ]` to `- [x]`.
   f. Add a `## Completion Notes` section at the end with a summary of actions taken and a UTC ISO 8601 completion timestamp.
   g. Change `status: pending` to `status: completed` in the YAML frontmatter.
   h. Move the file from `Needs_Action/` to `Done/`.
   i. Update `Dashboard.md`: add a timestamped entry under `## Recent Activity`, update pending/completed counts in `## System Status`, set `Last Execution` to current UTC timestamp.
7. After all tasks are processed, confirm `Needs_Action/` contains no pending `.md` files.

## Constraints

- Operate only within the vault root directory. Never read or write files outside it.
- Follow all policies defined in `Company_Handbook.md`.
- Do not modify `watcher.py`, `backup.sh`, or `Company_Handbook.md`.
- Do not delete any file from `Done/`. Completed tasks are permanent.
- Do not skip any task. If a task cannot be completed, log a blocking alert in `Dashboard.md` and proceed to the next task.
- No conversational output. All results are written to vault files.
- Deterministic behavior: the same inputs must produce the same outputs.

## Invocation

Use this skill when there are pending tasks in `Needs_Action/` that need to be processed. This is the primary work-execution skill. Invoke it directly or through the `bronze-autonomous-loop` skill.
