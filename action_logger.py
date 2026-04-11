#!/usr/bin/env python3
"""
action_logger.py — Gold Tier Structured Action Logger

Centralized logging for all Gold Tier actions. Every action gets a structured
JSON-line entry in Logs/actions.jsonl plus human-readable entries in
Logs/ACTION_*.md.

Usage:
    from action_logger import log_action, get_actions_since, get_action_summary
"""

import os
import json
import time
from datetime import datetime, timezone
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR = SCRIPT_DIR
LOGS_DIR = os.path.join(VAULT_DIR, "Logs")
ACTIONS_JSONL = os.path.join(LOGS_DIR, "actions.jsonl")


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


def log_action(
    action: str,
    target: str,
    result: str,
    error: Optional[str] = None,
    duration_ms: int = 0,
    metadata: Optional[dict] = None,
) -> dict:
    """Write a structured log entry for an action.

    Args:
        action: Action type (e.g. "execute_task", "send_email", "retry_task")
        target: What was acted on (e.g. "TASK_*.md", email address)
        result: "success" or "failure"
        error: Error message if result is "failure"
        duration_ms: How long the action took in milliseconds
        metadata: Additional key-value pairs

    Returns:
        The log entry dict that was written.
    """
    os.makedirs(LOGS_DIR, exist_ok=True)

    entry = {
        "ts": iso_ts(),
        "action": action,
        "target": target,
        "result": result,
        "duration_ms": duration_ms,
        "error": error,
        "metadata": metadata or {},
    }

    # Write to JSONL
    try:
        with open(ACTIONS_JSONL, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass

    # Write human-readable markdown for significant actions
    if result == "failure" or action in (
        "execute_task", "retry_task", "send_email", "odoo_transaction",
        "social_media_post", "generate_report", "run_audit",
        "cycle_start", "cycle_end",
    ):
        _write_action_md(entry)

    return entry


def _write_action_md(entry: dict) -> None:
    """Write a human-readable markdown log file for an action."""
    ts = file_ts()
    fname = f"ACTION_{ts}_{entry['action']}.md"
    fpath = os.path.join(LOGS_DIR, fname)

    # Handle collision
    counter = 0
    while os.path.exists(fpath):
        counter += 1
        fname = f"ACTION_{ts}_{entry['action']}_{counter}.md"
        fpath = os.path.join(LOGS_DIR, fname)

    content = (
        "---\n"
        "type: action_log\n"
        f"action: {entry['action']}\n"
        f"target: \"{entry['target']}\"\n"
        f"result: {entry['result']}\n"
        f"timestamp: {entry['ts']}\n"
        "---\n"
        "\n"
        f"# Action: {entry['action']}\n"
        "\n"
        f"- **Target**: {entry['target']}\n"
        f"- **Result**: {entry['result']}\n"
        f"- **Duration**: {entry['duration_ms']}ms\n"
    )

    if entry.get("error"):
        content += f"- **Error**: {entry['error']}\n"

    if entry.get("metadata"):
        content += "\n## Metadata\n"
        for k, v in entry["metadata"].items():
            content += f"- **{k}**: {v}\n"

    try:
        with open(fpath, "w", encoding="utf-8") as fh:
            fh.write(content)
    except OSError:
        pass


def get_actions_since(since_dt: datetime) -> list:
    """Return all action entries since a given datetime.

    Args:
        since_dt: Datetime (UTC) to filter from.

    Returns:
        List of action entry dicts, sorted by timestamp ascending.
    """
    if not os.path.isfile(ACTIONS_JSONL):
        return []

    since_str = iso_ts(since_dt)
    results = []

    try:
        with open(ACTIONS_JSONL, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("ts", "") >= since_str:
                        results.append(entry)
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass

    return results


def get_action_summary(since_dt: datetime) -> dict:
    """Return aggregated counts of actions since a datetime.

    Returns:
        {
            "total": int,
            "by_action": {"execute_task": {"success": N, "failure": N}, ...},
            "successes": int,
            "failures": int,
            "errors": [{"ts": ..., "action": ..., "error": ...}, ...]
        }
    """
    actions = get_actions_since(since_dt)

    summary = {
        "total": len(actions),
        "by_action": {},
        "successes": 0,
        "failures": 0,
        "errors": [],
    }

    for entry in actions:
        action = entry.get("action", "unknown")
        result = entry.get("result", "unknown")

        if action not in summary["by_action"]:
            summary["by_action"][action] = {"success": 0, "failure": 0}

        if result == "success":
            summary["by_action"][action]["success"] += 1
            summary["successes"] += 1
        else:
            summary["by_action"][action]["failure"] += 1
            summary["failures"] += 1
            if entry.get("error"):
                summary["errors"].append({
                    "ts": entry["ts"],
                    "action": action,
                    "target": entry.get("target", ""),
                    "error": entry["error"],
                })

    return summary


if __name__ == "__main__":
    # Quick self-test
    print("action_logger.py — self-test")
    entry = log_action(
        action="self_test",
        target="action_logger.py",
        result="success",
        duration_ms=42,
        metadata={"test": True},
    )
    print(f"Logged: {json.dumps(entry, indent=2)}")

    summary = get_action_summary(datetime(2000, 1, 1, tzinfo=timezone.utc))
    print(f"Summary: {json.dumps(summary, indent=2)}")
    print("OK")
