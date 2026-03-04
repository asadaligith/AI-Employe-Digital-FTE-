#!/usr/bin/env python3
"""WhatsApp Chat Export Watcher — Silver Tier Perception Layer.

Monitors Inbox/whatsapp/ for exported WhatsApp chat .txt files,
parses messages, and creates structured TASK_*.md files in Needs_Action/.

WhatsApp export format (supported variants):
  [DD/MM/YYYY, HH:MM:SS] Contact Name: Message text
  DD/MM/YYYY, HH:MM - Contact Name: Message text
  [MM/DD/YY, HH:MM:SS AM/PM] Contact Name: Message text

Usage:
  python whatsapp_watcher.py           # continuous polling
  python whatsapp_watcher.py --once    # single scan then exit
"""

import hashlib
import json
import os
import re
import signal
import sys
import tempfile
import time
from datetime import datetime, timezone

VAULT_DIR = os.path.dirname(os.path.abspath(__file__))
WHATSAPP_DIR = os.path.join(VAULT_DIR, "Inbox", "whatsapp")
NEEDS_ACTION_DIR = os.path.join(VAULT_DIR, "Needs_Action")
REGISTRY_FILE = os.path.join(VAULT_DIR, ".whatsapp_registry.json")
CONFIG_FILE = os.path.join(VAULT_DIR, "config.json")
LOG_FILE = os.path.join(VAULT_DIR, "watcher.log")

DEFAULT_POLL_INTERVAL = 30  # seconds
DEFAULT_MAX_MESSAGES = 50

# Patterns for WhatsApp export lines
# Pattern 1: [DD/MM/YYYY, HH:MM:SS] Contact: Message
PATTERN_BRACKET = re.compile(
    r"^\[(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\]\s*"
    r"(.+?):\s(.+)$"
)
# Pattern 2: DD/MM/YYYY, HH:MM - Contact: Message
PATTERN_DASH = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\s*-\s*"
    r"(.+?):\s(.+)$"
)

URGENT_KEYWORDS = [
    "urgent", "asap", "emergency", "immediately", "critical",
    "deadline", "important", "priority", "help", "sos",
]

shutdown_requested = False


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] [whatsapp-watcher] {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass
    print(line)


# ---------------------------------------------------------------------------
# Registry (deduplication)
# ---------------------------------------------------------------------------

def load_registry() -> dict:
    """Load registry of processed files. Returns {filename_hash: timestamp}."""
    if not os.path.isfile(REGISTRY_FILE):
        return {}
    try:
        with open(REGISTRY_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def save_registry(registry: dict) -> None:
    """Atomically save registry."""
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=VAULT_DIR, suffix=".tmp"
        )
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            json.dump(registry, fh, indent=2)
        os.replace(tmp_path, REGISTRY_FILE)
    except OSError as exc:
        log(f"WARNING: could not save registry: {exc}")


def file_hash(filepath: str) -> str:
    """SHA-256 hash of file content for deduplication."""
    h = hashlib.sha256()
    try:
        with open(filepath, "rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


# ---------------------------------------------------------------------------
# WhatsApp export parsing
# ---------------------------------------------------------------------------

def parse_whatsapp_export(filepath: str, max_messages: int = 50) -> list:
    """Parse a WhatsApp chat export .txt file into structured messages.

    Returns list of dicts: [{"sender": str, "timestamp": str, "text": str}, ...]
    """
    messages = []
    current_msg = None

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError as exc:
        log(f"ERROR reading {filepath}: {exc}")
        return []

    for line in lines:
        line = line.rstrip("\n\r")

        # Skip empty lines
        if not line.strip():
            continue

        # Try to match a new message line
        match = PATTERN_BRACKET.match(line) or PATTERN_DASH.match(line)

        if match:
            # Save previous message
            if current_msg:
                messages.append(current_msg)

            date_str, time_str, sender, text = match.groups()
            current_msg = {
                "sender": sender.strip(),
                "timestamp": f"{date_str}, {time_str}",
                "text": text.strip(),
            }
        elif current_msg:
            # Continuation line — append to current message
            current_msg["text"] += "\n" + line

    # Don't forget the last message
    if current_msg:
        messages.append(current_msg)

    # Limit messages
    if len(messages) > max_messages:
        messages = messages[-max_messages:]

    return messages


def detect_priority(messages: list) -> str:
    """Determine priority based on message content."""
    all_text = " ".join(m["text"].lower() for m in messages)
    for kw in URGENT_KEYWORDS:
        if kw in all_text:
            return "high"
    return "medium"


def get_primary_contact(messages: list) -> str:
    """Get the most frequent sender (excluding system messages)."""
    counts = {}
    for m in messages:
        sender = m["sender"]
        # Skip WhatsApp system messages
        if sender.lower() in ("system", "you", ""):
            continue
        counts[sender] = counts.get(sender, 0) + 1

    if not counts:
        return "Unknown Contact"
    return max(counts, key=counts.get)


def sanitize_yaml(s: str) -> str:
    """Make a string safe for YAML frontmatter values."""
    s = s.replace('"', '\\"').replace("\n", " ")
    if len(s) > 200:
        s = s[:200]
    return s


# ---------------------------------------------------------------------------
# Task creation
# ---------------------------------------------------------------------------

def build_whatsapp_task(
    messages: list,
    filename: str,
    contact: str,
    priority: str,
) -> str:
    """Build TASK_*.md content from parsed WhatsApp messages."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    safe_contact = sanitize_yaml(contact)
    safe_filename = sanitize_yaml(filename)

    # Build conversation preview (last 10 messages)
    preview_msgs = messages[-10:]
    preview_lines = []
    for m in preview_msgs:
        text_preview = m["text"][:150]
        preview_lines.append(f"> **{m['sender']}** ({m['timestamp']}): {text_preview}")
    preview = "\n".join(preview_lines)

    msg_count = len(messages)
    senders = set(m["sender"] for m in messages if m["sender"].lower() not in ("system", ""))

    task = (
        f"---\n"
        f"type: message\n"
        f"priority: {priority}\n"
        f"status: pending\n"
        f"created: {ts}\n"
        f"source: whatsapp_watcher.py\n"
        f'whatsapp_contact: "{safe_contact}"\n'
        f'whatsapp_file: "{safe_filename}"\n'
        f"message_count: {msg_count}\n"
        f"---\n\n"
        f"## Task Description\n\n"
        f"WhatsApp conversation exported from **{contact}**.\n\n"
        f"**Source file**: `{filename}`\n"
        f"**Messages**: {msg_count}\n"
        f"**Participants**: {', '.join(senders)}\n\n"
        f"### Conversation Preview (last {len(preview_msgs)} messages)\n\n"
        f"{preview}\n\n"
        f"## Required Outcome\n\n"
        f"Read and process this WhatsApp conversation. "
        f"Extract key information, action items, or requests. "
        f"Determine if a response or follow-up action is needed.\n\n"
        f"## Processing Checklist\n"
        f"- [ ] analyze conversation content\n"
        f"- [ ] extract action items or requests\n"
        f"- [ ] determine if response is needed\n"
        f"- [ ] generate plan for follow-up\n"
    )

    return task


def write_task(task_content: str, source_filename: str) -> str:
    """Write task file to Needs_Action/ with atomic write. Returns filename."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    # Create a short safe name from source file
    base = os.path.splitext(source_filename)[0]
    safe_base = re.sub(r"[^a-zA-Z0-9_-]", "_", base)[:30]
    task_filename = f"TASK_WA_{safe_base}_{ts}.md"
    task_path = os.path.join(NEEDS_ACTION_DIR, task_filename)

    try:
        os.makedirs(NEEDS_ACTION_DIR, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=NEEDS_ACTION_DIR, suffix=".tmp"
        )
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            fh.write(task_content)
        os.replace(tmp_path, task_path)
        log(f"task created: {task_filename}")
        return task_filename
    except OSError as exc:
        log(f"ERROR writing task: {exc}")
        return ""


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def scan_whatsapp(config: dict, registry: dict) -> dict:
    """Single scan cycle: check Inbox/whatsapp/ for new export files.

    Returns updated registry.
    """
    wa_config = config.get("whatsapp", {})
    watch_dir = os.path.join(VAULT_DIR, wa_config.get("watch_dir", "Inbox/whatsapp"))
    max_messages = wa_config.get("max_messages_per_task", DEFAULT_MAX_MESSAGES)

    if not os.path.isdir(watch_dir):
        os.makedirs(watch_dir, exist_ok=True)
        return registry

    try:
        entries = os.listdir(watch_dir)
    except OSError as exc:
        log(f"ERROR scanning {watch_dir}: {exc}")
        return registry

    txt_files = [
        f for f in entries
        if f.endswith(".txt") and not f.startswith(".")
    ]

    if not txt_files:
        return registry

    new_count = 0
    for fname in txt_files:
        fpath = os.path.join(watch_dir, fname)

        # Compute hash for deduplication
        fhash = file_hash(fpath)
        if not fhash:
            continue

        if fhash in registry:
            continue  # Already processed

        log(f"new WhatsApp export detected: {fname}")

        # Parse messages
        messages = parse_whatsapp_export(fpath, max_messages)
        if not messages:
            log(f"WARNING: no messages parsed from {fname}")
            registry[fhash] = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            continue

        # Build and write task
        contact = get_primary_contact(messages)
        priority = detect_priority(messages)
        task_content = build_whatsapp_task(messages, fname, contact, priority)
        task_file = write_task(task_content, fname)

        if task_file:
            new_count += 1

        # Mark as processed
        registry[fhash] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    if new_count:
        log(f"scan complete: {new_count} new task(s) created")
    save_registry(registry)
    return registry


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """Load config.json."""
    if not os.path.isfile(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------

def signal_handler(signum, frame):
    global shutdown_requested
    log("shutdown signal received")
    shutdown_requested = True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global shutdown_requested

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    single_run = "--once" in sys.argv

    log("WhatsApp watcher started" + (" (single scan)" if single_run else ""))

    config = load_config()
    wa_config = config.get("whatsapp", {})
    poll_interval = config.get("watchers", {}).get(
        "poll_interval_seconds", DEFAULT_POLL_INTERVAL
    )

    # Ensure watch directory exists
    watch_dir = os.path.join(
        VAULT_DIR, wa_config.get("watch_dir", "Inbox/whatsapp")
    )
    os.makedirs(watch_dir, exist_ok=True)

    registry = load_registry()

    while not shutdown_requested:
        try:
            registry = scan_whatsapp(config, registry)
        except Exception as exc:
            log(f"ERROR during scan: {exc}")

        if single_run:
            break

        # Wait for next poll
        for _ in range(int(poll_interval)):
            if shutdown_requested:
                break
            time.sleep(1)

    log("WhatsApp watcher stopped")


if __name__ == "__main__":
    main()
