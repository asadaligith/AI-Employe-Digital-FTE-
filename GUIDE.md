# Silver Tier AI Employee — Complete Guide

> A local-first, file-driven autonomous AI agent with email integration, WhatsApp monitoring, LinkedIn post generation, and human-in-the-loop approval workflows.

---

## Table of Contents

1. [What Is This?](#what-is-this)
2. [Architecture Overview](#architecture-overview)
3. [Prerequisites](#prerequisites)
4. [Quick Start (5 Steps)](#quick-start)
5. [Gmail Setup](#gmail-setup)
6. [WhatsApp Setup](#whatsapp-setup)
7. [Running the System](#running-the-system)
8. [Scheduling (Automated Daily Runs)](#scheduling)
9. [Approval Workflow](#approval-workflow)
10. [LinkedIn Post Generation](#linkedin-post-generation)
11. [Email Sending (MCP)](#email-sending)
12. [Task File Schema](#task-file-schema)
13. [Task Types and Examples](#task-types-and-examples)
14. [Core Files Reference](#core-files-reference)
15. [Troubleshooting](#troubleshooting)
16. [Quick Reference Cheat Sheet](#quick-reference)

---

## What Is This?

The Silver Tier AI Employee is an **autonomous task-processing agent** that operates entirely through the filesystem. It builds on the Bronze foundation with:

- **3 Watchers** — filesystem, Gmail, and WhatsApp monitoring
- **AI Reasoning** — Claude Code CLI for intelligent task processing
- **Plan Generation** — creates structured Plan.md files before execution
- **Approval Gates** — human-in-the-loop for sensitive actions (email, LinkedIn, finance)
- **LinkedIn Post Generation** — drafts professional posts for review
- **Email Sending** — MCP server for outbound email with approval enforcement
- **Scheduled Execution** — cron/Task Scheduler for daily automated runs

**Key principles:**
- No chat interface — communication happens through files
- Deterministic 7-phase execution pipeline
- Full audit trail — every task is preserved, never deleted
- Local-first with controlled external actions (email only after approval)
- Obsidian-compatible — open the vault in Obsidian for a visual dashboard

---

## Architecture Overview

```
AI_Employ_Vault/Bronce-tiar/
│
├── Dashboard.md              # System state — pending count, activity log, alerts
├── Company_Handbook.md       # Policy rules the agent must obey
├── config.json               # Credentials and watcher configuration
├── GUIDE.md                  # This file
│
├── Inbox/                    # Raw external inputs
│   └── whatsapp/             # WhatsApp chat export drop zone
├── Needs_Action/             # Active tasks waiting to be processed
├── Done/                     # Completed tasks (permanent archive)
├── Plans/                    # Generated execution plans
├── Pending_Approval/         # Human approval requests & LinkedIn drafts
├── Logs/                     # Audit trail for external actions
├── Backups/                  # Timestamped .tar.gz vault archives
│
├── silver_loop.py            # 7-phase reasoning loop orchestrator
├── watcher.py                # Filesystem perception layer (Inbox/)
├── gmail_watcher.py          # Gmail IMAP perception layer
├── whatsapp_watcher.py       # WhatsApp chat export perception layer
├── watcher_manager.py        # Unified watcher orchestrator (all 3)
├── approval_gate.py          # Human-in-the-loop module
├── linkedin_post_generator.py # LinkedIn post draft generator
├── mcp_email_server.py       # MCP server for outbound email
│
├── run_silver.sh             # Daily execution entry point
├── schedule_setup.sh         # Cron/scheduler installer
├── backup.sh                 # Vault backup utility
└── watcher.log               # Watcher and agent event log
```

### Silver Tier Pipeline (7 Phases)

```
Phase 1: Initialize    → Load policies, validate vault structure
Phase 2: Analyze       → Scan Needs_Action/, classify tasks by type
Phase 3: Plan          → Generate Plan.md with steps and approval gates
Phase 4: Route & Execute → Route to skill, check approvals, execute
Phase 5: Complete      → Write results, mark checklist, move to Done/
Phase 6: Update Dashboard → Record counts, activity, alerts
Phase 7: Return        → Output JSON summary
```

### Lifecycle Flow

```
External Input ──► Inbox/ ──► Watchers detect ──► Needs_Action/ ──► silver_loop.py ──► Done/
     │                              │                     │               │
     ├── File drop                  ├── watcher.py        │               ├── Plans/ (generated)
     ├── Gmail                      ├── gmail_watcher.py  │               ├── Pending_Approval/
     └── WhatsApp export            └── whatsapp_watcher  │               ├── Dashboard.md (updated)
                                                          │               └── Logs/ (if external action)
                                                          │
                                                          └── Approval gate check
                                                               (email, LinkedIn, finance)
```

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **OS** | Linux, macOS, or WSL2 (Windows) |
| **Python** | 3.6+ (standard library only — no pip installs needed) |
| **Claude Code CLI** | Required for AI reasoning (`claude --print`) |
| **Gmail** | Optional — for email watcher and sending. Requires App Password. |
| **Obsidian** | Optional — for visual dashboard experience |

---

## Quick Start

### Step 1 — Verify vault structure

```bash
cd /mnt/e/AI_Employ_Vault/Bronce-tiar   # adjust path to your vault
ls -la
```

All directories and scripts should already be in place.

### Step 2 — Verify Python

```bash
python3 --version   # needs 3.6+
python3 -c "import silver_loop; import whatsapp_watcher; import linkedin_post_generator; print('All modules OK')"
```

### Step 3 — Configure credentials (optional, for Gmail)

```bash
# Edit config.json and fill in Gmail credentials
# See "Gmail Setup" section below
```

### Step 4 — Run a test scan

```bash
# Single scan with all watchers (no credentials needed for filesystem/WhatsApp)
python3 watcher_manager.py --once
```

### Step 5 — Run the reasoning loop

```bash
# Process any pending tasks
python3 silver_loop.py

# Or use the full pipeline (watchers + loop)
./run_silver.sh full
```

---

## Gmail Setup

Gmail integration requires a Google App Password (regular password won't work).

### Step 1 — Enable 2-Step Verification

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Under "How you sign in to Google", click **2-Step Verification**
3. Follow the prompts to enable it

### Step 2 — Create an App Password

1. Go to [App Passwords](https://myaccount.google.com/apppasswords)
2. Select app: **Mail**, device: **Other** (enter "AI Employee")
3. Click **Generate**
4. Copy the 16-character password (shown with spaces — remove spaces)

### Step 3 — Update config.json

Edit `config.json` and fill in:

```json
{
  "gmail": {
    "email": "your.email@gmail.com",
    "app_password": "abcdefghijklmnop"
  },
  "smtp": {
    "email": "your.email@gmail.com",
    "app_password": "abcdefghijklmnop"
  }
}
```

### Step 4 — Test the connection

```bash
python3 gmail_watcher.py --once
# Should log: "gmail watcher started (single scan)"
# If credentials are wrong: "ERROR: IMAP login failed"
```

---

## WhatsApp Setup

WhatsApp integration uses **exported chat files** — no API or third-party service needed.

### How to Export a WhatsApp Chat

1. Open **WhatsApp** on your phone
2. Open the chat you want to export
3. Tap the **three-dot menu** (Android) or **contact name** (iOS)
4. Select **Export Chat** > **Without Media**
5. Send/save the `.txt` file to your computer
6. Place it in `Inbox/whatsapp/` in the vault:

```bash
# Copy exported chat to the watch directory
cp "WhatsApp Chat with John.txt" Inbox/whatsapp/
```

### How It Works

- `whatsapp_watcher.py` detects new `.txt` files in `Inbox/whatsapp/`
- Parses the WhatsApp export format (supports multiple date formats)
- Creates a structured `TASK_WA_*.md` in `Needs_Action/` with:
  - Conversation preview (last 10 messages)
  - Primary contact identification
  - Priority detection (urgent keywords → high priority)
- Registry-based deduplication prevents reprocessing the same file

### Test WhatsApp Watcher

```bash
# Create a sample WhatsApp export
cat > Inbox/whatsapp/test-chat.txt << 'EOF'
[01/03/2026, 10:00:00] John: Hey, can you send me the project update?
[01/03/2026, 10:05:00] You: Sure, I'll prepare it today.
[01/03/2026, 10:06:00] John: Great, it's urgent. Client is asking.
EOF

# Run single scan
python3 whatsapp_watcher.py --once

# Check if task was created
ls Needs_Action/TASK_WA_*
```

---

## Running the System

### Option A: Full Pipeline (Recommended)

```bash
./run_silver.sh full
```

This runs:
1. All watchers (single scan) — detect new inputs
2. Reasoning loop — process all pending tasks
3. Dashboard update — record results

### Option B: Watchers Only

```bash
./run_silver.sh --watchers
```

Runs all watchers once to detect and create tasks. Does not process them.

### Option C: Reasoning Loop Only

```bash
./run_silver.sh --loop
```

Processes existing tasks in `Needs_Action/`. Does not scan for new inputs.

### Option D: Dry Run (Test Mode)

```bash
python3 silver_loop.py --dry-run
```

Analyzes and plans tasks without executing them. Useful for testing.

### Option E: Individual Components

```bash
# Filesystem watcher only
python3 watcher.py

# Gmail watcher only
python3 gmail_watcher.py --once

# WhatsApp watcher only
python3 whatsapp_watcher.py --once

# All watchers continuously
python3 watcher_manager.py

# Reasoning loop only
python3 silver_loop.py
```

### Monitoring

```bash
# Watch the log in real time
tail -f watcher.log

# Check system state
cat Dashboard.md

# See pending tasks
ls Needs_Action/

# See completed tasks
ls Done/

# See pending approvals
ls Pending_Approval/
```

---

## Scheduling

### Linux/macOS — Cron

```bash
# Install daily cron job (runs at 8:00 UTC)
./schedule_setup.sh

# Check installed schedule
./schedule_setup.sh --status

# Remove schedule
./schedule_setup.sh --remove
```

### WSL2 / Windows — Task Scheduler

Since WSL2 doesn't have a persistent cron daemon, use Windows Task Scheduler:

1. Open **Task Scheduler** (search in Start menu)
2. Click **Create Basic Task**
3. Name: `AI Employee Silver`
4. Trigger: **Daily**, set time (e.g., 8:00 AM)
5. Action: **Start a program**
6. Program: `wsl`
7. Arguments: `bash -c "cd /mnt/e/AI_Employ_Vault/Bronce-tiar && ./run_silver.sh full"`
8. Click **Finish**

### Manual Execution

If you prefer manual control:

```bash
# Run whenever you want
cd /mnt/e/AI_Employ_Vault/Bronce-tiar
./run_silver.sh full
```

---

## Approval Workflow

Sensitive actions require human approval before execution. This includes:
- **Outbound email** (send_email)
- **LinkedIn posts** (linkedin_post)
- **Financial transactions** (financial_transaction)

### How It Works

1. Agent detects a task requiring approval
2. Creates `Pending_Approval/APPROVAL_<timestamp>.md`
3. Task is paused — status: `pending_approval`
4. **You review** the approval file
5. Change frontmatter `status: pending` to `status: approved` (or `status: rejected`)
6. Save the file
7. On next run, the agent checks and proceeds (or skips if rejected)

### Reviewing Approvals

```bash
# List pending approvals
ls Pending_Approval/

# Read an approval file
cat Pending_Approval/APPROVAL_20260304_120000.md
```

### Approving

Open the file and change the frontmatter:

```yaml
# Before (agent created):
status: pending

# After (you approve):
status: approved
```

### Rejecting

```yaml
status: rejected
```

### Risk Levels and Expiry

| Risk Level | Expiry Window | Example Actions |
|------------|--------------|-----------------|
| Low | 72 hours | Routine internal actions |
| Medium | 48 hours | Email, LinkedIn posts |
| High | 24 hours | Financial transactions |

Expired approvals are automatically treated as rejected.

---

## LinkedIn Post Generation

Marketing tasks automatically generate LinkedIn post drafts.

### How It Works

1. Create a task with marketing keywords (topic, audience, goal)
2. Agent classifies it as `marketing`
3. Approval gate creates `Pending_Approval/APPROVAL_*.md`
4. After approval, `linkedin_post_generator.py` generates a draft
5. Draft saved to `Pending_Approval/LINKEDIN_<timestamp>.md`
6. You review, edit, and manually post on LinkedIn

### Creating a Marketing Task

```bash
cat > Needs_Action/linkedin-post.md << 'EOF'
---
type: marketing
priority: medium
status: pending
created: 2026-03-04T12:00:00Z
source: manual_drop
---

## Task Description
Generate a LinkedIn post about our new AI consulting service launch.

Topic: AI-powered document automation for small businesses
Audience: SMB owners and operations managers
Goal: lead_generation

## Required Outcome
A professional LinkedIn post draft ready for review and publishing.

## Processing Checklist
- [ ] analyze marketing objective
- [ ] generate LinkedIn post content
- [ ] review for compliance and tone
- [ ] submit for publishing approval
EOF
```

### Post Goals

| Goal | Structure | Best For |
|------|-----------|----------|
| `awareness` | Hook → Insight → Value → CTA | Thought leadership, brand building |
| `lead_generation` | Pain point → Solution → Proof → CTA | Generating inbound leads |
| `update` | Announcement → Context → Impact → CTA | Company news, product launches |

### Standalone Generation

```bash
# Generate directly (bypasses task pipeline)
python3 linkedin_post_generator.py "AI consulting service launch" "startup founders" lead_generation
```

---

## Email Sending

Email is sent through an MCP (Model Context Protocol) server.

### How It Works

1. A task requiring email action goes through the approval gate
2. After approval, the MCP server sends via SMTP
3. Full audit log in `Logs/`

### MCP Server

The email MCP server (`mcp_email_server.py`) runs as a JSON-RPC stdio server. It's configured in `.claude/settings.json`:

```json
{
  "mcpServers": {
    "vault-email": {
      "command": "python3",
      "args": ["mcp_email_server.py"],
      "cwd": "/mnt/e/AI_Employ_Vault/Bronce-tiar"
    }
  }
}
```

### Safety

- Email NEVER sends without a valid, non-expired approval file
- All send attempts are logged in `Logs/`
- Attachment size limit: 10MB
- Attachments must be within the vault directory

---

## Task File Schema

Every file in `Needs_Action/` **must** follow this structure:

```markdown
---
type: <task_type>
priority: low | medium | high
status: pending
created: <ISO 8601 timestamp>
source: <origin>
---

## Task Description
<What needs to be done>

## Required Outcome
<Clear completion condition>

## Processing Checklist
- [ ] analyze task
- [ ] generate plan
- [ ] complete objective
```

### Frontmatter Fields

| Field | Required | Values | Description |
|-------|----------|--------|-------------|
| `type` | Yes | Any string | Category (email, message, marketing, file, etc.) |
| `priority` | Yes | `low`, `medium`, `high` | Processing order |
| `status` | Yes | `pending` | Agent changes to `completed` |
| `created` | Yes | ISO 8601 | When the task was created |
| `source` | Yes | Any string | Origin (manual_drop, gmail_watcher.py, etc.) |

### Task Classification

Tasks are auto-classified by type:

| Type | Keywords Matched | Approval Required |
|------|-----------------|-------------------|
| `email` | email, inbox | Yes |
| `message` | whatsapp, message, chat, notification | No |
| `file` | file, watcher.py source | No |
| `finance` | finance, invoice, payment, budget | Yes |
| `marketing` | linkedin, marketing, social, post | Yes |
| `general` | Everything else | No |

---

## Task Types and Examples

### Research Task (General)

```markdown
---
type: research
priority: medium
status: pending
created: 2026-03-04T12:00:00Z
source: manual_drop
---

## Task Description
Compile a summary of the top 3 AI frameworks for small businesses in 2026.

## Required Outcome
A markdown list with one-sentence descriptions each.

## Processing Checklist
- [ ] analyze task
- [ ] generate plan
- [ ] complete objective
```

### Email Response Task

```markdown
---
type: email
priority: high
status: pending
created: 2026-03-04T12:00:00Z
source: gmail_watcher.py
email_from: "client@example.com"
email_subject: "Project proposal"
---

## Task Description
Email received from client@example.com regarding project proposal.

## Required Outcome
Draft a professional response and send after approval.

## Processing Checklist
- [ ] analyze email content
- [ ] draft response
- [ ] submit for approval
- [ ] send email
```

### Marketing Task (LinkedIn)

```markdown
---
type: marketing
priority: medium
status: pending
created: 2026-03-04T12:00:00Z
source: manual_drop
---

## Task Description
Create a LinkedIn post about our quarterly results.

Topic: Q1 2026 revenue growth of 40%
Audience: investors and business partners
Goal: update

## Required Outcome
A LinkedIn post draft ready for review.

## Processing Checklist
- [ ] analyze marketing objective
- [ ] generate LinkedIn post
- [ ] review for compliance
- [ ] submit for approval
```

---

## Core Files Reference

| File | Role | Updated By | When |
|------|------|------------|------|
| `Dashboard.md` | System state | Agent | After every task |
| `Company_Handbook.md` | Policy rules | Human | When policies change |
| `config.json` | Credentials | Human | During setup |
| `watcher.log` | Event log | All watchers + agent | Continuously |
| `silver_loop.py` | Main orchestrator | -- | 7-phase pipeline |
| `watcher.py` | Filesystem watcher | -- | Monitors Inbox/ |
| `gmail_watcher.py` | Gmail watcher | -- | Monitors IMAP inbox |
| `whatsapp_watcher.py` | WhatsApp watcher | -- | Monitors Inbox/whatsapp/ |
| `watcher_manager.py` | Watcher orchestrator | -- | Runs all watchers |
| `approval_gate.py` | Approval module | -- | Manages approvals |
| `linkedin_post_generator.py` | LinkedIn drafts | -- | Generates post drafts |
| `mcp_email_server.py` | Email MCP server | -- | Sends email via SMTP |

---

## Troubleshooting

### Task is not being processed
- Verify the file is in `Needs_Action/`, not `Inbox/`
- Check YAML frontmatter is valid (dashes, colons, spacing)
- Ensure `status: pending` is set
- Check `Dashboard.md` Alerts for rejection messages
- Run `python3 silver_loop.py` to trigger processing

### Watcher is not detecting files
- Confirm watcher is running: check `watcher.log`
- Files must be in the correct directory:
  - General files → `Inbox/`
  - WhatsApp exports → `Inbox/whatsapp/`
- Hidden files (starting with `.`) are ignored
- Wait at least the poll interval (default 30 seconds)

### Gmail watcher fails
- Check credentials in `config.json` (email + app_password)
- Ensure 2FA is enabled on Google account
- Verify App Password is correct (16 chars, no spaces)
- Test: `python3 gmail_watcher.py --once`
- Check if "Less secure apps" is NOT what you need — use App Password instead

### WhatsApp watcher not creating tasks
- File must be `.txt` format (not .pdf, .zip, etc.)
- File must be in `Inbox/whatsapp/` (not `Inbox/`)
- Check if file was already processed: look in `.whatsapp_registry.json`
- To reprocess: delete the file's hash from `.whatsapp_registry.json`

### Approval is stuck
- Check `Pending_Approval/` for pending approval files
- Open the file and change `status: pending` to `status: approved`
- Verify the approval hasn't expired (check `expires:` in frontmatter)
- Re-run `python3 silver_loop.py` after approving

### LinkedIn draft not generated
- Task must be classified as `marketing` (check type field or keywords)
- Approval must be granted first (check Pending_Approval/)
- Run with `--dry-run` to see classification: `python3 silver_loop.py --dry-run`

### Email sending fails
- Check SMTP credentials in `config.json`
- Verify approval exists and is not expired
- Check `Logs/` for error details
- Ensure MCP server config in `.claude/settings.json` is correct

### Scheduling not working (WSL2)
- WSL2 cron may not run in background — use Windows Task Scheduler instead
- Program: `wsl`, Arguments: `bash -c "cd /mnt/e/AI_Employ_Vault/Bronce-tiar && ./run_silver.sh full"`
- Test manually first: `./run_silver.sh full`

### System seems stuck
```bash
# Check current state
cat Dashboard.md

# Check for errors in log
tail -50 watcher.log

# Check for pending approvals blocking tasks
ls Pending_Approval/

# Run dry-run to diagnose
python3 silver_loop.py --dry-run
```

---

## Quick Reference

```bash
# ── Full Pipeline ──
./run_silver.sh full              # watchers + reasoning loop
./run_silver.sh --watchers        # watchers only (detect inputs)
./run_silver.sh --loop            # reasoning loop only (process tasks)

# ── Individual Watchers ──
python3 watcher.py                # filesystem (continuous)
python3 gmail_watcher.py --once   # gmail (single scan)
python3 whatsapp_watcher.py --once # whatsapp (single scan)
python3 watcher_manager.py        # all watchers (continuous)
python3 watcher_manager.py --once  # all watchers (single scan)

# ── Reasoning Loop ──
python3 silver_loop.py            # process all pending tasks
python3 silver_loop.py --dry-run  # analyze only, no execution

# ── LinkedIn Post ──
python3 linkedin_post_generator.py "topic" "audience" goal

# ── Scheduling ──
./schedule_setup.sh               # install daily cron
./schedule_setup.sh --status      # check schedule
./schedule_setup.sh --remove      # remove schedule

# ── Utilities ──
./backup.sh                       # create vault backup
tail -f watcher.log               # live log monitoring
cat Dashboard.md                  # system state

# ── Drop Inputs ──
cp my-file.md Inbox/              # filesystem watcher picks up
cp "WhatsApp Chat.txt" Inbox/whatsapp/  # WhatsApp watcher picks up

# ── Create Task Directly ──
cat > Needs_Action/my-task.md << 'EOF'
---
type: general
priority: medium
status: pending
created: 2026-03-04T12:00:00Z
source: manual_drop
---

## Task Description
Describe your task here.

## Required Outcome
Define the expected result.

## Processing Checklist
- [ ] analyze task
- [ ] generate plan
- [ ] complete objective
EOF
```

---

*This vault is designed to be opened in [Obsidian](https://obsidian.md) for a visual dashboard experience, but works entirely from the command line.*
