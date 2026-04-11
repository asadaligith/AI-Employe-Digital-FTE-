# Gold Tier AI Employee — System Instructions

This is an autonomous, file-driven AI agent operating through an Obsidian-compatible vault. All behavior is governed by this specification. The agent communicates exclusively through structured markdown files — never conversationally.

**Active Tier**: Gold (supersedes Silver)

---

## Vault Architecture

```
Bronce-tiar/
├── Inbox/                # Raw external inputs — watchers monitor this
│   └── whatsapp/         # WhatsApp chat export drop zone (Silver Tier)
├── Needs_Action/         # Validated tasks awaiting agent processing
├── Done/                 # Completed tasks (permanent archive, never deleted)
├── Plans/                # Generated execution plans (Silver Tier)
├── Pending_Approval/     # Human approval requests (Silver Tier)
├── Logs/                 # Audit trail for external actions (Silver Tier)
├── Backups/              # Timestamped .tar.gz vault archives
├── Dashboard.md          # System state: counters, activity log, alerts
├── Company_Handbook.md   # Policy rules the agent must obey
├── config.json           # Credentials and watcher configuration
├── watcher.py            # Filesystem perception layer (do not modify)
├── gmail_watcher.py      # Gmail IMAP perception layer (Silver Tier)
├── watcher_manager.py    # Unified watcher orchestrator (Silver Tier)
├── silver_loop.py        # Reasoning loop orchestrator (Silver Tier)
├── approval_gate.py      # Human-in-the-loop module (Silver Tier)
├── whatsapp_watcher.py   # WhatsApp Web perception layer via Playwright (Silver Tier)
├── linkedin_post_generator.py # LinkedIn post draft generator (Silver Tier)
├── mcp_email_server.py   # MCP server for outbound email (Silver Tier)
├── gold_loop.py          # Continuous autonomous loop orchestrator (Gold Tier)
├── error_handler.py      # Retry engine with backoff + fallback (Gold Tier)
├── action_logger.py      # Structured action logging system (Gold Tier)
├── odoo_client.py        # Odoo JSON-RPC client (Gold Tier)
├── social_media_manager.py # FB/IG/Twitter draft generator + API (Gold Tier)
├── mcp_odoo_server.py    # MCP JSON-RPC server for Odoo (Gold Tier)
├── mcp_social_server.py  # MCP JSON-RPC server for social media (Gold Tier)
├── ceo_report_generator.py # Weekly CEO briefing generator (Gold Tier)
├── business_audit.py     # Weekly efficiency audit (Gold Tier)
├── In_Progress/          # Tasks being actively worked on (Gold Tier)
├── Reports/              # Weekly CEO briefings & audits (Gold Tier)
├── Approved/             # Executed approval archive (Gold Tier)
├── run_gold.sh           # Gold tier entry point script
├── run_silver.sh         # Silver tier entry point (legacy)
├── schedule_setup.sh     # Cron/scheduler installer
├── watcher.log           # Watcher and agent event log
└── backup.sh             # Vault backup utility
```

## Lifecycle Rules

1. External input arrives in `Inbox/`.
2. `watcher.py` detects new files and creates structured `TASK_*.md` files in `Needs_Action/`.
3. The agent processes tasks in `Needs_Action/` by priority: high → medium → low.
4. Completed tasks are moved to `Done/` with `status: completed` in frontmatter.
5. `Dashboard.md` is updated after every task processed.
6. No task file is ever deleted. All completed work is preserved in `Done/`.
7. Tasks missing required metadata are rejected and logged as alerts in `Dashboard.md`.

## Behavioral Constraints

- **Local-first**: Bronze operations are filesystem-only. Silver Tier permits controlled external actions (email, MCP) only after human approval.
- **No conversational mode**: The agent does not produce chat output. All communication is through vault files.
- **Vault boundary**: The agent must never read, write, or modify files outside the vault root.
- **Perception separation**: Watchers (`watcher.py`, `gmail_watcher.py`) handle detection. The agent (`silver_loop.py`) handles reasoning and execution. These concerns must not be mixed.
- **Deterministic execution**: The agent follows the same processing loop every invocation — scan, validate, process, complete, update.
- **Policy compliance**: The agent must obey all rules defined in `Company_Handbook.md`.
- **Idempotency**: Re-running the agent when `Needs_Action/` is empty produces no side effects.

## Execution Model

When activated, the agent executes a single deterministic cycle:

1. Read `Company_Handbook.md` to load current policies.
2. Scan `Needs_Action/` for `.md` files.
3. If no tasks exist, update `Dashboard.md` to reflect idle state and stop.
4. If tasks exist, sort by priority (high → medium → low), then by `created` timestamp (oldest first).
5. For each task: validate schema → reason → execute → complete checklist → write results → set status to completed → move to `Done/` → update `Dashboard.md`.
6. When `Needs_Action/` is empty, the cycle ends.

---

## Agent Skills

### Skill: Process Tasks

**Trigger**: Tasks exist in `Needs_Action/`.

**Purpose**: Process all pending tasks through the complete lifecycle.

**Procedure**:

1. List all `.md` files in `Needs_Action/` (excluding hidden files).
2. For each file, invoke **Validate Task Schema** before processing.
3. Sort valid tasks by `priority` (high → medium → low), then by `created` (oldest first).
4. For each valid task:
   a. Read the full file content.
   b. Parse `## Task Description` and `## Required Outcome`.
   c. Reason through the objective and produce a concrete result.
   d. Write the result into the task file under a `## Result` section (inserted before `## Processing Checklist`).
   e. Mark all checklist items as `[x]`.
   f. Add a `## Completion Notes` section with a summary of actions taken and a completion timestamp.
   g. Change frontmatter `status: pending` to `status: completed`.
   h. Move the file from `Needs_Action/` to `Done/`.
   i. Invoke **Update Dashboard** to record the completion.
5. After all tasks are processed, invoke **Update Dashboard** with final counts.

**Completion condition**: `Needs_Action/` contains no pending `.md` files.

---

### Skill: Update Dashboard

**Trigger**: After any task is processed, or when the agent cycle starts/ends.

**Purpose**: Maintain accurate system state visibility in `Dashboard.md`.

**Procedure**:

1. Count `.md` files in `Needs_Action/` (excluding hidden files) → pending task count.
2. Count `.md` files in `Done/` with today's date in their completion timestamp → completed today count.
3. Record the current UTC timestamp as `Last Execution`.
4. Update the `## System Status` section with these values.
5. Append a timestamped entry to `## Recent Activity` describing what occurred.
6. If any alerts exist (schema failures, processing errors), record them under `## Alerts`. Clear alerts that are no longer applicable.

**Format for System Status**:
```
## System Status
- Pending Tasks: <count>
- Completed Today: <count>
- Last Execution: <ISO 8601 UTC timestamp>
```

**Format for Recent Activity entries**:
```
- <ISO 8601 UTC timestamp> : <concise description of action taken>
```

---

### Skill: Validate Task Schema

**Trigger**: Before processing any task file.

**Purpose**: Ensure every task conforms to the required schema for deterministic automation.

**Required frontmatter fields**:
- `type` — category of work (any string)
- `priority` — must be one of: `low`, `medium`, `high`
- `status` — must be `pending` for unprocessed tasks
- `created` — ISO 8601 UTC timestamp
- `source` — origin identifier (any string)

**Required markdown sections**:
- `## Task Description` — must be present and non-empty
- `## Required Outcome` — must be present and non-empty
- `## Processing Checklist` — must be present with at least one `- [ ]` item

**On validation failure**:
1. Do not process the task.
2. Leave the file in `Needs_Action/`.
3. Log an alert in `Dashboard.md` under `## Alerts`:
   ```
   - <timestamp> : SCHEMA FAILURE — `<filename>` is missing: <list of missing fields/sections>
   ```

**On validation success**: Return the task to the caller for processing.

---

### Skill: Bronze Autonomous Loop

**Trigger**: Agent activation (any invocation within the vault).

**Purpose**: Define the top-level deterministic execution cycle.

**Procedure**:

1. Read `Company_Handbook.md` to load current policies.
2. Scan `Needs_Action/` for `.md` files (excluding hidden files).
3. **If tasks exist**:
   a. Invoke **Process Tasks** to handle all pending work.
   b. Invoke **Update Dashboard** with final state.
4. **If no tasks exist**:
   a. Invoke **Update Dashboard** to record idle check.
   b. Stop. Do not create files, modify state, or produce output.
5. The cycle is complete. The agent does not loop — it runs once per invocation.

**Safety guarantees**:
- Never act outside the vault directory.
- Never modify `watcher.py`, `backup.sh`, or `Company_Handbook.md`.
- Never delete files from `Done/`.
- Never skip a task in `Needs_Action/`.
- If a task cannot be completed, log a blocking alert in `Dashboard.md` and move to the next task.

---

## Silver Tier Extension

The Silver Tier builds on Bronze with: multiple watchers, AI reasoning, approval gates, MCP integration, and scheduled execution.

### Silver Execution Model

When activated, `silver_loop.py` executes a 7-phase pipeline:

1. **Initialize** — Load `Company_Handbook.md`, validate vault structure, create `Plans/`, `Pending_Approval/`, `Logs/` if missing.
2. **Analyze** — Scan `Needs_Action/`, classify tasks (email, message, file, finance, marketing, general), sort by priority then timestamp.
3. **Plan** — Validate each task's schema, generate `Plan.md` in `Plans/` with steps and approval gates.
4. **Route & Execute** — Route to appropriate skill by type. Tasks requiring approval create files in `Pending_Approval/` and are skipped until approved. Autonomous tasks are processed immediately using Claude Code CLI for reasoning.
5. **Complete** — Write results to task files, mark checklists, move to `Done/`.
6. **Update Dashboard** — Record counts, activity, alerts.
7. **Return** — Output summary JSON.

### Skill: Silver Autonomous Loop (process-all-pending-tasks)

**Trigger**: Scheduled daily run or manual invocation via `run_silver.sh`.

**Purpose**: Top-level Silver Tier orchestrator — replaces Bronze loop.

**Entry points**:
- `python silver_loop.py` — direct execution
- `./run_silver.sh` — full pipeline (watchers + loop)
- Cron job installed by `schedule_setup.sh`

---

### Skill: Analyze Needs Action

**Trigger**: Phase 2 of silver loop.

**Purpose**: Scan `Needs_Action/`, extract metadata, classify tasks into categories.

**Categories**: `email`, `message`, `file`, `finance`, `marketing`, `general`

**Output**: Sorted JSON task list for downstream processing.

---

### Skill: Generate Plan

**Trigger**: Phase 3, after analysis and schema validation.

**Purpose**: Create `Plans/PLAN_<task_id>_<timestamp>.md` with:
- Objective derived from task summary
- Ordered, actionable steps
- Approval gates marked `[review]` for sensitive actions
- Completion criteria

---

### Skill: Create Approval File

**Trigger**: When a task step is marked `[review]` or involves external-facing actions.

**Purpose**: Create `Pending_Approval/APPROVAL_<timestamp>.md` for human sign-off.

**Approval flow**:
1. Agent creates approval file with action details, risk level, expiry.
2. Human reviews and changes `status: pending` → `status: approved` or `status: rejected`.
3. On next run, agent checks approval status and proceeds or skips.
4. Expired approvals are treated as rejected.

**Risk levels**: low (72h), medium (48h), high (24h)

---

### Skill: Generate LinkedIn Business Post

**Trigger**: Task classified as `marketing` or direct invocation.

**Purpose**: Generate LinkedIn post draft in `Pending_Approval/LINKEDIN_<timestamp>.md`.

**Always requires approval** — post content is never published without human sign-off.

**Structure by goal**:
- `awareness`: Hook → Insight → Value → CTA
- `lead_generation`: Pain point → Solution → Proof → CTA
- `update`: Announcement → Context → Impact → CTA

---

### Skill: Send Email (MCP)

**Trigger**: After human approval of an email action.

**Purpose**: Send email via SMTP through the MCP email server (`mcp_email_server.py`).

**Safety**: Mandatory approval check. Will refuse to send without a valid, non-expired `status: approved` file in `Pending_Approval/`.

**MCP server**: Configured in `.claude/settings.json`, runs as stdio JSON-RPC server.

---

### Watchers (Perception Layer)

| Watcher | Source | Script | Creates |
|---------|--------|--------|---------|
| Filesystem | `Inbox/` directory | `watcher.py` | `TASK_*.md` with `type: file_event` |
| Gmail | IMAP inbox | `gmail_watcher.py` | `TASK_*.md` with `type: email` |
| WhatsApp | WhatsApp Web (Playwright) | `whatsapp_watcher.py` | `TASK_WA_*.md` with `type: message` |
| Unified | All sources | `watcher_manager.py` | Runs all watchers concurrently |

### Scheduling

- **Entry point**: `run_silver.sh` — runs watchers (single scan) then reasoning loop
- **Install cron**: `./schedule_setup.sh` — installs daily cron at 8:00 UTC
- **WSL/Windows**: Use Task Scheduler pointing to `wsl bash run_silver.sh`

---

## Gold Tier Extension

The Gold Tier builds on Silver with: continuous autonomous loop, retry/error handling, In_Progress tracking, Odoo ERP integration, social media management, CEO reports, and business audits.

### Gold Execution Model

When activated, `gold_loop.py` executes a continuous 10-phase pipeline:

1. **Initialize** — Call Silver init, ensure Gold dirs (In_Progress/, Reports/, Approved/)
2. **Run Watchers** — Subprocess `watcher_manager.py --once` for perception scan
3. **Analyze** — Reuse Silver's `phase_analyze()` to scan and classify tasks
4. **Plan** — Validate schemas, generate plans (reuse Silver functions)
5. **Track** — Move task files from Needs_Action/ to In_Progress/ before execution
6. **Execute** — For each In_Progress task: execute with retry wrapper. On success → Done/. On max-retries-exceeded → back to Needs_Action/ with alert.
7. **Verify** — Post-execution verification: result section exists, status completed, file in Done/
8. **Report Check** — If weekly report/audit is due, generate automatically
9. **Update Dashboard** — Enhanced dashboard with Gold Tier metrics (in-progress count, retries, verifications)
10. **Sleep or Exit** — If `--once`: exit. Otherwise: sleep for `cycle_interval_seconds` (default 300s), then repeat.

### New Directories

| Directory | Purpose |
|-----------|---------|
| `In_Progress/` | Tasks currently being executed — moved here from Needs_Action/ before processing |
| `Reports/` | Weekly CEO briefings and business audit reports |
| `Approved/` | Archive of executed approval files |

### Skill: Gold Autonomous Loop

**Trigger**: `./run_gold.sh` or `python gold_loop.py`

**CLI**:
- `python gold_loop.py` — continuous mode (default, 5-min cycles)
- `python gold_loop.py --once` — single cycle then exit
- `python gold_loop.py --dry-run` — analyze only

**Signal handling**: SIGINT/SIGTERM triggers graceful shutdown after current cycle.

### Skill: CEO Weekly Report

**Trigger**: Scheduled (configurable) or `python ceo_report_generator.py`

**Output**: `Reports/CEO_REPORT_WEEK_YYYY-MM-DD.md`

**Sections**: Executive Summary, Task Performance, Communication Activity, Financial Overview (if Odoo), Social Media, Issues & Alerts, Recommendations.

### Skill: Business Audit

**Trigger**: Scheduled (configurable) or `python business_audit.py`

**Output**: `Reports/AUDIT_WEEK_YYYY-MM-DD.md`

**Sections**: Efficiency Scores (A-D), Task Throughput, Approval Pipeline, Error Analysis, Watcher Health, Optimization Suggestions.

### Retry Engine (`error_handler.py`)

- Exponential backoff: `delay = min(base_delay * backoff_factor^attempt, max_delay)`
- State persisted in `.gold_retry_state.json` across cycles
- Default: 3 attempts, 5s base delay, 300s max delay
- Max-retries-exceeded tasks marked `status: blocked` with dashboard alert

### Action Logger (`action_logger.py`)

- All Gold Tier actions logged to `Logs/actions.jsonl` (structured JSON lines)
- Significant actions also get `Logs/ACTION_*.md` human-readable files
- Supports querying by time range and aggregation for reports

### Odoo Integration

**Client**: `odoo_client.py` — JSON-RPC client for Odoo ERP (stdlib only)
**MCP Server**: `mcp_odoo_server.py` — exposes `odoo_get_invoices`, `odoo_get_payments`, `odoo_get_contacts`, `odoo_create_invoice`, `odoo_financial_summary`

Write operations (invoice creation) require human approval.

### Social Media Integration

**Manager**: `social_media_manager.py` — draft generation + API posting for Facebook, Instagram, Twitter/X
**MCP Server**: `mcp_social_server.py` — exposes `social_generate_draft`, `social_post`, `social_list_drafts`

All posts require human approval. API posting is optional — works in draft-only mode without credentials.

### Gold Scheduling

- **Entry point**: `./run_gold.sh` — continuous loop (default) or single-cycle modes
- **CEO Report**: Configurable via `gold.report_day` / `gold.report_hour_utc` in config.json
- **Business Audit**: Configurable via `gold.audit_day` / `gold.audit_hour_utc` in config.json
- **WSL/Windows**: Use Task Scheduler pointing to `wsl bash run_gold.sh`
