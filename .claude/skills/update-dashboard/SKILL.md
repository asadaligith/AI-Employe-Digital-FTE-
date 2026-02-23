# Skill: update-dashboard

## Purpose

Maintain accurate system state visibility by updating `Dashboard.md` with current task counts, execution timestamps, recent activity entries, and active alerts.

## Execution Steps

1. Count all `.md` files in `Needs_Action/` (exclude hidden files and `.gitkeep`) → pending task count.
2. Count all `.md` files in `Done/` that contain a completion timestamp matching today's UTC date → completed today count.
3. Get the current UTC timestamp in ISO 8601 format (e.g. `2026-02-23T14:30:00Z`).
4. Read the current `Dashboard.md`.
5. Update the `## System Status` section:
   ```
   ## System Status
   - Pending Tasks: <pending count>
   - Completed Today: <completed today count>
   - Last Execution: <current UTC ISO 8601 timestamp>
   ```
6. If a specific activity occurred (task completed, validation failure, cycle run), insert a new timestamped entry at the top of the `## Recent Activity` list:
   ```
   - <UTC ISO 8601 timestamp> : <concise description of what occurred>
   ```
7. Review the `## Alerts` section:
   - If there are active issues (schema failures, processing errors), ensure they are listed.
   - If previously logged alerts are resolved, remove them.
   - If no alerts remain, set the content to `- None`.
8. Write the updated `Dashboard.md` back to disk.

## Constraints

- Operate only within the vault root directory.
- Follow all policies in `Company_Handbook.md`.
- Do not fabricate activity entries. Only record events that actually occurred.
- Do not remove or alter existing historical activity entries. Only prepend new ones.
- No conversational output. Results are written to `Dashboard.md`.
- Deterministic behavior: running this skill when nothing has changed must not create spurious entries.

## Invocation

Use this skill after any task is processed, after a validation failure is logged, at the start or end of an agent cycle, or any time the system state in `Dashboard.md` may be stale.
