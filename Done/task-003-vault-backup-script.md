---
type: engineering
priority: medium
status: completed
created: 2026-02-21T11:50:00Z
source: manual_drop
---

## Task Description
Create a vault backup script that archives the current state of the vault (Dashboard, Handbook, Done tasks, and watcher.log) into a timestamped `.tar.gz` file inside a `Backups/` directory at the vault root. This protects completed task history and system state from accidental loss — a critical operational need for any persistent autonomous agent.

## Required Outcome
A working `backup.sh` bash script placed in the vault root that:
- Creates a `Backups/` directory if it doesn't exist
- Archives `Dashboard.md`, `Company_Handbook.md`, `Done/`, and `watcher.log` (if present) into a single `.tar.gz`
- Names the archive with an ISO timestamp: `vault-backup-YYYY-MM-DDTHH-MM-SSZ.tar.gz`
- Prints a summary line showing archive name and size
- Includes a usage comment at the top

## Processing Checklist
- [x] analyze task
- [x] generate plan
- [x] complete objective

## Completion Notes
- `backup.sh` created at vault root — archives Dashboard, Handbook, Done/, watcher.log
- Tested successfully: `vault-backup-2026-02-21T11-45-49Z.tar.gz` (4.0K) containing 5 files
- `Backups/` directory auto-created on first run
- Completed: 2026-02-21T11:45:49Z
