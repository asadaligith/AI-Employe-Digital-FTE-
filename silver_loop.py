#!/usr/bin/env python3
"""
silver_loop.py — Silver Tier Reasoning Loop Orchestrator

The main execution engine that implements the 7-phase Silver Tier pipeline:
  Phase 1: Initialize — load policies, validate vault structure
  Phase 2: Analyze — scan Needs_Action/, classify tasks
  Phase 3: Plan — generate Plan.md for each task
  Phase 4: Route & Execute — skill routing, approval gates, task execution
  Phase 5: Complete — archive to Done/
  Phase 6: Update Dashboard
  Phase 7: Return summary

This script orchestrates the pipeline. For tasks requiring AI reasoning,
it invokes Claude Code CLI. For structural operations (file moves, approval
checks, dashboard updates), it acts directly.

Usage:
    python silver_loop.py              # full pipeline run
    python silver_loop.py --dry-run    # analyze only, no execution
"""

import os
import sys
import re
import json
import shutil
import tempfile
import subprocess
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR = SCRIPT_DIR

INBOX_DIR = os.path.join(VAULT_DIR, "Inbox")
NEEDS_ACTION_DIR = os.path.join(VAULT_DIR, "Needs_Action")
DONE_DIR = os.path.join(VAULT_DIR, "Done")
PLANS_DIR = os.path.join(VAULT_DIR, "Plans")
PENDING_APPROVAL_DIR = os.path.join(VAULT_DIR, "Pending_Approval")
LOGS_DIR = os.path.join(VAULT_DIR, "Logs")
BACKUPS_DIR = os.path.join(VAULT_DIR, "Backups")

DASHBOARD_FILE = os.path.join(VAULT_DIR, "Dashboard.md")
HANDBOOK_FILE = os.path.join(VAULT_DIR, "Company_Handbook.md")
CONFIG_FILE = os.path.join(VAULT_DIR, "config.json")
LOG_FILE = os.path.join(VAULT_DIR, "watcher.log")

# Import approval gate
sys.path.insert(0, VAULT_DIR)
from approval_gate import (
    requires_approval, create_approval_file, check_approval,
    mark_approval_executed, list_pending_approvals
)

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_ts(dt: datetime = None) -> str:
    if dt is None:
        dt = now_utc()
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def file_ts(dt: datetime = None) -> str:
    if dt is None:
        dt = now_utc()
    return dt.strftime("%Y%m%d_%H%M%S")


def log(message: str) -> None:
    ts = iso_ts()
    line = f"{ts} : [silver] {message}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def parse_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter as a dict."""
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    fm = {}
    for line in match.group(1).split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip().strip('"').strip("'")
    return fm


def extract_section(content: str, heading: str) -> str:
    """Extract the text under a ## heading, up to the next ## heading."""
    pattern = rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""

# ---------------------------------------------------------------------------
# Phase 1: Initialize
# ---------------------------------------------------------------------------

def phase_initialize() -> bool:
    """Load policies, validate vault structure. Returns True if valid."""
    log("Phase 1: Initialize")

    # Check critical files
    if not os.path.isfile(HANDBOOK_FILE):
        log("FATAL: Company_Handbook.md not found — halting")
        dashboard_alert("HALT — Company_Handbook.md missing, cannot load policies")
        return False

    if not os.path.isfile(DASHBOARD_FILE):
        log("FATAL: Dashboard.md not found — halting")
        return False

    # Ensure directories
    for d in (INBOX_DIR, NEEDS_ACTION_DIR, DONE_DIR, BACKUPS_DIR,
              PLANS_DIR, PENDING_APPROVAL_DIR, LOGS_DIR):
        os.makedirs(d, exist_ok=True)

    log("vault structure validated — all directories present")

    # Load handbook (for policy awareness)
    try:
        with open(HANDBOOK_FILE, "r", encoding="utf-8") as fh:
            handbook = fh.read()
        log(f"Company_Handbook.md loaded ({len(handbook)} bytes)")
    except OSError as exc:
        log(f"WARNING: could not read handbook: {exc}")

    return True

# ---------------------------------------------------------------------------
# Phase 2: Analyze (implements analyze-needs-action skill)
# ---------------------------------------------------------------------------

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}

# Classification rules from the skill definition
def classify_task(fm: dict, description: str) -> str:
    """Classify task type based on frontmatter and description."""
    ftype = fm.get("type", "").lower()
    source = fm.get("source", "").lower()
    desc_lower = description.lower()

    if "email" in ftype or "email" in source or "email" in desc_lower or "inbox" in desc_lower:
        return "email"
    if any(kw in ftype for kw in ["message", "chat", "notification", "alert"]):
        return "message"
    if "file" in ftype or source == "watcher.py" or "file detect" in desc_lower:
        return "file"
    if any(kw in ftype or kw in desc_lower for kw in ["finance", "invoice", "payment", "budget"]):
        return "finance"
    if any(kw in ftype or kw in desc_lower for kw in ["linkedin", "marketing", "social", "post"]):
        return "marketing"
    return "general"


def phase_analyze() -> list:
    """Scan Needs_Action/ and return sorted, classified task list."""
    log("Phase 2: Analyze")

    try:
        entries = [e for e in os.listdir(NEEDS_ACTION_DIR)
                   if e.endswith(".md") and not e.startswith(".")]
    except OSError as exc:
        log(f"error scanning Needs_Action/: {exc}")
        return []

    if not entries:
        log("no pending tasks found — idle")
        return []

    tasks = []
    for idx, fname in enumerate(sorted(entries), 1):
        fpath = os.path.join(NEEDS_ACTION_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            log(f"WARNING: could not read {fname}")
            continue

        fm = parse_frontmatter(content)
        description = extract_section(content, "Task Description")
        summary = description[:120].replace("\n", " ").strip()

        task_type = classify_task(fm, description)
        priority = fm.get("priority", "low")
        created = fm.get("created", "")
        status = fm.get("status", "")

        tasks.append({
            "id": f"NA-{idx}",
            "filename": fname,
            "type": task_type,
            "priority": priority,
            "created": created,
            "status": status,
            "summary": summary,
            "frontmatter": fm,
            "content": content,
        })

    # Sort: high → medium → low, then by created (oldest first)
    tasks.sort(key=lambda t: (
        PRIORITY_ORDER.get(t["priority"], 2),
        t["created"]
    ))

    log(f"analyzed {len(tasks)} task(s): " +
        ", ".join(f'{t["id"]}({t["type"]},{t["priority"]})' for t in tasks))

    return tasks

# ---------------------------------------------------------------------------
# Phase 3: Plan (implements validate-task-schema + generate-plan-md skills)
# ---------------------------------------------------------------------------

REQUIRED_FM_FIELDS = ["type", "priority", "status", "created", "source"]
REQUIRED_SECTIONS = ["Task Description", "Required Outcome", "Processing Checklist"]
VALID_PRIORITIES = ["low", "medium", "high"]


def validate_task_schema(task: dict) -> list:
    """Validate task against required schema. Returns list of errors."""
    errors = []
    fm = task["frontmatter"]
    content = task["content"]

    for field in REQUIRED_FM_FIELDS:
        if field not in fm or not fm[field]:
            errors.append(f"missing frontmatter field: {field}")

    if fm.get("priority") not in VALID_PRIORITIES:
        errors.append(f"invalid priority: {fm.get('priority')}")

    if fm.get("status") != "pending":
        errors.append(f"status is '{fm.get('status')}', expected 'pending'")

    for section in REQUIRED_SECTIONS:
        section_content = extract_section(content, section)
        if not section_content:
            errors.append(f"missing or empty section: ## {section}")

    # Check for at least one unchecked item
    if "- [ ]" not in content:
        errors.append("no unchecked checklist items found")

    return errors


def generate_plan(task: dict) -> Optional[str]:
    """Generate a Plan.md file for a task. Returns plan file path or None."""
    task_id = task["id"]
    task_type = task["type"]
    summary = task["summary"]
    priority = task["priority"]

    now = now_utc()
    ts = iso_ts(now)
    fts = file_ts(now)

    # Determine complexity
    content_len = len(task["content"])
    if content_len < 500:
        complexity = "simple"
    elif content_len < 1500:
        complexity = "moderate"
    else:
        complexity = "complex"

    # Determine steps based on task type
    needs_approval = requires_approval("", task_type)

    steps = []
    if task_type == "email":
        steps = [
            ("Read and parse email content", "auto"),
            ("Extract key requests and action items", "auto"),
            ("Determine if response is needed", "auto"),
            ("Draft response or summary", "review" if needs_approval else "auto"),
        ]
    elif task_type == "marketing":
        steps = [
            ("Analyze marketing objective and audience", "auto"),
            ("Generate LinkedIn post content", "auto"),
            ("Review post for compliance and tone", "review"),
            ("Submit for publishing approval", "review"),
        ]
    elif task_type == "finance":
        steps = [
            ("Parse financial data and amounts", "auto"),
            ("Validate calculations and references", "auto"),
            ("Prepare financial action", "review"),
            ("Execute financial transaction", "review"),
        ]
    elif task_type == "file":
        steps = [
            ("Analyze file content and metadata", "auto"),
            ("Determine required processing action", "auto"),
            ("Execute processing and write result", "auto"),
        ]
    else:  # general
        steps = [
            ("Analyze task requirements", "auto"),
            ("Research and reason through objective", "auto"),
            ("Produce concrete result", "auto"),
        ]

    # Build plan content
    steps_md = "\n".join(
        f'- [ ] **Step {i+1}**: {desc} `[{gate}]`'
        for i, (desc, gate) in enumerate(steps)
    )

    review_steps = [(i+1, desc) for i, (desc, gate) in enumerate(steps) if gate == "review"]
    if review_steps:
        gates_md = "\n".join(
            f"- Step {num} requires review: {desc}"
            for num, desc in review_steps
        )
    else:
        gates_md = "- No approval gates — all steps are autonomous."

    plan_content = (
        "---\n"
        f"task_id: {task_id}\n"
        f"task_type: {task_type}\n"
        f"priority: {priority}\n"
        f"complexity: {complexity}\n"
        "status: pending\n"
        f"created: {ts}\n"
        f"source_file: {task['filename']}\n"
        "---\n"
        "\n"
        f"# Plan: Process {task_type} task — {summary[:80]}\n"
        "\n"
        "## Objective\n"
        f"{summary}\n"
        "\n"
        "## Context\n"
        f"- **Task ID**: {task_id}\n"
        f"- **Type**: {task_type}\n"
        f"- **Priority**: {priority}\n"
        f"- **Source file**: {task['filename']}\n"
        "\n"
        "## Steps\n"
        "\n"
        f"{steps_md}\n"
        "\n"
        "## Approval Gates\n"
        f"{gates_md}\n"
        "\n"
        "## Completion Criteria\n"
        "- All steps executed or approved\n"
        "- Result written to task file\n"
        "- Task moved to Done/\n"
    )

    fname = f"PLAN_{task_id}_{fts}.md"
    fpath = os.path.join(PLANS_DIR, fname)

    try:
        with open(fpath, "w", encoding="utf-8") as fh:
            fh.write(plan_content)
        log(f"plan created: {fname}")
        return f"Plans/{fname}"
    except OSError as exc:
        log(f"ERROR creating plan for {task_id}: {exc}")
        return None

# ---------------------------------------------------------------------------
# Phase 4: Route & Execute
# ---------------------------------------------------------------------------

def invoke_claude_reasoning(task: dict) -> str:
    """Invoke Claude Code CLI to reason through a task and produce a result.

    Falls back to a structured summary if CLI is not available.
    """
    description = extract_section(task["content"], "Task Description")
    outcome = extract_section(task["content"], "Required Outcome")

    prompt = (
        f"You are processing a task in an AI Employee vault.\n\n"
        f"## Task Description\n{description}\n\n"
        f"## Required Outcome\n{outcome}\n\n"
        f"Produce a concrete, actionable result that satisfies the required outcome. "
        f"Be specific and thorough. Output ONLY the result text, no preamble."
    )

    # Try to invoke Claude Code CLI
    try:
        result = subprocess.run(
            ["claude", "--print", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=VAULT_DIR,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # Fallback: structured analysis without Claude CLI
    log("Claude CLI not available — producing structured analysis")
    return (
        f"**Task Analysis** (automated — Silver Tier)\n\n"
        f"**Input**: {description[:300]}\n\n"
        f"**Objective**: {outcome[:300]}\n\n"
        f"**Status**: Task analyzed and filed. "
        f"Full AI reasoning requires Claude Code CLI (`claude --print`). "
        f"Re-run with Claude Code available for complete processing."
    )


def execute_task(task: dict, plan_path: Optional[str], dry_run: bool) -> dict:
    """Execute a single task through the Silver pipeline.

    Returns: {"status": "completed"|"pending_approval"|"failed", "details": str}
    """
    task_id = task["id"]
    task_type = task["type"]
    filename = task["filename"]

    if dry_run:
        log(f"[dry-run] would process {task_id} ({task_type})")
        return {"status": "dry_run", "details": "skipped (dry run mode)"}

    # Check if this task type needs approval
    needs_gate = task_type in ("email", "finance", "marketing")

    if needs_gate:
        # Check for existing approval
        action_map = {
            "email": "send_email",
            "finance": "financial_transaction",
            "marketing": "linkedin_post",
        }
        action_type = action_map.get(task_type, task_type)

        approval_status = check_approval(action_type, filename)

        if not approval_status.get("approved"):
            reason = approval_status.get("reason", "")

            if "no matching approval" in reason or "pending" in reason:
                # Create approval request if none exists
                if "no matching" in reason:
                    description = extract_section(task["content"], "Task Description")
                    target = task["frontmatter"].get("email_from", filename)
                    risk = "high" if task_type == "finance" else "medium"

                    create_approval_file(
                        action_type=action_type,
                        description=f"Process {task_type} task: {description[:200]}",
                        target=target,
                        risk_level=risk,
                        source_task=task_id,
                    )
                    log(f"{task_id}: approval requested for {action_type}")

                return {
                    "status": "pending_approval",
                    "details": f"awaiting human approval for {action_type}"
                }

            elif "rejected" in reason:
                log(f"{task_id}: approval was rejected")
                return {"status": "failed", "details": f"approval rejected: {reason}"}

            elif "expired" in reason:
                log(f"{task_id}: approval expired")
                return {"status": "failed", "details": f"approval expired: {reason}"}

    # Execute: invoke Claude reasoning
    log(f"executing {task_id} ({task_type})...")
    result_text = invoke_claude_reasoning(task)

    # Write result into task file
    fpath = os.path.join(NEEDS_ACTION_DIR, filename)
    try:
        with open(fpath, "r", encoding="utf-8") as fh:
            content = fh.read()
    except OSError as exc:
        return {"status": "failed", "details": f"cannot read task file: {exc}"}

    # Insert ## Result before ## Processing Checklist
    if "## Processing Checklist" in content:
        content = content.replace(
            "## Processing Checklist",
            f"## Result\n{result_text}\n\n## Processing Checklist"
        )
    else:
        content += f"\n## Result\n{result_text}\n"

    # Mark checklist items as done
    content = content.replace("- [ ]", "- [x]")

    # Add completion notes
    completion_ts = iso_ts()
    content += (
        f"\n## Completion Notes\n"
        f"- Processed by Silver Tier autonomous loop\n"
        f"- Task type: {task_type}\n"
        f"- Plan: {plan_path or 'inline'}\n"
        f"- Completed: {completion_ts}\n"
    )

    # Update status in frontmatter
    content = re.sub(
        r"^status:\s*pending\s*$",
        "status: completed",
        content,
        flags=re.MULTILINE
    )

    # Write back
    try:
        with open(fpath, "w", encoding="utf-8") as fh:
            fh.write(content)
    except OSError as exc:
        return {"status": "failed", "details": f"cannot write task file: {exc}"}

    # Mark approval as executed if applicable
    if needs_gate:
        approval_status = check_approval(
            action_map.get(task_type, task_type), filename
        )
        if approval_status.get("approved"):
            mark_approval_executed(approval_status.get("file", ""))

    # Update plan status
    if plan_path:
        plan_fpath = os.path.join(VAULT_DIR, plan_path)
        if os.path.isfile(plan_fpath):
            try:
                with open(plan_fpath, "r", encoding="utf-8") as fh:
                    plan_content = fh.read()
                plan_content = re.sub(
                    r"^status:\s*pending\s*$",
                    "status: completed",
                    plan_content,
                    flags=re.MULTILINE
                )
                plan_content = plan_content.replace("- [ ]", "- [x]")
                with open(plan_fpath, "w", encoding="utf-8") as fh:
                    fh.write(plan_content)
            except OSError:
                pass

    return {"status": "completed", "details": f"result written ({len(result_text)} chars)"}

# ---------------------------------------------------------------------------
# Phase 5: Complete (move to Done/)
# ---------------------------------------------------------------------------

def move_to_done(filename: str) -> bool:
    """Move a completed task from Needs_Action/ to Done/."""
    src = os.path.join(NEEDS_ACTION_DIR, filename)
    dst = os.path.join(DONE_DIR, filename)

    # Handle collision
    if os.path.exists(dst):
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(dst):
            dst = os.path.join(DONE_DIR, f"{base}_{counter}{ext}")
            counter += 1

    try:
        shutil.move(src, dst)
        log(f"moved {filename} → Done/")
        return True
    except OSError as exc:
        log(f"ERROR moving {filename} to Done: {exc}")
        return False

# ---------------------------------------------------------------------------
# Phase 6: Update Dashboard
# ---------------------------------------------------------------------------

def update_dashboard(summary: dict) -> None:
    """Update Dashboard.md with current state."""
    log("Phase 6: Update Dashboard")

    if not os.path.isfile(DASHBOARD_FILE):
        return

    try:
        with open(DASHBOARD_FILE, "r", encoding="utf-8") as fh:
            content = fh.read()
    except OSError:
        return

    # Count pending tasks
    try:
        pending = len([e for e in os.listdir(NEEDS_ACTION_DIR)
                       if e.endswith(".md") and not e.startswith(".")])
    except OSError:
        pending = 0

    # Count completed today
    today_str = now_utc().strftime("%Y-%m-%d")
    try:
        done_files = [e for e in os.listdir(DONE_DIR) if e.endswith(".md")]
        completed_today = 0
        for f in done_files:
            fpath = os.path.join(DONE_DIR, f)
            try:
                with open(fpath, "r", encoding="utf-8") as fh:
                    fc = fh.read()
                if today_str in fc:
                    completed_today += 1
            except OSError:
                pass
    except OSError:
        completed_today = 0

    # Count pending approvals
    try:
        pending_approvals = len([e for e in os.listdir(PENDING_APPROVAL_DIR)
                                 if e.startswith("APPROVAL_") and e.endswith(".md")])
    except OSError:
        pending_approvals = 0

    ts = iso_ts()

    # Update system status
    new_status = (
        "## System Status\n"
        f"- Pending Tasks: {pending}\n"
        f"- Completed Today: {completed_today}\n"
        f"- Pending Approvals: {pending_approvals}\n"
        f"- Last Execution: {ts}\n"
    )

    # Replace system status section
    content = re.sub(
        r"## System Status\n(?:- .*\n)*",
        new_status,
        content
    )

    # Add activity entry
    processed = summary.get("processed_tasks", 0)
    pending_a = summary.get("pending_approval", 0)
    failed = summary.get("failed_tasks", 0)

    activity = (
        f"- {ts} : Silver Tier run complete — "
        f"{processed} processed, {pending_a} pending approval, {failed} failed. "
        f"Skill: process-all-pending-tasks.\n"
    )

    content = content.replace(
        "## Recent Activity\n",
        f"## Recent Activity\n{activity}",
        1
    )

    # Clear stale alerts if no failures
    if failed == 0 and "## Alerts" in content:
        content = re.sub(
            r"## Alerts\n(?:- .*\n)*",
            "## Alerts\n- None\n",
            content
        )

    try:
        with open(DASHBOARD_FILE, "w", encoding="utf-8") as fh:
            fh.write(content)
        log("Dashboard.md updated")
    except OSError as exc:
        log(f"ERROR updating Dashboard: {exc}")


def dashboard_alert(message: str) -> None:
    """Add an alert to Dashboard.md."""
    if not os.path.isfile(DASHBOARD_FILE):
        return
    ts = iso_ts()
    entry = f"- {ts} : {message}\n"
    try:
        with open(DASHBOARD_FILE, "r", encoding="utf-8") as fh:
            content = fh.read()
        # Replace "None" alert or append
        if "- None\n" in content:
            content = content.replace("- None\n", entry, 1)
        else:
            content = content.replace("## Alerts\n", f"## Alerts\n{entry}", 1)
        with open(DASHBOARD_FILE, "w", encoding="utf-8") as fh:
            fh.write(content)
    except OSError:
        pass

# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(dry_run: bool = False) -> dict:
    """Execute the full Silver Tier pipeline. Returns summary dict."""
    print("")
    print("========================================")
    print("  Silver Tier — Reasoning Loop")
    print("  Autonomous Processing Pipeline")
    print("========================================")
    print("")

    summary = {
        "processed_tasks": 0,
        "approved_tasks": 0,
        "pending_approval": 0,
        "failed_tasks": 0,
        "status": "complete",
    }

    # Phase 1
    if not phase_initialize():
        summary["status"] = "halted"
        return summary

    # Phase 2
    tasks = phase_analyze()
    if not tasks:
        log("no tasks to process — updating dashboard and exiting")
        update_dashboard(summary)
        return summary

    # Phase 3: Plan
    log(f"Phase 3: Plan ({len(tasks)} task(s))")
    task_plans = {}
    valid_tasks = []

    for task in tasks:
        # Validate schema
        errors = validate_task_schema(task)
        if errors:
            log(f"SCHEMA FAILURE — {task['filename']}: {', '.join(errors)}")
            dashboard_alert(
                f"SCHEMA FAILURE — `{task['filename']}` is missing: {', '.join(errors)}"
            )
            summary["failed_tasks"] += 1
            continue

        # Generate plan
        plan_path = generate_plan(task)
        task_plans[task["id"]] = plan_path
        valid_tasks.append(task)

    # Phase 4: Route & Execute
    log(f"Phase 4: Route & Execute ({len(valid_tasks)} valid task(s))")
    completed_tasks = []

    for task in valid_tasks:
        plan_path = task_plans.get(task["id"])
        result = execute_task(task, plan_path, dry_run)

        status = result["status"]
        log(f"{task['id']}: {status} — {result['details']}")

        if status == "completed":
            summary["processed_tasks"] += 1
            completed_tasks.append(task)
        elif status == "pending_approval":
            summary["pending_approval"] += 1
        elif status == "failed":
            summary["failed_tasks"] += 1
            dashboard_alert(f"TASK FAILED — {task['filename']}: {result['details']}")

    # Phase 5: Complete
    log(f"Phase 5: Complete ({len(completed_tasks)} task(s))")
    for task in completed_tasks:
        move_to_done(task["filename"])

    # Phase 6: Update Dashboard
    update_dashboard(summary)

    # Phase 7: Return
    log(f"Phase 7: Pipeline complete — {json.dumps(summary)}")

    print("")
    print("========================================")
    print(f"  Processed:        {summary['processed_tasks']}")
    print(f"  Pending Approval: {summary['pending_approval']}")
    print(f"  Failed:           {summary['failed_tasks']}")
    print(f"  Status:           {summary['status']}")
    print("========================================")
    print("")

    return summary


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("  [DRY RUN MODE — no tasks will be executed]\n")
    run_pipeline(dry_run=dry_run)


if __name__ == "__main__":
    main()
