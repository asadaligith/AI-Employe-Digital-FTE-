#!/usr/bin/env python3
"""
business_audit.py — Gold Tier Weekly Efficiency Audit

Analyzes system activity, identifies inefficiencies, and suggests optimizations.
Output: Reports/AUDIT_WEEK_YYYY-MM-DD.md

Usage:
    python business_audit.py                  # current week
    python business_audit.py --since 2026-04-01  # custom start date
"""

import os
import sys
import re
import json
import subprocess
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR = SCRIPT_DIR

DONE_DIR = os.path.join(VAULT_DIR, "Done")
NEEDS_ACTION_DIR = os.path.join(VAULT_DIR, "Needs_Action")
LOGS_DIR = os.path.join(VAULT_DIR, "Logs")
REPORTS_DIR = os.path.join(VAULT_DIR, "Reports")
PENDING_APPROVAL_DIR = os.path.join(VAULT_DIR, "Pending_Approval")
CONFIG_FILE = os.path.join(VAULT_DIR, "config.json")
LOG_FILE = os.path.join(VAULT_DIR, "watcher.log")

sys.path.insert(0, VAULT_DIR)

try:
    from action_logger import get_actions_since, get_action_summary
except ImportError:
    def get_actions_since(dt):
        return []
    def get_action_summary(dt):
        return {"total": 0, "by_action": {}, "successes": 0, "failures": 0, "errors": []}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_ts(dt: datetime = None) -> str:
    if dt is None:
        dt = now_utc()
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_frontmatter(content: str) -> dict:
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    fm = {}
    for line in match.group(1).split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip().strip('"').strip("'")
    return fm


# ---------------------------------------------------------------------------
# Analysis Functions
# ---------------------------------------------------------------------------

def analyze_task_throughput(since: datetime) -> dict:
    """Analyze task processing speed and bottlenecks."""
    analysis = {
        "total_completed": 0,
        "avg_processing_time_hours": 0,
        "fastest_type": "",
        "slowest_type": "",
        "bottleneck_type": "",
        "type_counts": {},
        "processing_times": [],
    }

    since_str = since.strftime("%Y-%m-%d")

    try:
        entries = os.listdir(DONE_DIR)
    except OSError:
        return analysis

    type_times = {}

    for entry in entries:
        if not entry.endswith(".md"):
            continue

        fpath = os.path.join(DONE_DIR, entry)
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            continue

        fm = parse_frontmatter(content)
        created_str = fm.get("created", "")

        if not created_str or created_str < since_str:
            continue

        analysis["total_completed"] += 1
        task_type = fm.get("type", "general")
        analysis["type_counts"][task_type] = analysis["type_counts"].get(task_type, 0) + 1

        # Try to calculate processing time from created → completed timestamps
        completed_match = re.search(r"Completed:\s*(\d{4}-\d{2}-\d{2}T[\d:]+Z)", content)
        if completed_match and created_str:
            try:
                created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                completed_dt = datetime.fromisoformat(
                    completed_match.group(1).replace("Z", "+00:00")
                )
                hours = (completed_dt - created_dt).total_seconds() / 3600
                analysis["processing_times"].append(hours)

                if task_type not in type_times:
                    type_times[task_type] = []
                type_times[task_type].append(hours)
            except ValueError:
                pass

    if analysis["processing_times"]:
        analysis["avg_processing_time_hours"] = round(
            sum(analysis["processing_times"]) / len(analysis["processing_times"]), 2
        )

    if type_times:
        avg_by_type = {
            t: sum(times) / len(times) for t, times in type_times.items()
        }
        analysis["fastest_type"] = min(avg_by_type, key=avg_by_type.get)
        analysis["slowest_type"] = max(avg_by_type, key=avg_by_type.get)

    # Bottleneck: type with most pending tasks
    try:
        pending_entries = os.listdir(NEEDS_ACTION_DIR)
        pending_types = {}
        for entry in pending_entries:
            if not entry.endswith(".md"):
                continue
            fpath = os.path.join(NEEDS_ACTION_DIR, entry)
            try:
                with open(fpath, "r", encoding="utf-8") as fh:
                    content = fh.read(500)
                fm = parse_frontmatter(content)
                t = fm.get("type", "general")
                pending_types[t] = pending_types.get(t, 0) + 1
            except OSError:
                pass
        if pending_types:
            analysis["bottleneck_type"] = max(pending_types, key=pending_types.get)
    except OSError:
        pass

    return analysis


def analyze_approval_efficiency(since: datetime) -> dict:
    """Analyze approval turnaround time and expiry rate."""
    analysis = {
        "total_approvals": 0,
        "avg_approval_hours": 0,
        "expiry_rate": 0,
        "fastest_approval_hours": None,
        "slowest_approval_hours": None,
    }

    since_str = since.strftime("%Y-%m-%d")
    approval_times = []

    for directory in (PENDING_APPROVAL_DIR,
                      os.path.join(VAULT_DIR, "Approved")):
        if not os.path.isdir(directory):
            continue
        try:
            entries = os.listdir(directory)
        except OSError:
            continue

        for entry in entries:
            if not entry.startswith("APPROVAL_") or not entry.endswith(".md"):
                continue

            fpath = os.path.join(directory, entry)
            try:
                with open(fpath, "r", encoding="utf-8") as fh:
                    content = fh.read()
            except OSError:
                continue

            fm = parse_frontmatter(content)
            created = fm.get("created", "")
            if created < since_str:
                continue

            analysis["total_approvals"] += 1

            # Check for review timestamp
            reviewed_match = re.search(
                r"Reviewed.*?(\d{4}-\d{2}-\d{2}T[\d:]+Z)", content
            )
            if reviewed_match and created:
                try:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    reviewed_dt = datetime.fromisoformat(
                        reviewed_match.group(1).replace("Z", "+00:00")
                    )
                    hours = (reviewed_dt - created_dt).total_seconds() / 3600
                    approval_times.append(hours)
                except ValueError:
                    pass

    if approval_times:
        analysis["avg_approval_hours"] = round(
            sum(approval_times) / len(approval_times), 2
        )
        analysis["fastest_approval_hours"] = round(min(approval_times), 2)
        analysis["slowest_approval_hours"] = round(max(approval_times), 2)

    # Count expired
    expired = 0
    now = now_utc()
    if os.path.isdir(PENDING_APPROVAL_DIR):
        try:
            for entry in os.listdir(PENDING_APPROVAL_DIR):
                if not entry.startswith("APPROVAL_"):
                    continue
                fpath = os.path.join(PENDING_APPROVAL_DIR, entry)
                try:
                    with open(fpath, "r", encoding="utf-8") as fh:
                        content = fh.read(500)
                    fm = parse_frontmatter(content)
                    expires = fm.get("expires", "")
                    if expires:
                        expires_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                        if now > expires_dt:
                            expired += 1
                except (OSError, ValueError):
                    pass
        except OSError:
            pass

    if analysis["total_approvals"] > 0:
        analysis["expiry_rate"] = round(expired / analysis["total_approvals"] * 100, 1)

    return analysis


def analyze_error_patterns(since: datetime) -> dict:
    """Analyze recurring failures and retry effectiveness."""
    summary = get_action_summary(since)
    actions = get_actions_since(since)

    analysis = {
        "total_errors": summary.get("failures", 0),
        "error_rate": 0,
        "recurring_errors": {},
        "retry_success_rate": 0,
    }

    total = summary.get("total", 0)
    if total > 0:
        analysis["error_rate"] = round(summary.get("failures", 0) / total * 100, 1)

    # Find recurring error patterns
    error_actions = {}
    for entry in actions:
        if entry.get("result") == "failure":
            action = entry.get("action", "unknown")
            error_actions[action] = error_actions.get(action, 0) + 1

    analysis["recurring_errors"] = dict(
        sorted(error_actions.items(), key=lambda x: -x[1])[:5]
    )

    # Retry effectiveness
    retry_attempts = sum(
        1 for a in actions
        if a.get("action") == "execute_task"
        and a.get("metadata", {}).get("attempt", 1) > 1
    )
    retry_successes = sum(
        1 for a in actions
        if a.get("action") == "execute_task"
        and a.get("metadata", {}).get("attempt", 1) > 1
        and a.get("result") == "success"
    )

    if retry_attempts > 0:
        analysis["retry_success_rate"] = round(
            retry_successes / retry_attempts * 100, 1
        )

    return analysis


def analyze_watcher_health() -> dict:
    """Analyze watcher uptime and message volume from log file."""
    analysis = {
        "filesystem_events": 0,
        "gmail_events": 0,
        "whatsapp_events": 0,
        "watcher_errors": 0,
    }

    if not os.path.isfile(LOG_FILE):
        return analysis

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as fh:
            # Read last 1000 lines
            lines = fh.readlines()[-1000:]
    except OSError:
        return analysis

    for line in lines:
        line_lower = line.lower()
        if "[watcher]" in line_lower or "watcher" in line_lower:
            if "new file" in line_lower or "file_event" in line_lower:
                analysis["filesystem_events"] += 1
            elif "gmail" in line_lower or "email" in line_lower:
                analysis["gmail_events"] += 1
            elif "whatsapp" in line_lower:
                analysis["whatsapp_events"] += 1
            if "error" in line_lower or "fail" in line_lower:
                analysis["watcher_errors"] += 1

    return analysis


# ---------------------------------------------------------------------------
# Optimization Suggestions
# ---------------------------------------------------------------------------

def generate_optimization_suggestions(analysis: dict) -> str:
    """Generate optimization suggestions via Claude CLI with fallback."""
    prompt = (
        "Based on the following system efficiency audit data, provide 3-5 "
        "specific, actionable optimization suggestions. Focus on improving "
        "throughput, reducing errors, and streamlining approvals. "
        "Output plain text, no markdown headers.\n\n"
        f"Audit data:\n{json.dumps(analysis, indent=2, default=str)}"
    )

    try:
        result = subprocess.run(
            ["claude", "--print", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=VAULT_DIR,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # Template fallback
    suggestions = []

    throughput = analysis.get("throughput", {})
    errors = analysis.get("errors", {})
    approvals = analysis.get("approvals", {})

    if errors.get("error_rate", 0) > 10:
        suggestions.append(
            f"Error rate is {errors['error_rate']}%. Investigate the top recurring "
            f"errors: {list(errors.get('recurring_errors', {}).keys())[:3]}"
        )

    if approvals.get("expiry_rate", 0) > 20:
        suggestions.append(
            f"Approval expiry rate is {approvals['expiry_rate']}%. "
            f"Consider extending expiry windows or setting up notifications."
        )

    if throughput.get("bottleneck_type"):
        suggestions.append(
            f"Bottleneck detected in '{throughput['bottleneck_type']}' tasks. "
            f"Consider adding specialized handling for this type."
        )

    if not suggestions:
        suggestions.append(
            "System is operating efficiently. Continue monitoring key metrics."
        )

    return "\n".join(f"- {s}" for s in suggestions)


# ---------------------------------------------------------------------------
# Audit Report
# ---------------------------------------------------------------------------

def _score(value: float, good: float, bad: float) -> str:
    """Simple A/B/C/D scoring."""
    if good <= bad:
        if value <= good:
            return "A"
        elif value <= (good + bad) / 2:
            return "B"
        elif value <= bad:
            return "C"
        return "D"
    else:
        if value >= good:
            return "A"
        elif value >= (good + bad) / 2:
            return "B"
        elif value >= bad:
            return "C"
        return "D"


def run_audit(since: datetime = None) -> dict:
    """Run a full efficiency audit and generate the report.

    Returns:
        {"audit_path": str} on success, {"error": str} on failure.
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)

    if since is None:
        since = now_utc() - timedelta(days=7)

    end_date = now_utc()
    start_str = since.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    # Run all analyses
    throughput = analyze_task_throughput(since)
    approvals = analyze_approval_efficiency(since)
    errors = analyze_error_patterns(since)
    watchers = analyze_watcher_health()

    all_analysis = {
        "throughput": throughput,
        "approvals": approvals,
        "errors": errors,
        "watchers": watchers,
    }

    suggestions = generate_optimization_suggestions(all_analysis)

    # Calculate efficiency scores
    error_rate = errors.get("error_rate", 0)
    expiry_rate = approvals.get("expiry_rate", 0)
    total_completed = throughput.get("total_completed", 0)

    error_score = _score(error_rate, 5, 20)
    approval_score = _score(expiry_rate, 10, 30)
    throughput_score = _score(total_completed, 10, 2)

    scores = {
        "Error Rate": f"{error_score} ({error_rate}%)",
        "Approval Efficiency": f"{approval_score} ({100 - expiry_rate:.0f}% on-time)",
        "Task Throughput": f"{throughput_score} ({total_completed} completed)",
    }

    overall_scores = [error_score, approval_score, throughput_score]
    score_values = {"A": 4, "B": 3, "C": 2, "D": 1}
    avg_score = sum(score_values.get(s, 2) for s in overall_scores) / len(overall_scores)
    if avg_score >= 3.5:
        overall = "A"
    elif avg_score >= 2.5:
        overall = "B"
    elif avg_score >= 1.5:
        overall = "C"
    else:
        overall = "D"

    # Build report
    scores_md = "\n".join(f"- **{k}**: {v}" for k, v in scores.items())

    type_breakdown = "\n".join(
        f"  - {t}: {c}" for t, c in throughput.get("type_counts", {}).items()
    ) or "  - No data"

    recurring_md = "\n".join(
        f"  - {action}: {count} occurrence(s)"
        for action, count in errors.get("recurring_errors", {}).items()
    ) or "  - No recurring errors"

    report = (
        "---\n"
        "type: business_audit\n"
        f"period: {start_str} to {end_str}\n"
        f"generated: {iso_ts()}\n"
        f"overall_score: {overall}\n"
        "---\n"
        "\n"
        "# Weekly Efficiency Audit\n"
        "\n"
        f"**Period**: {start_str} to {end_str}\n"
        f"**Overall Score**: {overall}\n"
        "\n"
        "## Efficiency Scores\n"
        f"{scores_md}\n"
        "\n"
        "## Task Throughput\n"
        f"- Tasks completed: {throughput['total_completed']}\n"
        f"- Average processing time: {throughput['avg_processing_time_hours']}h\n"
        f"- Fastest category: {throughput.get('fastest_type', 'N/A')}\n"
        f"- Slowest category: {throughput.get('slowest_type', 'N/A')}\n"
        f"- Current bottleneck: {throughput.get('bottleneck_type', 'None')}\n"
        f"- Breakdown:\n{type_breakdown}\n"
        "\n"
        "## Approval Pipeline\n"
        f"- Total requests: {approvals['total_approvals']}\n"
        f"- Average turnaround: {approvals['avg_approval_hours']}h\n"
        f"- Expiry rate: {approvals['expiry_rate']}%\n"
        "\n"
        "## Error Analysis\n"
        f"- Total errors: {errors['total_errors']}\n"
        f"- Error rate: {errors['error_rate']}%\n"
        f"- Retry success rate: {errors['retry_success_rate']}%\n"
        f"- Recurring patterns:\n{recurring_md}\n"
        "\n"
        "## Watcher Health\n"
        f"- Filesystem events: {watchers['filesystem_events']}\n"
        f"- Gmail events: {watchers['gmail_events']}\n"
        f"- WhatsApp events: {watchers['whatsapp_events']}\n"
        f"- Watcher errors: {watchers['watcher_errors']}\n"
        "\n"
        "## Optimization Suggestions\n"
        f"{suggestions}\n"
    )

    # Write report
    fname = f"AUDIT_WEEK_{end_str}.md"
    fpath = os.path.join(REPORTS_DIR, fname)

    if os.path.exists(fpath):
        counter = 1
        base = f"AUDIT_WEEK_{end_str}"
        while os.path.exists(fpath):
            fname = f"{base}_{counter}.md"
            fpath = os.path.join(REPORTS_DIR, fname)
            counter += 1

    try:
        with open(fpath, "w", encoding="utf-8") as fh:
            fh.write(report)
        return {"audit_path": f"Reports/{fname}"}
    except OSError as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    since = None
    for i, arg in enumerate(sys.argv):
        if arg == "--since" and i + 1 < len(sys.argv):
            try:
                since = datetime.strptime(sys.argv[i + 1], "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                print(f"Invalid date: {sys.argv[i + 1]}")
                sys.exit(1)

    print("Running weekly efficiency audit...")
    result = run_audit(since=since)

    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)
    else:
        print(f"Audit saved: {result['audit_path']}")
