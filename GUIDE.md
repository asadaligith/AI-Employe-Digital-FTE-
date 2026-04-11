# Gold Tier AI Employee — Complete Guide

> A local-first, file-driven autonomous AI agent with continuous operation, retry handling, Odoo ERP integration, social media management, CEO reports, business audits, and human-in-the-loop approval workflows.

---

## Table of Contents

1. [What Is This?](#what-is-this)
2. [Architecture Overview](#architecture-overview)
3. [Prerequisites](#prerequisites)
4. [Quick Start (5 Steps)](#quick-start)
5. [Gmail Setup](#gmail-setup)
6. [WhatsApp Setup](#whatsapp-setup)
7. [Running the System](#running-the-system)
8. [Gold Tier: Continuous Operation](#gold-tier-continuous-operation)
9. [Gold Tier: Retry & Error Handling](#gold-tier-retry--error-handling)
10. [Gold Tier: Odoo ERP Integration](#gold-tier-odoo-erp-integration)
11. [Gold Tier: Social Media Management](#gold-tier-social-media-management)
12. [Gold Tier: CEO Reports & Business Audits](#gold-tier-ceo-reports--business-audits)
13. [Scheduling (Automated Runs)](#scheduling)
14. [Approval Workflow](#approval-workflow)
15. [LinkedIn Post Generation](#linkedin-post-generation)
16. [Email Sending (MCP)](#email-sending)
17. [Task File Schema](#task-file-schema)
18. [Task Types and Examples](#task-types-and-examples)
19. [Core Files Reference](#core-files-reference)
20. [Troubleshooting](#troubleshooting)
21. [Quick Reference Cheat Sheet](#quick-reference)

---

## What Is This?

The Gold Tier AI Employee is a **continuously running autonomous task-processing agent** that operates entirely through the filesystem. It builds on Bronze and Silver foundations with:

- **Continuous Operation** — runs in a loop with configurable cycle intervals (default 5 min)
- **In_Progress Tracking** — tasks move Needs_Action → In_Progress → Done with full visibility
- **Retry & Error Handling** — exponential backoff, max attempts, persistent retry state
- **3 Watchers** — filesystem, Gmail, and WhatsApp monitoring (from Silver)
- **AI Reasoning** — Claude Code CLI for intelligent task processing
- **Odoo ERP Integration** — invoices, payments, contacts via JSON-RPC + MCP server
- **Social Media Management** — Facebook, Instagram, Twitter/X drafts + API posting + MCP server
- **CEO Weekly Reports** — automated briefings from system activity data
- **Business Audits** — weekly efficiency analysis with A-D scoring
- **Approval Gates** — human-in-the-loop for sensitive actions (email, LinkedIn, finance, Odoo, social media)
- **Structured Action Logging** — JSONL audit trail for all Gold Tier actions

**Key principles:**
- No chat interface — communication happens through files
- Continuous 10-phase execution pipeline (extends Silver's 7-phase)
- Full audit trail — every task and action is preserved, never deleted
- Local-first with controlled external actions (only after human approval)
- Obsidian-compatible — open the vault in Obsidian for a visual dashboard
- All integrations (Odoo, social media) are opt-in — disabled by default

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
├── In_Progress/              # Tasks currently being executed (Gold)
├── Done/                     # Completed tasks (permanent archive)
├── Plans/                    # Generated execution plans
├── Pending_Approval/         # Human approval requests & drafts
├── Approved/                 # Executed approval archive (Gold)
├── Reports/                  # CEO briefings & audit reports (Gold)
├── Logs/                     # Audit trail (actions.jsonl + markdown logs)
├── Backups/                  # Timestamped .tar.gz vault archives
│
├── gold_loop.py              # Gold: 10-phase continuous loop orchestrator
├── silver_loop.py            # Silver: 7-phase reasoning loop (reused by Gold)
├── error_handler.py          # Gold: retry engine with exponential backoff
├── action_logger.py          # Gold: structured JSONL action logging
├── odoo_client.py            # Gold: Odoo ERP JSON-RPC client
├── social_media_manager.py   # Gold: FB/IG/Twitter draft + API posting
├── ceo_report_generator.py   # Gold: weekly CEO briefing generator
├── business_audit.py         # Gold: weekly efficiency audit
│
├── watcher.py                # Filesystem perception layer (Inbox/)
├── gmail_watcher.py          # Gmail IMAP perception layer
├── whatsapp_watcher.py       # WhatsApp Web perception layer
├── watcher_manager.py        # Unified watcher orchestrator (all 3)
├── approval_gate.py          # Human-in-the-loop module
├── linkedin_post_generator.py # LinkedIn post draft generator
├── mcp_email_server.py       # MCP server for outbound email
├── mcp_odoo_server.py        # Gold: MCP server for Odoo operations
├── mcp_social_server.py      # Gold: MCP server for social media
│
├── run_gold.sh               # Gold tier entry point (continuous or single)
├── run_silver.sh             # Silver tier entry point (legacy)
├── schedule_setup.sh         # Cron/scheduler installer
├── backup.sh                 # Vault backup utility
└── watcher.log               # Watcher and agent event log
```

### Gold Tier Pipeline (10 Phases)

```
Phase 1:  Initialize      → Load policies, ensure Gold dirs
Phase 2:  Run Watchers    → Subprocess watcher_manager.py --once
Phase 3:  Analyze         → Scan Needs_Action/, classify tasks
Phase 4:  Plan            → Validate schemas, generate Plan.md files
Phase 5:  Track           → Move tasks: Needs_Action/ → In_Progress/
Phase 6:  Execute         → Run with retry wrapper (exponential backoff)
Phase 7:  Verify          → Post-execution checks (result, status, location)
Phase 8:  Report Check    → Generate CEO report / audit if scheduled
Phase 9:  Update Dashboard → Enhanced metrics (in-progress, retries, verified)
Phase 10: Sleep or Exit   → Continuous: sleep N seconds. --once: exit.
```

### Lifecycle Flow

```
External Input ──► Inbox/ ──► Watchers ──► Needs_Action/ ──► In_Progress/ ──► Done/
     │                          │                │               │               │
     ├── File drop              ├── watcher.py   │               │ (gold_loop)   ├── Plans/
     ├── Gmail                  ├── gmail_watcher │               │               ├── Pending_Approval/
     └── WhatsApp               └── whatsapp     │               ├── Retry ──►   ├── Reports/ (weekly)
                                                  │               │  (backoff)    ├── Dashboard.md
                                                  │               │               └── Logs/actions.jsonl
                                                  │               │
                                                  │               └── On failure → back to Needs_Action/
                                                  │
                                                  └── Approval gate check
                                                       (email, LinkedIn, finance,
                                                        Odoo, social media)
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
python3 -c "import gold_loop; import silver_loop; import action_logger; import error_handler; print('All modules OK')"
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

### Step 5 — Run the Gold Tier loop

```bash
# Single cycle (recommended for first run)
python3 gold_loop.py --once

# Or use the full entry point
./run_gold.sh --once

# Continuous mode (runs every 5 minutes)
./run_gold.sh
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

### Option A: Gold Tier Continuous (Recommended)

```bash
./run_gold.sh
```

This runs the Gold Tier in continuous mode:
1. Watchers scan for new inputs each cycle
2. Tasks move through Needs_Action → In_Progress → Done
3. Failed tasks are retried with exponential backoff
4. CEO reports and audits are generated on schedule
5. Sleeps 5 minutes between cycles (configurable)
6. Press Ctrl+C for graceful shutdown

### Option B: Gold Tier Single Cycle

```bash
./run_gold.sh --once
```

Runs one full 10-phase cycle and exits.

### Option C: Dry Run (Test Mode)

```bash
python3 gold_loop.py --dry-run
```

Analyzes and plans tasks without executing them.

### Option D: Silver Tier (Legacy)

```bash
./run_silver.sh full    # Silver 7-phase pipeline
```

### Option E: Individual Components

```bash
# Watchers
python3 watcher_manager.py --once    # all watchers (single scan)
python3 watcher.py                   # filesystem only
python3 gmail_watcher.py --once      # gmail only
python3 whatsapp_watcher.py --once   # whatsapp only

# Gold loop only
python3 gold_loop.py --once

# Reports on demand
python3 ceo_report_generator.py
python3 business_audit.py
```

### Monitoring

```bash
# Watch the log in real time
tail -f watcher.log

# Check system state
cat Dashboard.md

# See pending / in-progress / completed tasks
ls Needs_Action/
ls In_Progress/
ls Done/

# See pending approvals and reports
ls Pending_Approval/
ls Reports/

# See action log
tail -20 Logs/actions.jsonl
```

---

## Gold Tier: Continuous Operation

Gold Tier replaces Silver's single-run model with a continuous loop.

### How It Works

1. `gold_loop.py` runs a 10-phase cycle
2. After each cycle, it sleeps for `cycle_interval_seconds` (default: 300s = 5 min)
3. On each cycle it runs watchers, processes all pending tasks, and checks for scheduled reports
4. Tasks are moved to `In_Progress/` during execution for visibility
5. On success: task moves to `Done/`. On failure: task returns to `Needs_Action/` for retry.

### Configuration

In `config.json`, add or edit the `gold` section:

```json
{
  "gold": {
    "enabled": true,
    "cycle_interval_seconds": 300,
    "max_retry_attempts": 3,
    "retry_base_delay_seconds": 5,
    "report_day": "monday",
    "report_hour_utc": 7,
    "audit_day": "friday",
    "audit_hour_utc": 18
  }
}
```

### Graceful Shutdown

Press **Ctrl+C** or send SIGTERM. The loop finishes the current cycle, moves any In_Progress tasks back to Needs_Action, and exits cleanly.

---

## Gold Tier: Retry & Error Handling

Failed tasks are automatically retried with exponential backoff.

### How It Works

1. When a task fails during execution, the error is recorded
2. On the next cycle, `should_retry()` checks if the task is eligible
3. Retry delay: `delay = min(base_delay * 2^attempt, max_delay)`
4. Default: 3 attempts, 5s base, 300s max
5. After max retries: task is marked `status: blocked` and a dashboard alert is raised

### Retry State

State is persisted in `.gold_retry_state.json` so retries survive across process restarts:

```json
{
  "TASK_xyz.md": {
    "attempts": 2,
    "last_error": "connection timeout",
    "last_attempt": "2026-04-11T10:00:00Z",
    "next_retry_after": "2026-04-11T10:00:20Z"
  }
}
```

### Clearing Retry State

```bash
# View current retry state
cat .gold_retry_state.json | python3 -m json.tool

# Clear all retry state (allows immediate retry for all tasks)
rm .gold_retry_state.json

# Old retry states (>7 days) are automatically cleaned up each cycle
```

---

## Gold Tier: Odoo ERP Integration

Connect to Odoo for invoice, payment, and contact management.

### Setup

1. Add Odoo credentials to `config.json`:

```json
{
  "odoo": {
    "enabled": true,
    "url": "https://your-odoo-instance.com",
    "database": "your-db",
    "username": "admin",
    "password": "your-api-key",
    "timeout": 30
  }
}
```

2. The MCP server is already configured in `.claude/settings.json` as `vault-odoo`.

### Available Operations

| Operation | MCP Tool | Approval Required |
|-----------|----------|-------------------|
| List invoices | `odoo_get_invoices` | No |
| List payments | `odoo_get_payments` | No |
| List contacts | `odoo_get_contacts` | No |
| Create invoice | `odoo_create_invoice` | Yes |
| Financial summary | `odoo_financial_summary` | No |

### Testing

```bash
python3 odoo_client.py --test   # dry-run config check
```

---

## Gold Tier: Social Media Management

Generate post drafts for Facebook, Instagram, and Twitter/X. Optionally post via API.

### How It Works

1. Generate a draft: creates `Pending_Approval/SOCIAL_*.md`
2. Human reviews and approves (change `status: pending_approval` to `status: approved`)
3. If API keys are configured, posts automatically. Otherwise marks as "ready for manual posting".

### Setup (Optional — for API posting)

Add API credentials to `config.json`:

```json
{
  "social_media": {
    "facebook": {"enabled": true, "page_id": "...", "page_access_token": "..."},
    "instagram": {"enabled": true, "business_account_id": "...", "access_token": "..."},
    "twitter": {"enabled": true, "api_key": "...", "api_secret": "...", "access_token": "...", "access_secret": "..."}
  }
}
```

Without API credentials, the system works in **draft-only mode**.

### Character Limits

| Platform | Limit |
|----------|-------|
| Twitter/X | 280 |
| Instagram | 2,200 |
| Facebook | 63,206 |

### Testing

```bash
python3 social_media_manager.py --test   # generates a test Twitter draft
```

---

## Gold Tier: CEO Reports & Business Audits

### CEO Weekly Report

Generated automatically on schedule (default: Monday 7:00 UTC), or on demand.

**Contents**: Executive Summary, Task Performance, Communication Activity, Financial Overview (if Odoo), Social Media, Issues & Alerts, AI Recommendations.

```bash
python3 ceo_report_generator.py                   # generate now
python3 ceo_report_generator.py --since 2026-04-01 # custom period
./run_gold.sh --report                             # via entry point
```

**Output**: `Reports/CEO_REPORT_WEEK_YYYY-MM-DD.md`

### Business Audit

Generated automatically on schedule (default: Friday 18:00 UTC), or on demand.

**Contents**: Efficiency Scores (A-D), Task Throughput, Approval Pipeline, Error Analysis, Watcher Health, Optimization Suggestions.

```bash
python3 business_audit.py    # generate now
./run_gold.sh --audit        # via entry point
```

**Output**: `Reports/AUDIT_WEEK_YYYY-MM-DD.md`

### Efficiency Scores

| Score | Meaning |
|-------|---------|
| A | Excellent — no action needed |
| B | Good — minor improvements possible |
| C | Fair — attention recommended |
| D | Poor — immediate action needed |

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
7. Arguments: `bash -c "cd /mnt/e/AI_Employ_Vault/Bronce-tiar && ./run_gold.sh --once"`
8. Click **Finish**

### Manual Execution

If you prefer manual control:

```bash
# Run whenever you want
cd /mnt/e/AI_Employ_Vault/Bronce-tiar
./run_gold.sh --once    # single cycle
./run_gold.sh           # continuous (press Ctrl+C to stop)
```

---

## Approval Workflow

Sensitive actions require human approval before execution. This includes:
- **Outbound email** (send_email)
- **LinkedIn posts** (linkedin_post)
- **Financial transactions** (financial_transaction)
- **Odoo invoice creation** (odoo_create_invoice) — Gold Tier
- **Social media posts** (facebook_post, instagram_post, twitter_post) — Gold Tier

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

| File | Role | Tier | Notes |
|------|------|------|-------|
| `Dashboard.md` | System state | All | Updated after every task |
| `Company_Handbook.md` | Policy rules | All | Human-maintained |
| `config.json` | Credentials | All | Contains sensitive data |
| `watcher.log` | Event log | All | Continuous append |
| **Gold Tier** | | | |
| `gold_loop.py` | Continuous loop orchestrator | Gold | 10-phase pipeline |
| `error_handler.py` | Retry engine | Gold | Exponential backoff |
| `action_logger.py` | Structured action logging | Gold | JSONL + markdown |
| `odoo_client.py` | Odoo ERP client | Gold | JSON-RPC, stdlib only |
| `social_media_manager.py` | Social media drafts + API | Gold | FB/IG/Twitter |
| `mcp_odoo_server.py` | Odoo MCP server | Gold | JSON-RPC stdio |
| `mcp_social_server.py` | Social media MCP server | Gold | JSON-RPC stdio |
| `ceo_report_generator.py` | CEO weekly report | Gold | Reports/ output |
| `business_audit.py` | Efficiency audit | Gold | Reports/ output |
| `run_gold.sh` | Gold entry point | Gold | Continuous or single |
| **Silver Tier** | | | |
| `silver_loop.py` | Silver orchestrator | Silver | 7-phase, reused by Gold |
| `watcher.py` | Filesystem watcher | Bronze | Monitors Inbox/ |
| `gmail_watcher.py` | Gmail watcher | Silver | Monitors IMAP inbox |
| `whatsapp_watcher.py` | WhatsApp watcher | Silver | Monitors WhatsApp Web |
| `watcher_manager.py` | Watcher orchestrator | Silver | Runs all watchers |
| `approval_gate.py` | Approval module | Silver | Updated for Gold actions |
| `linkedin_post_generator.py` | LinkedIn drafts | Silver | Draft generation |
| `mcp_email_server.py` | Email MCP server | Silver | SMTP via approval |

---

## Troubleshooting

### Task is not being processed
- Verify the file is in `Needs_Action/`, not `Inbox/` or `In_Progress/`
- Check YAML frontmatter is valid (dashes, colons, spacing)
- Ensure `status: pending` is set (not `blocked`)
- Check `Dashboard.md` Alerts for rejection messages
- Check `.gold_retry_state.json` for max-retries-exceeded entries
- Run `python3 gold_loop.py --once` to trigger processing

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

### Task stuck in In_Progress/
- This means the Gold loop was interrupted during execution
- The task will be moved back to Needs_Action/ on the next cycle automatically
- Or manually: `mv In_Progress/TASK_xyz.md Needs_Action/`

### Task marked as blocked
- Check `.gold_retry_state.json` — task exceeded max retry attempts
- Fix the underlying issue, then clear the retry state:
  ```bash
  python3 -c "from error_handler import clear_retry_state; clear_retry_state('TASK_xyz.md')"
  ```
- Change `status: blocked` back to `status: pending` in the task file

### Odoo connection fails
- Check `config.json` odoo section (url, database, username, password)
- Ensure `"enabled": true` is set
- Test: `python3 odoo_client.py --test`
- Check Logs/ for error details

### Social media draft not generated
- Ensure `social_media_manager.py` is importable: `python3 -c "import social_media_manager; print('OK')"`
- Check character limits — Twitter has 280 char max
- Test: `python3 social_media_manager.py --test`

### Scheduling not working (WSL2)
- WSL2 cron may not run in background — use Windows Task Scheduler instead
- Program: `wsl`, Arguments: `bash -c "cd /mnt/e/AI_Employ_Vault/Bronce-tiar && ./run_gold.sh --once"`
- For continuous mode, run `./run_gold.sh` in a persistent terminal

### System seems stuck
```bash
# Check current state
cat Dashboard.md

# Check for errors in log
tail -50 watcher.log

# Check action log for recent failures
tail -20 Logs/actions.jsonl

# Check for pending approvals blocking tasks
ls Pending_Approval/

# Check retry state
cat .gold_retry_state.json 2>/dev/null || echo "No retry state"

# Check In_Progress for stuck tasks
ls In_Progress/

# Run dry-run to diagnose
python3 gold_loop.py --dry-run
```

---

## Quick Reference

```bash
# ── Gold Tier (Recommended) ──
./run_gold.sh                     # continuous loop (default, Ctrl+C to stop)
./run_gold.sh --once              # single cycle then exit
./run_gold.sh --dry-run           # analyze only, no execution
./run_gold.sh --report            # generate CEO report now
./run_gold.sh --audit             # run business audit now

# ── Silver Tier (Legacy) ──
./run_silver.sh full              # watchers + 7-phase reasoning loop

# ── Individual Watchers ──
python3 watcher_manager.py --once  # all watchers (single scan)
python3 watcher_manager.py        # all watchers (continuous)
python3 watcher.py                # filesystem only
python3 gmail_watcher.py --once   # gmail only
python3 whatsapp_watcher.py --once # whatsapp only

# ── Gold Loop Only ──
python3 gold_loop.py              # continuous
python3 gold_loop.py --once       # single cycle
python3 gold_loop.py --dry-run    # analyze only

# ── Reports & Audits ──
python3 ceo_report_generator.py   # CEO weekly report
python3 business_audit.py         # efficiency audit

# ── Social Media ──
python3 social_media_manager.py --test  # generate test draft

# ── LinkedIn Post ──
python3 linkedin_post_generator.py "topic" "audience" goal

# ── Odoo ──
python3 odoo_client.py --test     # config check

# ── Scheduling ──
./schedule_setup.sh               # install daily cron
./schedule_setup.sh --status      # check schedule
./schedule_setup.sh --remove      # remove schedule

# ── Utilities ──
./backup.sh                       # create vault backup
tail -f watcher.log               # live log monitoring
cat Dashboard.md                  # system state
tail -20 Logs/actions.jsonl       # recent actions
cat .gold_retry_state.json        # retry state

# ── Drop Inputs ──
cp my-file.md Inbox/              # filesystem watcher picks up
cp "WhatsApp Chat.txt" Inbox/whatsapp/  # WhatsApp watcher picks up

# ── Create Task Directly ──
cat > Needs_Action/my-task.md << 'EOF'
---
type: general
priority: medium
status: pending
created: 2026-04-11T12:00:00Z
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

*This vault is designed to be opened in [Obsidian](https://obsidian.md) for a visual dashboard experience, but works entirely from the command line. Gold Tier adds continuous operation, retry handling, Odoo ERP, social media, CEO reports, and business audits on top of the Silver foundation.*
