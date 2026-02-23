# Skill: bronze-autonomous-loop

## Purpose

Execute the top-level deterministic cycle for the Bronze Tier AI Employee. This is the primary entry point for agent activation. It orchestrates all other skills in the correct order.

## Execution Steps

1. Read `Company_Handbook.md` to load current operational policies.
2. Scan `Needs_Action/` for `.md` files (exclude hidden files and `.gitkeep`).
3. If tasks exist:
   a. Invoke `process-tasks` to handle all pending work through the full lifecycle.
   b. After processing completes, invoke `update-dashboard` to record final system state.
4. If no tasks exist:
   a. Invoke `update-dashboard` to record the idle check with current UTC timestamp.
   b. Stop. Do not create files, do not modify state beyond the dashboard timestamp.
5. The cycle is complete. The agent runs once per invocation. It does not loop continuously.

## Constraints

- Operate only within the vault root directory. Never act outside the vault boundary.
- Do not modify `watcher.py`. Perception is handled separately by the watcher.
- Do not modify `backup.sh` or `Company_Handbook.md`.
- Do not delete any file from `Done/`. Completed tasks are a permanent archive.
- Do not skip any task in `Needs_Action/`. Every task must be attempted.
- If a task cannot be completed, log a blocking alert in `Dashboard.md` under `## Alerts` and continue to the next task.
- No conversational output. The agent communicates exclusively through vault files.
- Deterministic behavior: invoking this skill with the same vault state must produce the same outcome.
- Idempotent when idle: running with an empty `Needs_Action/` produces no side effects beyond updating the dashboard timestamp.

## Invocation

Use this skill as the main entry point for the AI Employee. Run it to trigger a full autonomous processing cycle. This is the skill to invoke when you want the agent to "do its job."
