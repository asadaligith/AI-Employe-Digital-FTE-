#!/usr/bin/env python3
"""
ceo_report_generator.py — Gold Tier Weekly CEO Briefing

Generates a comprehensive weekly report from Done/, Logs/, Dashboard.md.
Output: Reports/CEO_REPORT_WEEK_YYYY-MM-DD.md

Usage:
    python ceo_report_generator.py                 # current week
    python ceo_report_generator.py --since 2026-04-01  # custom start date
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
LOGS_DIR = os.path.join(VAULT_DIR, "Logs")
REPORTS_DIR = os.path.join(VAULT_DIR, "Reports")
PENDING_APPROVAL_DIR = os.path.join(VAULT_DIR, "Pending_Approval")
APPROVED_DIR = os.path.join(VAULT_DIR, "Approved")
DASHBOARD_FILE = os.path.join(VAULT_DIR, "Dashboard.md")
CONFIG_FILE = os.path.join(VAULT_DIR, "config.json")

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
# Metric Collection
# ---------------------------------------------------------------------------

def collect_task_metrics(since: datetime) -> dict:
    """Count completed tasks by type and priority from Done/."""
    metrics = {
        "total_completed": 0,
        "by_type": {},
        "by_priority": {"high": 0, "medium": 0, "low": 0},
    }

    since_str = since.strftime("%Y-%m-%d")

    try:
        entries = os.listdir(DONE_DIR)
    except OSError:
        return metrics

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

        # Check if completed within the period
        # Look for completion timestamp in content
        completed_in_period = False
        if since_str in content:
            completed_in_period = True
        elif fm.get("created", "") >= since_str:
            completed_in_period = True

        if not completed_in_period:
            continue

        metrics["total_completed"] += 1

        task_type = fm.get("type", "general")
        metrics["by_type"][task_type] = metrics["by_type"].get(task_type, 0) + 1

        priority = fm.get("priority", "low")
        if priority in metrics["by_priority"]:
            metrics["by_priority"][priority] += 1

    return metrics


def collect_approval_metrics(since: datetime) -> dict:
    """Approval stats from Pending_Approval/ and Approved/."""
    metrics = {
        "total_requests": 0,
        "approved": 0,
        "rejected": 0,
        "expired": 0,
        "pending": 0,
    }

    since_str = since.strftime("%Y-%m-%d")

    for directory in (PENDING_APPROVAL_DIR, APPROVED_DIR):
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

            metrics["total_requests"] += 1
            status = fm.get("status", "pending")
            if status == "approved" or status == "executed":
                metrics["approved"] += 1
            elif status == "rejected":
                metrics["rejected"] += 1
            elif status == "pending":
                # Check if expired
                expires = fm.get("expires", "")
                if expires:
                    try:
                        expires_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                        if now_utc() > expires_dt:
                            metrics["expired"] += 1
                            continue
                    except ValueError:
                        pass
                metrics["pending"] += 1

    return metrics


def collect_error_metrics(since: datetime) -> dict:
    """Error and retry stats from action logs."""
    summary = get_action_summary(since)
    return {
        "total_actions": summary.get("total", 0),
        "successes": summary.get("successes", 0),
        "failures": summary.get("failures", 0),
        "error_list": summary.get("errors", [])[:10],
    }


def collect_odoo_metrics() -> dict:
    """Financial summary from Odoo (if configured)."""
    try:
        config = {}
        with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
            config = json.load(fh)

        if not config.get("odoo", {}).get("enabled"):
            return {"available": False}

        from odoo_client import OdooClient
        client = OdooClient.from_config()
        client.authenticate()
        summary = client.get_financial_summary()
        summary["available"] = True
        return summary
    except Exception:
        return {"available": False}


def collect_social_metrics(since: datetime) -> dict:
    """Social media activity stats."""
    metrics = {
        "drafts_created": 0,
        "by_platform": {},
        "posts_published": 0,
    }

    since_str = since.strftime("%Y-%m-%d")

    if not os.path.isdir(PENDING_APPROVAL_DIR):
        return metrics

    for directory in (PENDING_APPROVAL_DIR, APPROVED_DIR):
        if not os.path.isdir(directory):
            continue
        try:
            entries = os.listdir(directory)
        except OSError:
            continue

        for entry in entries:
            if not (entry.startswith("SOCIAL_") or entry.startswith("LINKEDIN_")):
                continue
            if not entry.endswith(".md"):
                continue

            fpath = os.path.join(directory, entry)
            try:
                with open(fpath, "r", encoding="utf-8") as fh:
                    content = fh.read(500)
            except OSError:
                continue

            fm = parse_frontmatter(content)
            created = fm.get("created", "")
            if created < since_str:
                continue

            metrics["drafts_created"] += 1
            platform = fm.get("platform", "linkedin")
            metrics["by_platform"][platform] = metrics["by_platform"].get(platform, 0) + 1

            if fm.get("status") in ("executed", "posted"):
                metrics["posts_published"] += 1

    return metrics


def collect_communication_metrics(since: datetime) -> dict:
    """Email and message processing stats."""
    metrics = {
        "emails_processed": 0,
        "whatsapp_messages": 0,
    }

    since_str = since.strftime("%Y-%m-%d")

    try:
        entries = os.listdir(DONE_DIR)
    except OSError:
        return metrics

    for entry in entries:
        if not entry.endswith(".md"):
            continue

        fpath = os.path.join(DONE_DIR, entry)
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                content = fh.read(1000)
        except OSError:
            continue

        fm = parse_frontmatter(content)
        created = fm.get("created", "")
        if created and created < since_str:
            continue

        task_type = fm.get("type", "")
        source = fm.get("source", "")

        if "email" in task_type or "email" in source:
            metrics["emails_processed"] += 1
        elif "whatsapp" in source.lower() or "message" in task_type:
            metrics["whatsapp_messages"] += 1

    return metrics


# ---------------------------------------------------------------------------
# AI Recommendations
# ---------------------------------------------------------------------------

def generate_recommendations(metrics: dict) -> str:
    """Generate recommendations using Claude CLI, with template fallback."""
    prompt = (
        "Based on the following weekly AI Employee system metrics, provide "
        "3-5 brief, actionable recommendations for improvement. "
        "Be specific and practical. Output plain text, no markdown headers.\n\n"
        f"Metrics:\n{json.dumps(metrics, indent=2, default=str)}"
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
    recs = []

    tasks = metrics.get("tasks", {})
    errors = metrics.get("errors", {})
    approvals = metrics.get("approvals", {})

    if errors.get("failures", 0) > 0:
        fail_rate = errors["failures"] / max(errors.get("total_actions", 1), 1)
        if fail_rate > 0.1:
            recs.append(
                f"High failure rate ({fail_rate:.0%}). Review error patterns in "
                f"Logs/actions.jsonl and address recurring issues."
            )

    if approvals.get("expired", 0) > 0:
        recs.append(
            f"{approvals['expired']} approval(s) expired this week. "
            f"Consider reviewing approval queue more frequently."
        )

    if approvals.get("pending", 0) > 3:
        recs.append(
            f"{approvals['pending']} approvals still pending. "
            f"Process the approval backlog to unblock waiting tasks."
        )

    if tasks.get("total_completed", 0) == 0:
        recs.append(
            "No tasks completed this week. Check if the pipeline is running "
            "and tasks are arriving in Needs_Action/."
        )

    if not recs:
        recs.append("System operating normally. No immediate action items.")

    return "\n".join(f"- {r}" for r in recs)


# ---------------------------------------------------------------------------
# Report Generation
# ---------------------------------------------------------------------------

def generate_weekly_report(week_start: datetime = None) -> dict:
    """Generate the weekly CEO report.

    Args:
        week_start: Start of the reporting period. Defaults to 7 days ago.

    Returns:
        {"report_path": str} on success, {"error": str} on failure.
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)

    if week_start is None:
        week_start = now_utc() - timedelta(days=7)

    week_end = now_utc()
    start_str = week_start.strftime("%Y-%m-%d")
    end_str = week_end.strftime("%Y-%m-%d")

    # Collect all metrics
    task_metrics = collect_task_metrics(week_start)
    approval_metrics = collect_approval_metrics(week_start)
    error_metrics = collect_error_metrics(week_start)
    odoo_metrics = collect_odoo_metrics()
    social_metrics = collect_social_metrics(week_start)
    comm_metrics = collect_communication_metrics(week_start)

    all_metrics = {
        "tasks": task_metrics,
        "approvals": approval_metrics,
        "errors": error_metrics,
        "social": social_metrics,
        "communications": comm_metrics,
    }

    # Generate recommendations
    recommendations = generate_recommendations(all_metrics)

    # Generate executive summary
    summary_parts = []
    summary_parts.append(
        f"This week the system processed {task_metrics['total_completed']} tasks"
    )
    if error_metrics["failures"] > 0:
        summary_parts.append(
            f"with {error_metrics['failures']} failure(s) out of "
            f"{error_metrics['total_actions']} total actions"
        )
    if approval_metrics["total_requests"] > 0:
        summary_parts.append(
            f"and handled {approval_metrics['total_requests']} approval request(s)"
        )
    exec_summary = ", ".join(summary_parts) + "."

    # Task breakdown
    type_breakdown = "\n".join(
        f"  - {t}: {c}"
        for t, c in sorted(task_metrics["by_type"].items(), key=lambda x: -x[1])
    ) or "  - No tasks completed"

    # Build report
    report = (
        "---\n"
        "type: ceo_report\n"
        f"period: {start_str} to {end_str}\n"
        f"generated: {iso_ts()}\n"
        "---\n"
        "\n"
        "# CEO Weekly Briefing\n"
        "\n"
        "## Executive Summary\n"
        f"{exec_summary}\n"
        "\n"
        "## Task Performance\n"
        f"- Completed: {task_metrics['total_completed']}\n"
        f"  - High priority: {task_metrics['by_priority']['high']}\n"
        f"  - Medium priority: {task_metrics['by_priority']['medium']}\n"
        f"  - Low priority: {task_metrics['by_priority']['low']}\n"
        f"- Breakdown by type:\n"
        f"{type_breakdown}\n"
        "\n"
        "## Communication Activity\n"
        f"- Emails processed: {comm_metrics['emails_processed']}\n"
        f"- WhatsApp messages: {comm_metrics['whatsapp_messages']}\n"
        f"- Approval requests: {approval_metrics['total_requests']} "
        f"(approved: {approval_metrics['approved']}, "
        f"rejected: {approval_metrics['rejected']}, "
        f"expired: {approval_metrics['expired']}, "
        f"pending: {approval_metrics['pending']})\n"
        "\n"
    )

    # Financial section (if Odoo configured)
    if odoo_metrics.get("available"):
        report += (
            "## Financial Overview\n"
            f"- Total Receivable: {odoo_metrics.get('currency', '$')}"
            f"{odoo_metrics.get('total_receivable', 0):,.2f}\n"
            f"- Total Payable: {odoo_metrics.get('currency', '$')}"
            f"{odoo_metrics.get('total_payable', 0):,.2f}\n"
            f"- Overdue: {odoo_metrics.get('currency', '$')}"
            f"{odoo_metrics.get('overdue_amount', 0):,.2f}\n"
            f"- Invoices: {odoo_metrics.get('invoice_count', 0)}\n"
            f"- Payments: {odoo_metrics.get('payment_count', 0)}\n"
            "\n"
        )

    # Social media section
    if social_metrics["drafts_created"] > 0:
        platform_breakdown = ", ".join(
            f"{p}: {c}" for p, c in social_metrics["by_platform"].items()
        )
        report += (
            "## Social Media\n"
            f"- Posts drafted: {social_metrics['drafts_created']} ({platform_breakdown})\n"
            f"- Posts published: {social_metrics['posts_published']}\n"
            "\n"
        )

    # Issues & Alerts
    report += "## Issues & Alerts\n"
    if error_metrics["error_list"]:
        for err in error_metrics["error_list"][:5]:
            report += f"- [{err['ts']}] {err['action']}: {err['error'][:100]}\n"
    else:
        report += "- No significant issues this week.\n"
    report += "\n"

    # System health
    report += (
        "## System Health\n"
        f"- Total actions logged: {error_metrics['total_actions']}\n"
        f"- Success rate: "
    )
    if error_metrics["total_actions"] > 0:
        rate = error_metrics["successes"] / error_metrics["total_actions"] * 100
        report += f"{rate:.1f}%\n"
    else:
        report += "N/A (no actions logged)\n"
    report += "\n"

    # Recommendations
    report += (
        "## Recommendations\n"
        f"{recommendations}\n"
    )

    # Write report
    fname = f"CEO_REPORT_WEEK_{end_str}.md"
    fpath = os.path.join(REPORTS_DIR, fname)

    # Handle collision
    if os.path.exists(fpath):
        counter = 1
        base = f"CEO_REPORT_WEEK_{end_str}"
        while os.path.exists(fpath):
            fname = f"{base}_{counter}.md"
            fpath = os.path.join(REPORTS_DIR, fname)
            counter += 1

    try:
        with open(fpath, "w", encoding="utf-8") as fh:
            fh.write(report)
        return {"report_path": f"Reports/{fname}"}
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

    print("Generating CEO weekly report...")
    result = generate_weekly_report(week_start=since)

    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)
    else:
        print(f"Report saved: {result['report_path']}")
