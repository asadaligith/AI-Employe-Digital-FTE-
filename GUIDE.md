# Bronze Tier AI Employee — Complete Guide

> A local-first, file-driven autonomous AI agent that processes tasks through an Obsidian-compatible vault structure.

---

## Table of Contents

1. [What Is This?](#what-is-this)
2. [Architecture Overview](#architecture-overview)
3. [How to Build (Setup from Scratch)](#how-to-build)
4. [How It Works](#how-it-works)
5. [How to Use It](#how-to-use-it)
6. [Task File Schema](#task-file-schema)
7. [Task Types and Examples](#task-types-and-examples)
8. [Utilities](#utilities)
9. [Core Files Reference](#core-files-reference)
10. [Troubleshooting](#troubleshooting)

---

## What Is This?

The Bronze Tier AI Employee is an **autonomous task-processing agent** that operates entirely through the filesystem. Instead of chatting back and forth, you give it work by dropping markdown files into a folder — it detects them, reasons through them, completes the objective, and moves the result to a "Done" folder.

**Key principles:**
- No chat interface — communication happens through files
- Deterministic execution loop — detect, reason, update, complete
- Full audit trail — every task is preserved, never deleted
- Local-first — everything runs on your machine, no cloud dependencies
- Obsidian-compatible — open the vault in Obsidian for a visual dashboard

---

## Architecture Overview

```
AI_Employ_Vault/Bronce-tiar/
│
├── Dashboard.md            # System state — pending count, activity log, alerts
├── Company_Handbook.md     # Policy rules the agent must obey
├── GUIDE.md                # This file
│
├── Inbox/                  # Raw external inputs (future use)
├── Needs_Action/           # Active tasks waiting to be processed
├── Done/                   # Completed tasks (permanent archive)
│
├── watcher.sh              # Filesystem watcher — detects new tasks
├── watcher.log             # Event log from watcher
├── backup.sh               # Vault backup utility
└── Backups/                # Timestamped .tar.gz archives
```

### Lifecycle Flow

```
External Input ──► Needs_Action/ ──► Agent Processes ──► Done/
                        │                    │
                        │                    ├── Updates Dashboard.md
                        │                    └── Marks checklist complete
                        │
                  watcher.sh detects file arrival
                  and logs to watcher.log
```

---

## How to Build

### Prerequisites

- **OS:** Linux or WSL2 (Windows Subsystem for Linux)
- **Shell:** Bash 4.0+
- **AI Backend:** Claude Code CLI (or any LLM agent that can read/write files)
- **Optional:** [inotify-tools](https://github.com/inotify-tools/inotify-tools) for event-driven file watching
- **Optional:** [Obsidian](https://obsidian.md) to visualize the vault

### Step 1 — Create the Vault Directory

```bash
mkdir -p AI_Employ_Vault/Bronce-tiar
cd AI_Employ_Vault/Bronce-tiar
```

### Step 2 — Create Lifecycle Directories

```bash
mkdir -p Inbox Needs_Action Done Backups
```

### Step 3 — Create Dashboard.md

```markdown
# AI Employee Dashboard

## System Status
- Pending Tasks: 0
- Completed Today: 0
- Last Execution: <not yet run>

## Recent Activity
- <timestamp> : Vault initialized

## Alerts
- None
```

### Step 4 — Create Company_Handbook.md

```markdown
# Company Handbook

## Communication Rules
- All communication occurs through vault files only.
- No conversational output outside of structured markdown.
- Alerts and status updates are logged in Dashboard.md.

## Risk Thresholds
- High priority tasks must be processed first.
- If a task cannot be completed, log a blocking alert in Dashboard.md.

## Approval Requirements
- Bronze Tier operates autonomously with no human approval required.
- All actions are local-loop only.

## Task Handling Policy
- Tasks must follow the mandatory schema (frontmatter metadata + checklist).
- Files missing metadata are rejected and logged as alerts.
- Tasks are processed in priority order: high > medium > low.
- Completed tasks are moved to Done/. Never deleted.
- No task may be skipped.
```

### Step 5 — Make Utility Scripts Executable

```bash
chmod +x watcher.sh backup.sh
```

Your vault is now ready to accept tasks.

---

## How It Works

The agent follows a **deterministic execution loop** every time it is activated:

```
1. Read all files in Needs_Action/
2. Validate metadata (reject malformed files)
3. Sort by priority: high → medium → low
4. For each task:
   a. Parse the task description and required outcome
   b. Create an internal reasoning plan
   c. Execute the objective
   d. Mark checklist items [x] complete
   e. Add completion notes to the task file
   f. Set status: completed in frontmatter
   g. Move the file to Done/
   h. Update Dashboard.md
5. When Needs_Action/ is empty → cycle ends
```

### What Triggers the Agent?

**Manual activation:** Run the agent via Claude Code CLI:
```bash
claude "complete these task if any remaining"
```

**Watcher-assisted:** Run `watcher.sh` in the background to detect new files. The watcher logs events but does not trigger the agent automatically (Bronze Tier limitation). You still invoke the agent manually or via a cron job.

### What Happens to Completed Tasks?

They are **moved to `Done/`**, never deleted. Each completed task retains:
- Original metadata and description
- Checked-off processing checklist
- Completion notes added by the agent
- Status changed to `completed`

---

## How to Use It

### Dropping a Task

Create a markdown file in `Needs_Action/` following the required schema:

```bash
cat > Needs_Action/task-004-my-task.md << 'EOF'
---
type: engineering
priority: high
status: pending
created: 2026-02-21T12:00:00Z
source: manual_drop
---

## Task Description
Describe what needs to be done. Be specific.

## Required Outcome
Define the concrete deliverable or success condition.

## Processing Checklist
- [ ] analyze task
- [ ] generate plan
- [ ] complete objective
EOF
```

### Naming Convention

```
task-<NNN>-<short-description>.md
```

Examples:
- `task-004-api-endpoint.md`
- `task-005-fix-login-bug.md`
- `task-006-write-unit-tests.md`

### Running the Agent

```bash
# Navigate to the vault
cd AI_Employ_Vault/Bronce-tiar

# Activate the agent via Claude Code
claude "complete these task if any remaining"
```

The agent will process all pending tasks and stop when `Needs_Action/` is empty.

### Running the Watcher

```bash
# Start in background
./watcher.sh &

# Check the log
tail -f watcher.log

# Stop the watcher
kill %1
```

The watcher monitors `Needs_Action/` and logs every new `.md` file to `watcher.log`. It uses `inotifywait` if available, otherwise falls back to 2-second polling.

### Running a Backup

```bash
./backup.sh
# Output: Backup complete: vault-backup-2026-02-21T12-00-00Z.tar.gz (4.0K)
```

Archives `Dashboard.md`, `Company_Handbook.md`, `Done/`, and `watcher.log` into `Backups/`.

---

## Task File Schema

Every file in `Needs_Action/` **must** follow this exact structure or it will be rejected:

```markdown
---
type: <task_type>            # engineering, research, operations, etc.
priority: low | medium | high
status: pending
created: <ISO 8601 timestamp> # e.g. 2026-02-21T12:00:00Z
source: <origin>              # manual_drop, watcher, cron, api, etc.
---

## Task Description
<What needs to be done — be specific and actionable>

## Required Outcome
<Clear, measurable completion condition>

## Processing Checklist
- [ ] analyze task
- [ ] generate plan
- [ ] complete objective
```

### Frontmatter Fields

| Field      | Required | Values                            | Description                          |
|------------|----------|-----------------------------------|--------------------------------------|
| `type`     | Yes      | Any string                        | Category of work                     |
| `priority` | Yes      | `low`, `medium`, `high`           | Processing order (high first)        |
| `status`   | Yes      | `pending` (set by you)            | Agent changes to `completed`         |
| `created`  | Yes      | ISO 8601 timestamp                | When the task was created            |
| `source`   | Yes      | Any string                        | Where the task came from             |

### What Happens If Metadata Is Missing?

The agent will **reject the file** and log an alert in `Dashboard.md` under the Alerts section. The file stays in `Needs_Action/` until fixed.

---

## Task Types and Examples

### Research Task

```markdown
---
type: research
priority: medium
status: pending
created: 2026-02-21T12:00:00Z
source: manual_drop
---

## Task Description
Compile a summary of the top 3 JavaScript testing frameworks in 2026.

## Required Outcome
A markdown list of 3 frameworks with one-sentence descriptions each.

## Processing Checklist
- [ ] analyze task
- [ ] generate plan
- [ ] complete objective
```

### Engineering Task

```markdown
---
type: engineering
priority: high
status: pending
created: 2026-02-21T12:00:00Z
source: manual_drop
---

## Task Description
Create a Python script that converts CSV files to JSON format.

## Required Outcome
A working `csv_to_json.py` script at the vault root that accepts a CSV path as argument and outputs JSON to stdout.

## Processing Checklist
- [ ] analyze task
- [ ] generate plan
- [ ] complete objective
```

### Operations Task

```markdown
---
type: operations
priority: low
status: pending
created: 2026-02-21T12:00:00Z
source: manual_drop
---

## Task Description
Clean up the Done/ folder by generating a summary index of all completed tasks.

## Required Outcome
A `Done/INDEX.md` file listing all completed tasks with their type, priority, and completion date.

## Processing Checklist
- [ ] analyze task
- [ ] generate plan
- [ ] complete objective
```

---

## Utilities

### watcher.sh — Filesystem Watcher

| Detail         | Value                                          |
|----------------|------------------------------------------------|
| Location       | Vault root                                     |
| Purpose        | Detects new `.md` files in `Needs_Action/`     |
| Log file       | `watcher.log`                                  |
| Primary mode   | `inotifywait` (event-driven, near-instant)     |
| Fallback mode  | Polling every 2 seconds                        |
| Install dep    | `sudo apt install inotify-tools` (optional)    |

### backup.sh — Vault Backup

| Detail         | Value                                          |
|----------------|------------------------------------------------|
| Location       | Vault root                                     |
| Purpose        | Archives vault state to timestamped `.tar.gz`  |
| Output dir     | `Backups/`                                     |
| Includes       | Dashboard, Handbook, Done/, watcher.log        |
| Naming         | `vault-backup-YYYY-MM-DDTHH-MM-SSZ.tar.gz`    |

---

## Core Files Reference

| File                  | Role                  | Updated By   | When                          |
|-----------------------|-----------------------|--------------|-------------------------------|
| `Dashboard.md`        | System state          | Agent        | After every task processed    |
| `Company_Handbook.md` | Policy rules          | Human        | When policies change          |
| `watcher.log`         | File detection events | `watcher.sh` | When new files are detected  |

---

## Troubleshooting

### Task is not being processed
- Verify the file is in `Needs_Action/`, not `Inbox/` or another folder
- Check that the YAML frontmatter is valid (dashes, colons, spacing)
- Ensure `status: pending` is set
- Check `Dashboard.md` Alerts section for rejection messages

### Watcher is not detecting files
- Confirm `watcher.sh` is running: `ps aux | grep watcher`
- Check `watcher.log` for startup messages
- Ensure the file has a `.md` extension (non-markdown files are ignored)
- If using polling mode, wait at least 3 seconds after dropping the file

### Backup is empty or fails
- Ensure at least one of `Dashboard.md`, `Company_Handbook.md`, or `Done/` exists
- Check disk space with `df -h`

### Agent reports "no tasks"
- Run `ls Needs_Action/` to verify files exist
- Ensure filenames end in `.md`
- Validate frontmatter is present and correctly formatted

---

## Quick Reference Cheat Sheet

```bash
# Drop a task
cp my-task.md Needs_Action/

# Run the agent
claude "complete these task if any remaining"

# Start the watcher
./watcher.sh &

# Check watcher events
tail -f watcher.log

# Back up the vault
./backup.sh

# View completed tasks
ls Done/

# Check system state
cat Dashboard.md
```

---

*This vault is designed to be opened in [Obsidian](https://obsidian.md) for a visual dashboard experience, but works entirely from the command line.*
