#!/usr/bin/env python3
"""
approval_gate.py — Silver Tier Human-in-the-Loop Module

Implements the approval workflow:
- Creates structured approval request files in Pending_Approval/
- Checks approval status before sensitive actions execute
- Handles expiry (low=72h, medium=48h, high=24h)

This module is imported by silver_loop.py and other components.
"""

import os
import re
import tempfile
import shutil
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR = SCRIPT_DIR

PENDING_APPROVAL_DIR = os.path.join(VAULT_DIR, "Pending_Approval")
DASHBOARD_FILE = os.path.join(VAULT_DIR, "Dashboard.md")

# Risk level → expiry window
EXPIRY_WINDOWS = {
    "low": timedelta(hours=72),
    "medium": timedelta(hours=48),
    "high": timedelta(hours=24),
}

# Action types that ALWAYS require approval
APPROVAL_REQUIRED_ACTIONS = {
    "send_email",
    "publish_post",
    "linkedin_post",
    "financial_transaction",
    "delete_external",
    "external_api_call",
}


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


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def requires_approval(action_type: str, task_type: str = "") -> bool:
    """Determine if an action requires human approval."""
    if action_type in APPROVAL_REQUIRED_ACTIONS:
        return True
    if task_type in ("email", "finance"):
        return True
    return False


def create_approval_file(
    action_type: str,
    description: str,
    target: str,
    risk_level: str = "medium",
    source_task: str = "direct invocation",
) -> dict:
    """Create a structured approval request file in Pending_Approval/.

    Returns:
        {"approval_file": "<path>", "status": "pending"} on success
        {"approval_file": None, "status": "failed", "error": "<msg>"} on failure
    """
    # Validate inputs
    if not action_type:
        return {"approval_file": None, "status": "failed", "error": "missing action_type"}
    if not description:
        return {"approval_file": None, "status": "failed", "error": "missing description"}
    if not target:
        return {"approval_file": None, "status": "failed", "error": "missing target"}

    # Normalize risk level
    if risk_level not in EXPIRY_WINDOWS:
        risk_level = "high"  # fail-safe

    now = now_utc()
    created_ts = iso_ts(now)
    expires_ts = iso_ts(now + EXPIRY_WINDOWS[risk_level])
    fname = f"APPROVAL_{file_ts(now)}.md"

    ensure_dir(PENDING_APPROVAL_DIR)
    dest = os.path.join(PENDING_APPROVAL_DIR, fname)

    # Handle collision
    counter = 0
    while os.path.exists(dest):
        counter += 1
        fname = f"APPROVAL_{file_ts(now)}_{counter}.md"
        dest = os.path.join(PENDING_APPROVAL_DIR, fname)

    # Risk assessment text
    risk_text = {
        "low": "Routine action with minimal impact. Auto-expires in 72h.",
        "medium": "Action affects external systems or contacts. Requires review within 48h.",
        "high": "Irreversible or high-impact action. Requires immediate review within 24h.",
    }

    content = (
        "---\n"
        "type: approval_request\n"
        f"action_type: {action_type}\n"
        f"risk_level: {risk_level}\n"
        "status: pending\n"
        f"created: {created_ts}\n"
        f"expires: {expires_ts}\n"
        "---\n"
        "\n"
        "# Approval Request\n"
        "\n"
        "## Action\n"
        f"**Type**: {action_type}\n"
        f"**Risk Level**: {risk_level}\n"
        "\n"
        "## Description\n"
        f"{description}\n"
        "\n"
        "## Target\n"
        f"{target}\n"
        "\n"
        "## Context\n"
        f"- **Requested by**: autonomous agent (Silver Tier)\n"
        f"- **Created**: {created_ts}\n"
        f"- **Expires**: {expires_ts}\n"
        f"- **Source task**: {source_task}\n"
        "\n"
        "## Risk Assessment\n"
        f"{risk_text.get(risk_level, risk_text['high'])}\n"
        "\n"
        "## Decision\n"
        "\n"
        "> **To approve**: Change `status: pending` to `status: approved` in frontmatter.\n"
        "> **To reject**: Change `status: pending` to `status: rejected` in frontmatter.\n"
        "> **To request changes**: Add notes under `## Reviewer Notes` and set `status: revision_requested`.\n"
        "\n"
        "- [ ] Reviewed by human operator\n"
        "- [ ] Decision recorded\n"
        "\n"
        "## Reviewer Notes\n"
        "\n"
    )

    # Atomic write
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=PENDING_APPROVAL_DIR, prefix=".approval_tmp_", suffix=".md"
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        shutil.move(tmp_path, dest)
    except OSError:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    # Log to dashboard
    _log_to_dashboard(
        f"APPROVAL REQUIRED ({risk_level}) — {action_type} targeting {target}. "
        f"Review within {EXPIRY_WINDOWS[risk_level].total_seconds()/3600:.0f}h. "
        f"File: {fname}",
        is_alert=(risk_level in ("medium", "high"))
    )

    return {"approval_file": f"Pending_Approval/{fname}", "status": "pending"}


def check_approval(action_type: str, target: str) -> dict:
    """Check if a valid, non-expired approval exists for an action.

    Returns:
        {"approved": True, "file": "<path>"} if approved
        {"approved": False, "reason": "<reason>"} otherwise
    """
    ensure_dir(PENDING_APPROVAL_DIR)
    now = now_utc()

    try:
        entries = sorted(os.listdir(PENDING_APPROVAL_DIR))
    except OSError:
        return {"approved": False, "reason": "cannot read Pending_Approval/"}

    for entry in entries:
        if not entry.startswith("APPROVAL_") or not entry.endswith(".md"):
            continue

        fpath = os.path.join(PENDING_APPROVAL_DIR, entry)
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            continue

        # Parse frontmatter
        fm = _parse_frontmatter(content)
        if not fm:
            continue

        # Match action type and target
        if fm.get("action_type") != action_type:
            continue

        # Check target in body
        if target and target not in content:
            continue

        status = fm.get("status", "")

        # Check expiry
        expires_str = fm.get("expires", "")
        if expires_str:
            try:
                expires_dt = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
                if now > expires_dt:
                    return {"approved": False, "reason": f"approval expired at {expires_str}"}
            except ValueError:
                pass

        if status == "approved":
            return {"approved": True, "file": f"Pending_Approval/{entry}"}
        elif status == "rejected":
            return {"approved": False, "reason": "approval was rejected"}
        elif status == "revision_requested":
            return {"approved": False, "reason": "revision requested by reviewer"}
        elif status == "pending":
            return {"approved": False, "reason": "approval is pending human review"}

    return {"approved": False, "reason": "no matching approval file found"}


def mark_approval_executed(approval_file: str) -> bool:
    """Mark an approval file as executed after the action completes."""
    fpath = os.path.join(VAULT_DIR, approval_file)
    if not os.path.isfile(fpath):
        return False

    try:
        with open(fpath, "r", encoding="utf-8") as fh:
            content = fh.read()

        content = re.sub(
            r"^status:\s*approved\s*$",
            "status: executed",
            content,
            flags=re.MULTILINE
        )

        with open(fpath, "w", encoding="utf-8") as fh:
            fh.write(content)
        return True
    except OSError:
        return False


def list_pending_approvals() -> list:
    """List all pending approval files with their metadata."""
    ensure_dir(PENDING_APPROVAL_DIR)
    results = []

    try:
        entries = sorted(os.listdir(PENDING_APPROVAL_DIR))
    except OSError:
        return results

    now = now_utc()

    for entry in entries:
        if not entry.startswith("APPROVAL_") or not entry.endswith(".md"):
            continue

        fpath = os.path.join(PENDING_APPROVAL_DIR, entry)
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            continue

        fm = _parse_frontmatter(content)
        if not fm:
            continue

        # Check if expired
        expired = False
        expires_str = fm.get("expires", "")
        if expires_str:
            try:
                expires_dt = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
                expired = now > expires_dt
            except ValueError:
                pass

        results.append({
            "file": entry,
            "action_type": fm.get("action_type", ""),
            "risk_level": fm.get("risk_level", ""),
            "status": fm.get("status", ""),
            "created": fm.get("created", ""),
            "expires": fm.get("expires", ""),
            "expired": expired,
        })

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter as a simple dict."""
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    fm = {}
    for line in match.group(1).split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip().strip('"').strip("'")
    return fm


def _log_to_dashboard(message: str, is_alert: bool = False) -> None:
    """Append an entry to Dashboard.md Recent Activity and optionally Alerts."""
    if not os.path.isfile(DASHBOARD_FILE):
        return

    ts = iso_ts()
    activity_entry = f"- {ts} : {message}\n"

    try:
        with open(DASHBOARD_FILE, "r", encoding="utf-8") as fh:
            content = fh.read()
    except OSError:
        return

    # Insert after ## Recent Activity
    content = content.replace(
        "## Recent Activity\n",
        f"## Recent Activity\n{activity_entry}",
        1
    )

    # Add alert if needed
    if is_alert:
        alert_entry = f"- {ts} : {message}\n"
        if "## Alerts" in content:
            content = content.replace(
                "## Alerts\n- None\n",
                f"## Alerts\n{alert_entry}",
                1
            )
            # If alerts section exists but doesn't have "None"
            if alert_entry not in content:
                content = content.replace(
                    "## Alerts\n",
                    f"## Alerts\n{alert_entry}",
                    1
                )

    try:
        with open(DASHBOARD_FILE, "w", encoding="utf-8") as fh:
            fh.write(content)
    except OSError:
        pass
