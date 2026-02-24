# Silver Tier AI Employee — System Architecture

## Overview

The Silver Tier extends the Bronze autonomous agent with:
- **Multiple watchers** (filesystem + Gmail)
- **AI reasoning loop** with plan generation
- **Human-in-the-loop approval** for sensitive actions
- **MCP server integration** for real external actions (email)
- **LinkedIn automation** with approval-gated publishing
- **Scheduled execution** via cron

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PERCEPTION LAYER                              │
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌────────────────┐  │
│  │  watcher.py   │     │gmail_watcher │     │watcher_manager │  │
│  │  (filesystem) │     │   (IMAP)     │     │  (orchestrator)│  │
│  └──────┬───────┘     └──────┬───────┘     └────────────────┘  │
│         │                     │                                  │
│         └─────────┬───────────┘                                  │
│                   ▼                                              │
│           Needs_Action/                                          │
│           (TASK_*.md files)                                      │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│                    REASONING LAYER                               │
│                    (silver_loop.py)                               │
│                                                                  │
│  Phase 1: Initialize ──── Company_Handbook.md                   │
│       │                                                          │
│  Phase 2: Analyze ─────── classify tasks by type                │
│       │                                                          │
│  Phase 3: Plan ────────── Plans/PLAN_*.md                       │
│       │                                                          │
│  Phase 4: Route & Execute                                        │
│       │    ├─ email ──────── approval gate → MCP email          │
│       │    ├─ marketing ──── approval gate → LinkedIn draft     │
│       │    ├─ finance ────── approval gate → log result         │
│       │    ├─ file ──────── auto-process (Claude reasoning)     │
│       │    └─ general ───── auto-process (Claude reasoning)     │
│       │                                                          │
│  Phase 5: Complete ────── Done/                                  │
│       │                                                          │
│  Phase 6: Dashboard ───── Dashboard.md                           │
│       │                                                          │
│  Phase 7: Return ──────── summary JSON                           │
└─────────────────────────────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│                    APPROVAL LAYER                                │
│                    (approval_gate.py)                             │
│                                                                  │
│  Pending_Approval/                                               │
│  ├── APPROVAL_*.md ──── status: pending → approved/rejected     │
│  └── LINKEDIN_*.md ──── draft posts awaiting review             │
│                                                                  │
│  Risk Levels:                                                    │
│  ├── low ────── 72h expiry                                      │
│  ├── medium ─── 48h expiry                                      │
│  └── high ──── 24h expiry                                       │
└─────────────────────────────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│                    ACTION LAYER                                  │
│                                                                  │
│  ┌──────────────────┐     ┌────────────────────────────────┐   │
│  │ mcp_email_server │     │ Claude Code CLI                 │   │
│  │ (SMTP via MCP)   │     │ (AI reasoning for task results) │   │
│  └──────────────────┘     └────────────────────────────────┘   │
│                                                                  │
│  Logs/                                                           │
│  └── EMAIL_*.md ──── full audit trail of sent emails            │
└─────────────────────────────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│                    SCHEDULING LAYER                              │
│                                                                  │
│  run_silver.sh ──── entry point (watchers + loop)               │
│  schedule_setup.sh ── cron installer (daily at 8:00 UTC)        │
│  crontab ──────────── 0 8 * * * bash run_silver.sh              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Folder Structure

```
Bronce-tiar/
├── .claude/
│   ├── settings.json              # MCP server configuration
│   └── skills/                    # 10 Agent Skill definitions
│       ├── bronze-autonomous-loop/
│       ├── process-tasks/
│       ├── update-dashboard/
│       ├── validate-task-schema/
│       ├── analyze-needs-action/
│       ├── generate-plan-md/
│       ├── generate-linkedin-business-post/
│       ├── create-approval-file/
│       ├── process-all-pending-tasks/
│       └── send-email-mcp/
│
├── Inbox/                         # Raw inputs (watchers monitor this)
├── Needs_Action/                  # Pending tasks (pipeline input)
├── Done/                          # Completed tasks (permanent archive)
├── Plans/                         # Generated execution plans
├── Pending_Approval/              # Approval requests + LinkedIn drafts
├── Logs/                          # Email send logs, audit trail
├── Backups/                       # Vault backup archives
│
├── CLAUDE.md                      # System instructions (Bronze + Silver)
├── Company_Handbook.md            # Policy rules (updated for Silver)
├── Dashboard.md                   # System state and activity
├── config.json                    # Credentials (Gmail, SMTP)
│
├── watcher.py                     # Filesystem watcher (Bronze)
├── gmail_watcher.py               # Gmail IMAP watcher (Silver)
├── watcher_manager.py             # Unified watcher orchestrator
├── silver_loop.py                 # Reasoning loop (7-phase pipeline)
├── approval_gate.py               # Human-in-the-loop module
├── mcp_email_server.py            # MCP email server (SMTP)
├── run_silver.sh                  # Daily execution entry point
├── schedule_setup.sh              # Cron job installer
├── backup.sh                      # Vault backup utility
├── watcher.log                    # Event log
└── SILVER_ARCHITECTURE.md         # This file
```

---

## Execution Pipeline

### Daily Automated Run

```
cron (8:00 UTC)
  └─→ run_silver.sh
       ├─→ watcher_manager.py --once     # single scan all watchers
       │    ├─→ watcher.py (filesystem)   # check Inbox/ for new files
       │    └─→ gmail_watcher.py (IMAP)   # check Gmail for new emails
       │         └─→ creates TASK_*.md in Needs_Action/
       │
       └─→ silver_loop.py                 # 7-phase reasoning pipeline
            ├─ Phase 1: Initialize        # load policies, validate dirs
            ├─ Phase 2: Analyze           # scan, classify, sort tasks
            ├─ Phase 3: Plan              # generate Plan.md per task
            ├─ Phase 4: Route & Execute   # skill routing, approval gates
            ├─ Phase 5: Complete          # move to Done/
            ├─ Phase 6: Dashboard         # update system state
            └─ Phase 7: Return            # output summary
```

### Human Approval Flow

```
Task requires approval (email/finance/marketing)
  └─→ approval_gate.py creates APPROVAL_*.md in Pending_Approval/
       └─→ Dashboard.md alert: "APPROVAL REQUIRED"
            └─→ Human opens file, changes status: pending → approved
                 └─→ Next silver_loop.py run detects approved status
                      └─→ Action executes (email sends, post publishes)
                           └─→ Approval marked: status: executed
                                └─→ Logged in Logs/ and Dashboard.md
```

---

## Component Details

### 1. Watchers (Perception)

**Filesystem Watcher** (`watcher.py`)
- Monitors `Inbox/` directory with 2-second polling
- Creates `TASK_*.md` in `Needs_Action/` for each new file
- Maintains `.watcher_registry.json` to prevent duplicates
- Sweeps completed tasks: moves inbox source files to `Done/`

**Gmail Watcher** (`gmail_watcher.py`)
- Connects to Gmail via IMAP SSL (stdlib `imaplib`)
- Polls for UNSEEN emails at configurable interval (default 30s)
- Creates `TASK_*.md` with `type: email` and email metadata
- Priority heuristic: "urgent"/"critical" keywords → high priority
- Maintains `.gmail_registry.json` (tracks processed UIDs)
- Requires `config.json` with Gmail App Password

**Watcher Manager** (`watcher_manager.py`)
- Runs both watchers concurrently using threads
- Supports `--once` for single-scan mode (used in daily run)
- Graceful shutdown via SIGINT/SIGTERM

### 2. Reasoning Loop (`silver_loop.py`)

The core intelligence engine implementing the `process-all-pending-tasks` skill.

**Task Classification** (from `analyze-needs-action` skill):
| Category | Match Criteria |
|----------|---------------|
| `email` | type/source contains "email", description mentions email |
| `message` | type contains "message", "chat", "notification" |
| `file` | type contains "file", source is watcher.py |
| `finance` | type/description mentions finance, invoice, payment |
| `marketing` | type/description mentions linkedin, marketing, social |
| `general` | fallback for unmatched tasks |

**AI Reasoning**: Invokes Claude Code CLI (`claude --print`) for task processing. Falls back to structured analysis if CLI is unavailable.

### 3. Approval Gate (`approval_gate.py`)

Implements the `create-approval-file` skill as a reusable Python module.

**Functions**:
- `requires_approval(action_type, task_type)` — check if approval needed
- `create_approval_file(...)` — create approval request in `Pending_Approval/`
- `check_approval(action_type, target)` — check if valid approval exists
- `mark_approval_executed(file)` — mark approval as executed after action
- `list_pending_approvals()` — list all pending approvals with metadata

### 4. MCP Email Server (`mcp_email_server.py`)

Implements the `send-email-mcp` skill as a real MCP server.

**Protocol**: JSON-RPC 2.0 over stdio (MCP standard)
**Tool**: `send_email` — sends via SMTP with mandatory approval enforcement
**Safety**: Will refuse to send without valid, non-expired approval
**Logging**: Every send attempt logged in `Logs/EMAIL_*.md`
**Config**: `.claude/settings.json` points to this server

### 5. LinkedIn Automation

Implements the `generate-linkedin-business-post` skill.

**Flow**:
1. Task classified as `marketing` enters pipeline
2. Silver loop generates LinkedIn post content
3. Draft saved to `Pending_Approval/LINKEDIN_*.md`
4. Human reviews draft, approves or requests changes
5. Approved draft can be manually posted (no API — draft-only)

### 6. Scheduling

**Daily cron** installed by `schedule_setup.sh`:
```
0 8 * * * /usr/bin/env bash /path/to/run_silver.sh >> watcher.log 2>&1
```

**WSL/Windows**: Use Windows Task Scheduler:
- Program: `wsl`
- Arguments: `bash /mnt/e/AI_Employ_Vault/Bronce-tiar/run_silver.sh`

---

## Build Order (Step-by-Step)

1. **Create directories**: `Plans/`, `Pending_Approval/`, `Logs/`
2. **Create `config.json`**: Template with Gmail/SMTP credentials
3. **Update `Company_Handbook.md`**: Add Silver Tier approval policies
4. **Build `gmail_watcher.py`**: IMAP email watcher
5. **Build `watcher_manager.py`**: Unified watcher orchestrator
6. **Build `approval_gate.py`**: Human-in-the-loop module
7. **Build `mcp_email_server.py`**: MCP email server + `.claude/settings.json`
8. **Build `silver_loop.py`**: 7-phase reasoning loop orchestrator
9. **Build `run_silver.sh`**: Daily execution entry point
10. **Build `schedule_setup.sh`**: Cron installer
11. **Update `CLAUDE.md`**: Add Silver Tier instructions
12. **Update `Dashboard.md`**: Add Silver Tier status fields

---

## Quick Start

```bash
# 1. Configure credentials
#    Edit config.json — set gmail.email, gmail.app_password, smtp credentials

# 2. Test watchers
python watcher_manager.py --once

# 3. Test reasoning loop (dry run)
python silver_loop.py --dry-run

# 4. Full manual run
./run_silver.sh

# 5. Install daily schedule
./schedule_setup.sh

# 6. Check status
./schedule_setup.sh --status

# 7. Continuous watcher mode (for development)
python watcher_manager.py
```

---

## Agent Skills Summary

| # | Skill | Tier | SKILL.md | Implementation |
|---|-------|------|----------|----------------|
| 1 | Validate Task Schema | Bronze | `.claude/skills/validate-task-schema/` | `silver_loop.py:validate_task_schema()` |
| 2 | Process Tasks | Bronze | `.claude/skills/process-tasks/` | `silver_loop.py:execute_task()` |
| 3 | Update Dashboard | Bronze | `.claude/skills/update-dashboard/` | `silver_loop.py:update_dashboard()` |
| 4 | Bronze Autonomous Loop | Bronze | `.claude/skills/bronze-autonomous-loop/` | `silver_loop.py` (backward compat) |
| 5 | Analyze Needs Action | Silver | `.claude/skills/analyze-needs-action/` | `silver_loop.py:phase_analyze()` |
| 6 | Generate Plan | Silver | `.claude/skills/generate-plan-md/` | `silver_loop.py:generate_plan()` |
| 7 | Generate LinkedIn Post | Silver | `.claude/skills/generate-linkedin-business-post/` | `silver_loop.py` + approval gate |
| 8 | Create Approval File | Silver | `.claude/skills/create-approval-file/` | `approval_gate.py` |
| 9 | Process All Pending | Silver | `.claude/skills/process-all-pending-tasks/` | `silver_loop.py:run_pipeline()` |
| 10 | Send Email (MCP) | Silver | `.claude/skills/send-email-mcp/` | `mcp_email_server.py` |

All 10 skills have both a declarative SKILL.md definition and working Python implementation.
