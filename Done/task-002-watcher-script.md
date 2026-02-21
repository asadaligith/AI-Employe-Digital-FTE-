---
type: engineering
priority: high
status: completed
created: 2026-02-20T00:15:00Z
source: manual_drop
---

## Task Description
Create a filesystem watcher script that monitors the `Needs_Action/` directory for new `.md` files. When a new file is detected, the script should log the event (filename, timestamp) to a `watcher.log` file in the vault root. This is the foundational integration point described in the Watcher Integration Contract (Section 6) — without it, the agent has no automated trigger.

## Required Outcome
A working `watcher.sh` bash script placed in the vault root that:
- Uses `inotifywait` (inotify-tools) to watch `Needs_Action/` for new file creation
- Logs each detected file to `watcher.log` with ISO timestamp and filename
- Runs as a background loop until manually killed
- Includes a usage comment at the top

## Processing Checklist
- [x] analyze task
- [x] generate plan
- [x] complete objective

## Completion Notes
- `watcher.sh` created at vault root with inotifywait-based monitoring loop
- Script filters for `.md` files only, logs ISO timestamps to `watcher.log`
- Includes dependency check, usage comments, and background-run support
- Completed: 2026-02-21T00:00:00Z
