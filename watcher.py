#!/usr/bin/env python3
"""
watcher.py — Bronze Tier Perception Layer

Monitors the Inbox/ directory for new files, converts each detection
into a structured task in Needs_Action/, and maintains a processed-file
registry to avoid duplicates.

Usage:
    python watcher.py
"""

import os
import sys
import time
import json
import re
import tempfile
import shutil
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Paths (resolved relative to this script's location)
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR = SCRIPT_DIR  # vault root is where the script lives

INBOX_DIR = os.path.join(VAULT_DIR, "Inbox")
NEEDS_ACTION_DIR = os.path.join(VAULT_DIR, "Needs_Action")
DONE_DIR = os.path.join(VAULT_DIR, "Done")
DASHBOARD_FILE = os.path.join(VAULT_DIR, "Dashboard.md")
HANDBOOK_FILE = os.path.join(VAULT_DIR, "Company_Handbook.md")
REGISTRY_FILE = os.path.join(VAULT_DIR, ".watcher_registry.json")
LOG_FILE = os.path.join(VAULT_DIR, "watcher.log")

POLL_INTERVAL = 2  # seconds

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(message: str) -> None:
    """Print and append a timestamped log line."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{ts} : {message}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError as exc:
        print(f"WARNING: could not write to log file: {exc}", file=sys.stderr)

# ---------------------------------------------------------------------------
# Vault directory bootstrap
# ---------------------------------------------------------------------------

def ensure_vault_dirs() -> None:
    """Create any missing vault lifecycle directories."""
    for path in (INBOX_DIR, NEEDS_ACTION_DIR, DONE_DIR):
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)
            log(f"created missing directory: {os.path.basename(path)}/")

# ---------------------------------------------------------------------------
# Processed-file registry (JSON list of filenames)
# ---------------------------------------------------------------------------

def load_registry() -> set:
    """Load the set of already-processed filenames."""
    if not os.path.isfile(REGISTRY_FILE):
        return set()
    try:
        with open(REGISTRY_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, list):
                return set(data)
    except (OSError, json.JSONDecodeError):
        pass
    return set()


def save_registry(registry: set) -> None:
    """Persist the processed-file registry atomically."""
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=VAULT_DIR, prefix=".watcher_reg_tmp_", suffix=".json"
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            json.dump(sorted(registry), fh, indent=2)
        shutil.move(tmp_path, REGISTRY_FILE)
    except OSError:
        # Clean up on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

# ---------------------------------------------------------------------------
# Task file generation
# ---------------------------------------------------------------------------

def build_task_content(filename: str) -> str:
    """Return the markdown content for a new task file."""
    now = datetime.now(timezone.utc)
    iso_ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    return (
        "---\n"
        "type: file_event\n"
        "priority: medium\n"
        "status: pending\n"
        f"created: {iso_ts}\n"
        "source: watcher.py\n"
        f"inbox_file: {filename}\n"
        "---\n"
        "\n"
        "## Task Description\n"
        "New file detected in Inbox.\n"
        "\n"
        "## Required Outcome\n"
        "Process the input and complete task.\n"
        "\n"
        "## Processing Checklist\n"
        "- [ ] analyze task\n"
        "- [ ] generate plan\n"
        "- [ ] complete objective\n"
    )


def task_filename() -> str:
    """Generate a unique task filename: TASK_YYYYMMDD_HHMMSS.md"""
    now = datetime.now(timezone.utc)
    return now.strftime("TASK_%Y%m%d_%H%M%S.md")


def write_task(inbox_filename: str) -> str:
    """Create a task file in Needs_Action/ for the given inbox file.

    Uses atomic write (write-to-temp then move) to prevent partial files.
    Returns the task filename on success.
    """
    name = task_filename()
    dest = os.path.join(NEEDS_ACTION_DIR, name)

    # Avoid collision (same second)
    counter = 0
    while os.path.exists(dest):
        counter += 1
        base = name.replace(".md", f"_{counter}.md")
        dest = os.path.join(NEEDS_ACTION_DIR, base)
        name = base

    content = build_task_content(inbox_filename)

    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=NEEDS_ACTION_DIR, prefix=".task_tmp_", suffix=".md"
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

    return name

# ---------------------------------------------------------------------------
# Completion sweep — move inbox files to Done/ when task is completed
# ---------------------------------------------------------------------------

def extract_inbox_file(task_path: str) -> str:
    """Read a task file and return the inbox_file value from frontmatter."""
    try:
        with open(task_path, "r", encoding="utf-8") as fh:
            content = fh.read()
    except OSError:
        return ""
    match = re.search(r"^inbox_file:\s*(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return ""


def is_task_completed(task_path: str) -> bool:
    """Check if a task file has status: completed in its frontmatter."""
    try:
        with open(task_path, "r", encoding="utf-8") as fh:
            content = fh.read()
    except OSError:
        return False
    return bool(re.search(r"^status:\s*completed\s*$", content, re.MULTILINE))


def update_dashboard(inbox_filename: str, task_filename: str) -> None:
    """Add a completion log entry to Dashboard.md."""
    if not os.path.isfile(DASHBOARD_FILE):
        return

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_entry = (
        f"- {ts} : Inbox file `{inbox_filename}` archived to Done/ "
        f"(task `{task_filename}` completed)."
    )

    try:
        with open(DASHBOARD_FILE, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError as exc:
        log(f"error reading Dashboard.md: {exc}")
        return

    # Insert new entry after the "## Recent Activity" heading
    inserted = False
    new_lines = []
    for line in lines:
        new_lines.append(line)
        if not inserted and line.strip() == "## Recent Activity":
            new_lines.append(new_entry + "\n")
            inserted = True

    if not inserted:
        return

    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=VAULT_DIR, prefix=".dash_tmp_", suffix=".md"
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            fh.writelines(new_lines)
        shutil.move(tmp_path, DASHBOARD_FILE)
    except OSError as exc:
        log(f"error updating Dashboard.md: {exc}")
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def sweep_completed(registry: set) -> set:
    """Check Done/ for completed tasks and move their inbox files to Done/."""
    try:
        done_entries = os.listdir(DONE_DIR)
    except OSError:
        return registry

    for entry in sorted(done_entries):
        if not entry.startswith("TASK_") or not entry.endswith(".md"):
            continue

        task_path = os.path.join(DONE_DIR, entry)
        if not is_task_completed(task_path):
            continue

        inbox_filename = extract_inbox_file(task_path)
        if not inbox_filename:
            continue

        inbox_path = os.path.join(INBOX_DIR, inbox_filename)
        if not os.path.isfile(inbox_path):
            continue

        # Move inbox file to Done/
        done_dest = os.path.join(DONE_DIR, inbox_filename)
        # Handle name collision in Done/
        if os.path.exists(done_dest):
            base, ext = os.path.splitext(inbox_filename)
            counter = 1
            while os.path.exists(done_dest):
                done_dest = os.path.join(DONE_DIR, f"{base}_{counter}{ext}")
                counter += 1

        try:
            shutil.move(inbox_path, done_dest)
            moved_name = os.path.basename(done_dest)
            log(f"task completed — moved Inbox/{inbox_filename} → Done/{moved_name}")
            update_dashboard(inbox_filename, entry)

            # Remove from registry so it doesn't block future files with the same name
            registry.discard(inbox_filename)
            save_registry(registry)
        except OSError as exc:
            log(f"error moving {inbox_filename} to Done: {exc}")

    return registry


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def scan_inbox(registry: set) -> set:
    """Scan Inbox/ once, create tasks for new files, return updated registry."""
    try:
        entries = os.listdir(INBOX_DIR)
    except OSError as exc:
        log(f"error reading Inbox: {exc}")
        return registry

    for entry in sorted(entries):
        # Skip hidden files and .gitkeep
        if entry.startswith("."):
            continue

        if entry in registry:
            continue

        full_path = os.path.join(INBOX_DIR, entry)
        if not os.path.isfile(full_path):
            continue

        try:
            task_name = write_task(entry)
            registry.add(entry)
            save_registry(registry)
            log(f"new file detected — {entry} → task created: {task_name}")
        except OSError as exc:
            log(f"error creating task for {entry}: {exc}")

    return registry


def main() -> None:
    """Entry point — run the perception loop forever."""
    print("")
    print("========================================")
    print("  Bronze Tier AI Employee — Watcher")
    print("  Perception Layer Active")
    print("========================================")
    print("")
    ensure_vault_dirs()
    log("watcher started — monitoring Inbox/")
    log(f"mode — polling ({POLL_INTERVAL}s interval)")

    registry = load_registry()
    log(f"registry loaded — {len(registry)} file(s) already processed")

    try:
        while True:
            registry = scan_inbox(registry)
            registry = sweep_completed(registry)
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        log("watcher stopped (keyboard interrupt)")
        print("")
        print("========================================")
        print("  Watcher shut down. Goodbye.")
        print("========================================")
        print("")
        sys.exit(0)


if __name__ == "__main__":
    main()
