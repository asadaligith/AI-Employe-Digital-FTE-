#!/usr/bin/env python3
"""
error_handler.py — Gold Tier Retry Engine

Provides retry logic with exponential backoff, max attempts, and fallback
strategies for task execution.

State is persisted in .gold_retry_state.json so retries survive across
gold_loop.py cycles.

Usage:
    from error_handler import RetryPolicy, with_retry, should_retry
"""

import os
import json
import time
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Callable, Any, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR = SCRIPT_DIR
RETRY_STATE_FILE = os.path.join(VAULT_DIR, ".gold_retry_state.json")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_ts(dt: datetime = None) -> str:
    if dt is None:
        dt = now_utc()
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 5.0        # seconds
    max_delay: float = 300.0       # seconds (5 min cap)
    backoff_factor: float = 2.0


def _load_retry_state() -> dict:
    """Load the global retry state file."""
    if not os.path.isfile(RETRY_STATE_FILE):
        return {}
    try:
        with open(RETRY_STATE_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_retry_state(state: dict) -> None:
    """Persist the global retry state file."""
    try:
        with open(RETRY_STATE_FILE, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2, ensure_ascii=False)
    except OSError:
        pass


def get_retry_state(task_filename: str) -> Optional[dict]:
    """Get retry state for a specific task.

    Returns:
        {"attempts": int, "last_error": str, "last_attempt": str,
         "next_retry_after": str} or None if no state exists.
    """
    state = _load_retry_state()
    return state.get(task_filename)


def update_retry_state(task_filename: str, attempt: int, error: str,
                       policy: RetryPolicy = None) -> None:
    """Record a retry attempt for a task."""
    if policy is None:
        policy = RetryPolicy()

    state = _load_retry_state()
    now = now_utc()

    # Calculate next retry delay
    delay = min(policy.base_delay * (policy.backoff_factor ** attempt),
                policy.max_delay)
    from datetime import timedelta
    next_retry = now + timedelta(seconds=delay)

    state[task_filename] = {
        "attempts": attempt,
        "last_error": str(error)[:500],
        "last_attempt": iso_ts(now),
        "next_retry_after": iso_ts(next_retry),
    }

    _save_retry_state(state)


def should_retry(task_filename: str, policy: RetryPolicy = None) -> dict:
    """Check whether a task should be retried.

    Returns:
        {"retry": bool, "reason": str, "attempts_so_far": int,
         "wait_seconds": float}
    """
    if policy is None:
        policy = RetryPolicy()

    task_state = get_retry_state(task_filename)

    if task_state is None:
        return {
            "retry": True,
            "reason": "no previous attempts",
            "attempts_so_far": 0,
            "wait_seconds": 0,
        }

    attempts = task_state.get("attempts", 0)

    if attempts >= policy.max_attempts:
        return {
            "retry": False,
            "reason": f"max attempts reached ({policy.max_attempts})",
            "attempts_so_far": attempts,
            "wait_seconds": 0,
        }

    # Check if enough time has passed since last attempt
    next_retry_str = task_state.get("next_retry_after", "")
    if next_retry_str:
        try:
            next_retry_dt = datetime.fromisoformat(
                next_retry_str.replace("Z", "+00:00")
            )
            now = now_utc()
            if now < next_retry_dt:
                wait = (next_retry_dt - now).total_seconds()
                return {
                    "retry": False,
                    "reason": f"backoff period not elapsed ({wait:.0f}s remaining)",
                    "attempts_so_far": attempts,
                    "wait_seconds": wait,
                }
        except ValueError:
            pass

    return {
        "retry": True,
        "reason": f"retry attempt {attempts + 1}/{policy.max_attempts}",
        "attempts_so_far": attempts,
        "wait_seconds": 0,
    }


def clear_retry_state(task_filename: str) -> None:
    """Remove retry state for a task after successful completion."""
    state = _load_retry_state()
    if task_filename in state:
        del state[task_filename]
        _save_retry_state(state)


def with_retry(
    func: Callable,
    args: tuple = (),
    kwargs: dict = None,
    policy: RetryPolicy = None,
    task_id: str = "",
) -> dict:
    """Execute a function with retry logic (inline, blocking).

    This is used for immediate retry within a single cycle. For cross-cycle
    retries, use should_retry() + update_retry_state() in gold_loop.py.

    Args:
        func: Callable to execute.
        args: Positional arguments.
        kwargs: Keyword arguments.
        policy: Retry policy. Defaults to RetryPolicy().
        task_id: Identifier for logging.

    Returns:
        {"success": bool, "result": any, "attempts": int,
         "errors": [str]}
    """
    if kwargs is None:
        kwargs = {}
    if policy is None:
        policy = RetryPolicy()

    errors = []

    for attempt in range(policy.max_attempts):
        try:
            result = func(*args, **kwargs)
            return {
                "success": True,
                "result": result,
                "attempts": attempt + 1,
                "errors": errors,
            }
        except Exception as exc:
            error_msg = f"Attempt {attempt + 1}/{policy.max_attempts}: {exc}"
            errors.append(error_msg)

            if attempt + 1 < policy.max_attempts:
                delay = min(
                    policy.base_delay * (policy.backoff_factor ** attempt),
                    policy.max_delay,
                )
                time.sleep(delay)

    return {
        "success": False,
        "result": None,
        "attempts": policy.max_attempts,
        "errors": errors,
    }


def get_all_retry_states() -> dict:
    """Return the full retry state for all tasks."""
    return _load_retry_state()


def cleanup_old_states(max_age_hours: int = 168) -> int:
    """Remove retry states older than max_age_hours (default 7 days).

    Returns number of entries removed.
    """
    from datetime import timedelta

    state = _load_retry_state()
    cutoff = now_utc() - timedelta(hours=max_age_hours)
    cutoff_str = iso_ts(cutoff)

    removed = 0
    to_remove = []

    for filename, entry in state.items():
        last_attempt = entry.get("last_attempt", "")
        if last_attempt and last_attempt < cutoff_str:
            to_remove.append(filename)

    for filename in to_remove:
        del state[filename]
        removed += 1

    if removed:
        _save_retry_state(state)

    return removed


if __name__ == "__main__":
    import sys
    print("error_handler.py — self-test")

    # Test retry policy
    policy = RetryPolicy(max_attempts=2, base_delay=0.1)
    print(f"Policy: {asdict(policy)}")

    # Test with_retry on a successful function
    result = with_retry(lambda: "ok", policy=policy, task_id="test")
    assert result["success"] is True
    assert result["attempts"] == 1
    print(f"Success test: {result}")

    # Test with_retry on a failing function
    call_count = 0
    def failing_func():
        global call_count
        call_count += 1
        raise ValueError(f"fail #{call_count}")

    result = with_retry(failing_func, policy=policy, task_id="test-fail")
    assert result["success"] is False
    assert result["attempts"] == 2
    print(f"Failure test: {result}")

    # Test state persistence
    update_retry_state("TEST_TASK.md", 1, "test error", policy)
    state = get_retry_state("TEST_TASK.md")
    print(f"State: {state}")
    assert state["attempts"] == 1

    check = should_retry("TEST_TASK.md", policy)
    print(f"Should retry: {check}")

    clear_retry_state("TEST_TASK.md")
    assert get_retry_state("TEST_TASK.md") is None
    print("State cleared.")

    print("OK")
