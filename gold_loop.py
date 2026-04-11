#!/usr/bin/env python3
"""
gold_loop.py — Gold Tier Continuous Autonomous Loop Orchestrator

The core Gold Tier execution engine. Wraps silver_loop.py functions, adds:
  - Continuous operation (sleep between cycles)
  - In_Progress/ tracking (tasks move through Needs_Action → In_Progress → Done)
  - Retry with exponential backoff
  - Post-execution verification
  - Scheduled CEO report and business audit generation
  - Graceful shutdown via SIGINT/SIGTERM

10-Phase Pipeline:
  1. Initialize — load policies, ensure Gold dirs
  2. Run Watchers — subprocess watcher_manager.py --once
  3. Analyze — scan Needs_Action/
  4. Plan — validate schemas, generate plans
  5. Track — move tasks to In_Progress/
  6. Execute — run with retry wrapper
  7. Verify — post-execution checks
  8. Report Check — generate CEO report / audit if due
  9. Update Dashboard — enhanced Gold metrics
  10. Sleep or Exit — continuous or single cycle

Usage:
    python gold_loop.py              # continuous mode (default)
    python gold_loop.py --once       # single cycle then exit
    python gold_loop.py --dry-run    # analyze only, no execution
"""

import os
import sys
import re
import json
import shutil
import signal
import subprocess
import time
import threading
from datetime import datetime, timezone, timedelta

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR = SCRIPT_DIR

IN_PROGRESS_DIR = os.path.join(VAULT_DIR, "In_Progress")
REPORTS_DIR = os.path.join(VAULT_DIR, "Reports")
APPROVED_DIR = os.path.join(VAULT_DIR, "Approved")
NEEDS_ACTION_DIR = os.path.join(VAULT_DIR, "Needs_Action")
DONE_DIR = os.path.join(VAULT_DIR, "Done")
LOGS_DIR = os.path.join(VAULT_DIR, "Logs")
CONFIG_FILE = os.path.join(VAULT_DIR, "config.json")
LOG_FILE = os.path.join(VAULT_DIR, "watcher.log")
DASHBOARD_FILE = os.path.join(VAULT_DIR, "Dashboard.md")

# ---------------------------------------------------------------------------
# Imports from Silver Tier (reuse, don't rewrite)
# ---------------------------------------------------------------------------
sys.path.insert(0, VAULT_DIR)

from silver_loop import (
    phase_initialize,
    phase_analyze,
    validate_task_schema,
    generate_plan,
    execute_task,
    move_to_done,
    update_dashboard,
    dashboard_alert,
    log as silver_log,
    iso_ts,
    now_utc,
    file_ts,
    extract_section,
    parse_frontmatter,
)

from error_handler import (
    RetryPolicy,
    with_retry,
    should_retry,
    update_retry_state,
    clear_retry_state,
    get_retry_state,
    cleanup_old_states,
)

from action_logger import log_action, get_action_summary

# ---------------------------------------------------------------------------
# Shutdown handling
# ---------------------------------------------------------------------------
shutdown_event = threading.Event()


def _signal_handler(signum, frame):
    """Graceful shutdown — finish current cycle then exit."""
    log("received shutdown signal — will exit after current cycle")
    shutdown_event.set()


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(message: str) -> None:
    ts = iso_ts()
    line = f"{ts} : [gold] {message}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_gold_config() -> dict:
    """Load gold-specific config from config.json."""
    defaults = {
        "enabled": True,
        "cycle_interval_seconds": 300,
        "max_retry_attempts": 3,
        "retry_base_delay_seconds": 5,
        "report_day": "monday",
        "report_hour_utc": 7,
        "audit_day": "friday",
        "audit_hour_utc": 18,
    }
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
            config = json.load(fh)
        gold_cfg = config.get("gold", {})
        for k, v in defaults.items():
            if k not in gold_cfg:
                gold_cfg[k] = v
        return gold_cfg
    except (OSError, json.JSONDecodeError):
        return defaults


# ---------------------------------------------------------------------------
# Phase 1: Initialize (extends Silver)
# ---------------------------------------------------------------------------

def gold_phase_initialize() -> bool:
    """Initialize vault — Silver init + Gold directories."""
    log("Phase 1: Initialize (Gold)")

    if not phase_initialize():
        return False

    # Ensure Gold-specific directories
    for d in (IN_PROGRESS_DIR, REPORTS_DIR, APPROVED_DIR):
        os.makedirs(d, exist_ok=True)

    log("Gold directories verified: In_Progress/, Reports/, Approved/")
    return True


# ---------------------------------------------------------------------------
# Phase 2: Run Watchers
# ---------------------------------------------------------------------------

def gold_phase_watchers() -> None:
    """Run watcher_manager.py --once as a subprocess for perception scan."""
    log("Phase 2: Run Watchers")
    watcher_script = os.path.join(VAULT_DIR, "watcher_manager.py")

    if not os.path.isfile(watcher_script):
        log("WARNING: watcher_manager.py not found — skipping watcher scan")
        return

    try:
        result = subprocess.run(
            [sys.executable, watcher_script, "--once"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=VAULT_DIR,
        )
        if result.returncode == 0:
            log("watcher scan complete")
        else:
            log(f"watcher scan returned code {result.returncode}")
            if result.stderr:
                log(f"watcher stderr: {result.stderr[:300]}")
    except subprocess.TimeoutExpired:
        log("WARNING: watcher scan timed out (120s)")
    except OSError as exc:
        log(f"WARNING: could not run watchers: {exc}")


# ---------------------------------------------------------------------------
# Phase 5: Track — move to In_Progress/
# ---------------------------------------------------------------------------

def move_to_in_progress(filename: str) -> bool:
    """Move a task from Needs_Action/ to In_Progress/ before execution."""
    src = os.path.join(NEEDS_ACTION_DIR, filename)
    dst = os.path.join(IN_PROGRESS_DIR, filename)

    if not os.path.isfile(src):
        log(f"WARNING: {filename} not found in Needs_Action/")
        return False

    # Handle collision
    if os.path.exists(dst):
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(dst):
            dst = os.path.join(IN_PROGRESS_DIR, f"{base}_{counter}{ext}")
            counter += 1

    try:
        shutil.move(src, dst)
        log(f"tracked: {filename} → In_Progress/")
        return True
    except OSError as exc:
        log(f"ERROR moving {filename} to In_Progress: {exc}")
        return False


def move_back_to_needs_action(filename: str) -> bool:
    """Move a failed task from In_Progress/ back to Needs_Action/."""
    src = os.path.join(IN_PROGRESS_DIR, filename)
    dst = os.path.join(NEEDS_ACTION_DIR, filename)

    if not os.path.isfile(src):
        return False

    try:
        shutil.move(src, dst)
        log(f"returned: {filename} → Needs_Action/ (retry later)")
        return True
    except OSError as exc:
        log(f"ERROR moving {filename} back to Needs_Action: {exc}")
        return False


def move_in_progress_to_done(filename: str) -> bool:
    """Move a completed task from In_Progress/ to Done/."""
    src = os.path.join(IN_PROGRESS_DIR, filename)
    dst = os.path.join(DONE_DIR, filename)

    if not os.path.isfile(src):
        return False

    # Handle collision
    if os.path.exists(dst):
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(dst):
            dst = os.path.join(DONE_DIR, f"{base}_{counter}{ext}")
            counter += 1

    try:
        shutil.move(src, dst)
        log(f"completed: {filename} → Done/")
        return True
    except OSError as exc:
        log(f"ERROR moving {filename} to Done: {exc}")
        return False


# ---------------------------------------------------------------------------
# Phase 6: Execute with retry
# ---------------------------------------------------------------------------

def execute_task_in_progress(task: dict, plan_path, dry_run: bool,
                             policy: RetryPolicy) -> dict:
    """Execute a single task that's been moved to In_Progress/.

    Temporarily patches silver_loop.NEEDS_ACTION_DIR so execute_task() reads
    from In_Progress/ instead.

    Returns: {"status": str, "details": str}
    """
    import silver_loop

    filename = task["filename"]

    if dry_run:
        log(f"[dry-run] would process {task['id']} ({task['type']})")
        return {"status": "dry_run", "details": "skipped (dry run mode)"}

    # Check retry eligibility
    retry_check = should_retry(filename, policy)
    if not retry_check["retry"]:
        reason = retry_check["reason"]
        log(f"{task['id']}: skipped — {reason}")
        return {"status": "skipped", "details": reason}

    attempt_num = retry_check["attempts_so_far"] + 1
    start_time = time.time()

    # Temporarily patch silver_loop to read from In_Progress/
    original_na_dir = silver_loop.NEEDS_ACTION_DIR
    silver_loop.NEEDS_ACTION_DIR = IN_PROGRESS_DIR

    try:
        result = execute_task(task, plan_path, dry_run)
    except Exception as exc:
        result = {"status": "failed", "details": str(exc)}
    finally:
        # Always restore
        silver_loop.NEEDS_ACTION_DIR = original_na_dir

    elapsed_ms = int((time.time() - start_time) * 1000)

    if result["status"] == "completed":
        clear_retry_state(filename)
        log_action("execute_task", filename, "success",
                   duration_ms=elapsed_ms,
                   metadata={"task_type": task["type"], "attempt": attempt_num})
    elif result["status"] == "pending_approval":
        # Not a failure — just waiting. Don't count as retry.
        pass
    else:
        # Failed — record retry state
        update_retry_state(filename, attempt_num, result["details"], policy)
        log_action("execute_task", filename, "failure",
                   error=result["details"], duration_ms=elapsed_ms,
                   metadata={"task_type": task["type"], "attempt": attempt_num})

    return result


# ---------------------------------------------------------------------------
# Phase 7: Verify
# ---------------------------------------------------------------------------

def verify_task_completion(filename: str) -> bool:
    """Post-execution verification: check the task was properly completed."""
    # Check if file made it to Done/
    done_path = os.path.join(DONE_DIR, filename)
    if not os.path.isfile(done_path):
        # Check without collision suffix
        base, ext = os.path.splitext(filename)
        found = False
        try:
            for entry in os.listdir(DONE_DIR):
                if entry.startswith(base) and entry.endswith(ext):
                    done_path = os.path.join(DONE_DIR, entry)
                    found = True
                    break
        except OSError:
            pass
        if not found:
            return False

    try:
        with open(done_path, "r", encoding="utf-8") as fh:
            content = fh.read()
    except OSError:
        return False

    # Verify result section exists
    if "## Result" not in content:
        log(f"VERIFY FAIL: {filename} missing ## Result section")
        return False

    # Verify status is completed
    fm = parse_frontmatter(content)
    if fm.get("status") != "completed":
        log(f"VERIFY FAIL: {filename} status is '{fm.get('status')}', expected 'completed'")
        return False

    return True


# ---------------------------------------------------------------------------
# Phase 8: Report Check
# ---------------------------------------------------------------------------

def is_report_due(gold_cfg: dict, report_type: str) -> bool:
    """Check if a weekly report/audit is due based on config."""
    now = now_utc()
    day_name = now.strftime("%A").lower()

    if report_type == "ceo_report":
        target_day = gold_cfg.get("report_day", "monday").lower()
        target_hour = gold_cfg.get("report_hour_utc", 7)
    elif report_type == "audit":
        target_day = gold_cfg.get("audit_day", "friday").lower()
        target_hour = gold_cfg.get("audit_hour_utc", 18)
    else:
        return False

    if day_name != target_day:
        return False

    if now.hour != target_hour:
        return False

    # Check if already generated today
    today_str = now.strftime("%Y-%m-%d")
    try:
        for entry in os.listdir(REPORTS_DIR):
            if today_str in entry:
                if report_type == "ceo_report" and entry.startswith("CEO_REPORT"):
                    return False
                if report_type == "audit" and entry.startswith("AUDIT"):
                    return False
    except OSError:
        pass

    return True


def run_report_check(gold_cfg: dict) -> None:
    """Generate CEO report or audit if scheduled."""
    log("Phase 8: Report Check")

    if is_report_due(gold_cfg, "ceo_report"):
        log("CEO weekly report is due — generating")
        try:
            from ceo_report_generator import generate_weekly_report
            result = generate_weekly_report()
            if result.get("report_path"):
                log(f"CEO report generated: {result['report_path']}")
                log_action("generate_report", "CEO weekly report", "success",
                           metadata={"path": result["report_path"]})
            else:
                log(f"CEO report generation failed: {result.get('error', 'unknown')}")
                log_action("generate_report", "CEO weekly report", "failure",
                           error=result.get("error", "unknown"))
        except ImportError:
            log("WARNING: ceo_report_generator not available")
        except Exception as exc:
            log(f"ERROR generating CEO report: {exc}")
            log_action("generate_report", "CEO weekly report", "failure",
                       error=str(exc))

    if is_report_due(gold_cfg, "audit"):
        log("Business audit is due — generating")
        try:
            from business_audit import run_audit
            result = run_audit()
            if result.get("audit_path"):
                log(f"Audit generated: {result['audit_path']}")
                log_action("run_audit", "weekly business audit", "success",
                           metadata={"path": result["audit_path"]})
            else:
                log(f"Audit generation failed: {result.get('error', 'unknown')}")
                log_action("run_audit", "weekly business audit", "failure",
                           error=result.get("error", "unknown"))
        except ImportError:
            log("WARNING: business_audit module not available")
        except Exception as exc:
            log(f"ERROR running audit: {exc}")
            log_action("run_audit", "weekly business audit", "failure",
                       error=str(exc))


# ---------------------------------------------------------------------------
# Phase 9: Enhanced Dashboard Update
# ---------------------------------------------------------------------------

def gold_update_dashboard(summary: dict) -> None:
    """Enhanced dashboard update with Gold Tier metrics."""
    # Call Silver dashboard update first
    update_dashboard(summary)

    # Append Gold-specific metrics
    if not os.path.isfile(DASHBOARD_FILE):
        return

    try:
        with open(DASHBOARD_FILE, "r", encoding="utf-8") as fh:
            content = fh.read()
    except OSError:
        return

    # Count in-progress tasks
    try:
        in_progress = len([e for e in os.listdir(IN_PROGRESS_DIR)
                           if e.endswith(".md") and not e.startswith(".")])
    except OSError:
        in_progress = 0

    # Count reports
    try:
        reports = len([e for e in os.listdir(REPORTS_DIR)
                       if e.endswith(".md")])
    except OSError:
        reports = 0

    ts = iso_ts()

    # Add Gold metrics to activity if not already there
    retried = summary.get("retried_tasks", 0)
    verified = summary.get("verified_tasks", 0)
    gold_note = (
        f"- {ts} : Gold Tier metrics — "
        f"{in_progress} in-progress, {retried} retried, "
        f"{verified} verified, {reports} reports total.\n"
    )

    content = content.replace(
        "## Recent Activity\n",
        f"## Recent Activity\n{gold_note}",
        1,
    )

    try:
        with open(DASHBOARD_FILE, "w", encoding="utf-8") as fh:
            fh.write(content)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Main Cycle
# ---------------------------------------------------------------------------

def run_gold_cycle(dry_run: bool = False, gold_cfg: dict = None) -> dict:
    """Execute a single Gold Tier cycle (10 phases).

    Returns summary dict.
    """
    if gold_cfg is None:
        gold_cfg = load_gold_config()

    cycle_start = time.time()
    log_action("cycle_start", "gold_loop", "success")

    summary = {
        "processed_tasks": 0,
        "pending_approval": 0,
        "failed_tasks": 0,
        "retried_tasks": 0,
        "verified_tasks": 0,
        "skipped_dry_run": 0,
        "status": "complete",
    }

    retry_policy = RetryPolicy(
        max_attempts=gold_cfg.get("max_retry_attempts", 3),
        base_delay=gold_cfg.get("retry_base_delay_seconds", 5),
    )

    # Phase 1: Initialize
    if not gold_phase_initialize():
        summary["status"] = "halted"
        log_action("cycle_end", "gold_loop", "failure", error="initialization failed")
        return summary

    # Phase 2: Run Watchers
    if not dry_run:
        gold_phase_watchers()

    # Phase 3: Analyze
    log("Phase 3: Analyze")
    tasks = phase_analyze()

    if not tasks:
        log("no tasks to process — idle cycle")
        summary["status"] = "idle"
        run_report_check(gold_cfg)
        gold_update_dashboard(summary)
        elapsed = int((time.time() - cycle_start) * 1000)
        log_action("cycle_end", "gold_loop", "success",
                   duration_ms=elapsed, metadata={"status": "idle"})
        return summary

    # Phase 4: Plan
    log(f"Phase 4: Plan ({len(tasks)} task(s))")
    task_plans = {}
    valid_tasks = []

    for task in tasks:
        errors = validate_task_schema(task)
        if errors:
            log(f"SCHEMA FAILURE — {task['filename']}: {', '.join(errors)}")
            dashboard_alert(
                f"SCHEMA FAILURE — `{task['filename']}` is missing: {', '.join(errors)}"
            )
            summary["failed_tasks"] += 1
            log_action("validate_schema", task["filename"], "failure",
                       error=", ".join(errors))
            continue

        plan_path = generate_plan(task)
        task_plans[task["id"]] = plan_path
        valid_tasks.append(task)

    # Phase 5: Track — move to In_Progress/
    log(f"Phase 5: Track ({len(valid_tasks)} task(s))")
    tracked_tasks = []

    for task in valid_tasks:
        filename = task["filename"]

        # Check retry eligibility before tracking
        retry_check = should_retry(filename, retry_policy)
        if not retry_check["retry"]:
            reason = retry_check["reason"]
            if "max attempts" in reason:
                # Max retries exceeded — mark as blocked
                log(f"{task['id']}: max retries exceeded — marking blocked")
                dashboard_alert(
                    f"BLOCKED — `{filename}` failed after {retry_policy.max_attempts} "
                    f"attempts. Manual intervention required."
                )
                _mark_task_blocked(filename)
                summary["failed_tasks"] += 1
            else:
                log(f"{task['id']}: skipped — {reason}")
            continue

        if retry_check["attempts_so_far"] > 0:
            summary["retried_tasks"] += 1

        if move_to_in_progress(filename):
            tracked_tasks.append(task)

    # Phase 6: Execute
    log(f"Phase 6: Execute ({len(tracked_tasks)} task(s))")
    completed_tasks = []
    approval_tasks = []

    for task in tracked_tasks:
        if shutdown_event.is_set():
            log("shutdown requested — moving remaining In_Progress tasks back")
            move_back_to_needs_action(task["filename"])
            continue

        plan_path = task_plans.get(task["id"])
        result = execute_task_in_progress(task, plan_path, dry_run, retry_policy)

        status = result["status"]
        log(f"{task['id']}: {status} — {result['details']}")

        if status == "completed":
            summary["processed_tasks"] += 1
            completed_tasks.append(task)
        elif status == "pending_approval":
            summary["pending_approval"] += 1
            approval_tasks.append(task)
            # Move back — will be picked up after approval
            move_back_to_needs_action(task["filename"])
        elif status == "dry_run":
            summary["skipped_dry_run"] += 1
            move_back_to_needs_action(task["filename"])
        elif status == "skipped":
            move_back_to_needs_action(task["filename"])
        else:
            # Failed — move back for retry
            summary["failed_tasks"] += 1
            dashboard_alert(f"TASK FAILED — {task['filename']}: {result['details']}")
            move_back_to_needs_action(task["filename"])

    # Phase 7: Verify & move completed to Done/
    log(f"Phase 7: Verify ({len(completed_tasks)} task(s))")
    for task in completed_tasks:
        filename = task["filename"]
        # Move from In_Progress to Done
        if move_in_progress_to_done(filename):
            if verify_task_completion(filename):
                summary["verified_tasks"] += 1
                log(f"verified: {filename}")
            else:
                log(f"VERIFY WARNING: {filename} — verification checks incomplete")

    # Phase 8: Report Check
    run_report_check(gold_cfg)

    # Phase 9: Update Dashboard
    log("Phase 9: Update Dashboard")
    gold_update_dashboard(summary)

    # Cleanup old retry states
    removed = cleanup_old_states()
    if removed:
        log(f"cleaned up {removed} old retry state(s)")

    elapsed = int((time.time() - cycle_start) * 1000)
    log_action("cycle_end", "gold_loop", "success",
               duration_ms=elapsed,
               metadata={
                   "processed": summary["processed_tasks"],
                   "failed": summary["failed_tasks"],
                   "retried": summary["retried_tasks"],
               })

    return summary


def _mark_task_blocked(filename: str) -> None:
    """Mark a task as blocked in its frontmatter."""
    fpath = os.path.join(NEEDS_ACTION_DIR, filename)
    if not os.path.isfile(fpath):
        return

    try:
        with open(fpath, "r", encoding="utf-8") as fh:
            content = fh.read()

        content = re.sub(
            r"^status:\s*pending\s*$",
            "status: blocked",
            content,
            flags=re.MULTILINE,
        )

        with open(fpath, "w", encoding="utf-8") as fh:
            fh.write(content)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Continuous Loop
# ---------------------------------------------------------------------------

def run_continuous(dry_run: bool = False) -> None:
    """Run the Gold Tier loop continuously until shutdown signal."""
    gold_cfg = load_gold_config()
    interval = gold_cfg.get("cycle_interval_seconds", 300)
    cycle_num = 0

    print("")
    print("=" * 50)
    print("  Gold Tier — Continuous Autonomous Loop")
    print(f"  Cycle interval: {interval}s")
    print("  Press Ctrl+C for graceful shutdown")
    print("=" * 50)
    print("")

    while not shutdown_event.is_set():
        cycle_num += 1
        log(f"=== Gold Cycle #{cycle_num} ===")

        summary = run_gold_cycle(dry_run=dry_run, gold_cfg=gold_cfg)

        print(f"\n  Cycle #{cycle_num} Summary:")
        print(f"    Processed:        {summary['processed_tasks']}")
        print(f"    Pending Approval: {summary['pending_approval']}")
        print(f"    Failed:           {summary['failed_tasks']}")
        print(f"    Retried:          {summary['retried_tasks']}")
        print(f"    Verified:         {summary['verified_tasks']}")
        print(f"    Status:           {summary['status']}")
        print("")

        if shutdown_event.is_set():
            break

        log(f"sleeping {interval}s until next cycle...")
        # Sleep in small increments to check shutdown
        for _ in range(interval):
            if shutdown_event.is_set():
                break
            time.sleep(1)

    log("Gold Tier loop shutdown complete")


def run_once(dry_run: bool = False) -> dict:
    """Run a single Gold Tier cycle and exit."""
    print("")
    print("=" * 50)
    print("  Gold Tier — Single Cycle")
    print("=" * 50)
    print("")

    summary = run_gold_cycle(dry_run=dry_run)

    print("")
    print("=" * 50)
    print(f"  Processed:        {summary['processed_tasks']}")
    print(f"  Pending Approval: {summary['pending_approval']}")
    print(f"  Failed:           {summary['failed_tasks']}")
    print(f"  Retried:          {summary['retried_tasks']}")
    print(f"  Verified:         {summary['verified_tasks']}")
    if summary.get("skipped_dry_run"):
        print(f"  Skipped (dry-run):{summary['skipped_dry_run']}")
    print(f"  Status:           {summary['status']}")
    print("=" * 50)
    print("")

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    once = "--once" in sys.argv
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("  [DRY RUN MODE — no tasks will be executed]\n")

    if once or dry_run:
        run_once(dry_run=dry_run)
    else:
        run_continuous(dry_run=dry_run)


if __name__ == "__main__":
    main()
