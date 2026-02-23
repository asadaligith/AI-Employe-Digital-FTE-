# Skill: validate-task-schema

## Purpose

Verify that a task file in `Needs_Action/` conforms to the mandatory schema before processing. Reject invalid files and log alerts in `Dashboard.md`.

## Execution Steps

1. Accept a target: either a specific filename in `Needs_Action/` or all `.md` files in that directory.
2. For each target file, read its full contents.
3. Check for valid YAML frontmatter (content between opening `---` and closing `---` at the top of the file).
4. Verify the following frontmatter fields are present:
   - `type` — must exist (any string value).
   - `priority` — must exist and be one of: `low`, `medium`, `high`.
   - `status` — must exist and be `pending` for unprocessed tasks.
   - `created` — must exist as an ISO 8601 UTC timestamp.
   - `source` — must exist (any string value).
5. Verify the following markdown sections exist with non-empty content:
   - `## Task Description` — must be present with text below the heading.
   - `## Required Outcome` — must be present with text below the heading.
   - `## Processing Checklist` — must be present with at least one `- [ ]` unchecked item.
6. If all checks pass: the file is valid and ready for processing.
7. If any check fails:
   a. Do not modify or move the file. Leave it in `Needs_Action/`.
   b. Log an alert in `Dashboard.md` under `## Alerts`:
      ```
      - <UTC ISO 8601 timestamp> : SCHEMA FAILURE — `<filename>` is missing: <comma-separated list of missing fields/sections>
      ```
   c. Report the file as invalid with specific failures listed.

## Constraints

- Operate only within the vault root directory.
- Follow all policies in `Company_Handbook.md`.
- This is a read-only inspection of task files. Never modify a task file during validation.
- No conversational output. Validation failures are logged to `Dashboard.md` alerts only.
- Deterministic behavior: the same file must always produce the same validation result.

## Invocation

Use this skill before processing any task file. It is called internally by `process-tasks` but can also be invoked standalone to audit `Needs_Action/` without triggering processing.
