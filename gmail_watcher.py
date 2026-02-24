#!/usr/bin/env python3
"""
gmail_watcher.py — Silver Tier Perception Layer (Email)

Monitors a Gmail inbox via IMAP, extracts email metadata, and creates
structured task files in Needs_Action/ for agent processing.

Requires: config.json with gmail credentials (App Password for Gmail).

Usage:
    python gmail_watcher.py              # continuous polling
    python gmail_watcher.py --once       # single scan then exit
"""

import os
import sys
import time
import json
import imaplib
import email
import email.header
import email.utils
import tempfile
import shutil
import re
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR = SCRIPT_DIR

NEEDS_ACTION_DIR = os.path.join(VAULT_DIR, "Needs_Action")
CONFIG_FILE = os.path.join(VAULT_DIR, "config.json")
REGISTRY_FILE = os.path.join(VAULT_DIR, ".gmail_registry.json")
LOG_FILE = os.path.join(VAULT_DIR, "watcher.log")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(message: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{ts} : [gmail] {message}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError as exc:
        print(f"WARNING: could not write to log file: {exc}", file=sys.stderr)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    if not os.path.isfile(CONFIG_FILE):
        log(f"FATAL: config file not found: {CONFIG_FILE}")
        sys.exit(1)
    with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)

# ---------------------------------------------------------------------------
# Registry (tracks processed email UIDs to avoid duplicates)
# ---------------------------------------------------------------------------

def load_registry() -> set:
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
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=VAULT_DIR, prefix=".gmail_reg_tmp_", suffix=".json"
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            json.dump(sorted(registry), fh, indent=2)
        shutil.move(tmp_path, REGISTRY_FILE)
    except OSError:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

# ---------------------------------------------------------------------------
# Email parsing helpers
# ---------------------------------------------------------------------------

def decode_header_value(raw: str) -> str:
    """Decode RFC 2047 encoded header values."""
    if not raw:
        return ""
    decoded_parts = email.header.decode_header(raw)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return " ".join(result)


def extract_body(msg: email.message.Message) -> str:
    """Extract plain text body from email message, truncated to 2000 chars."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="replace")
                    break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace")
    # Truncate for task file
    return body[:2000].strip()


def sanitize_for_yaml(text: str) -> str:
    """Sanitize a string for safe YAML frontmatter inclusion."""
    text = text.replace('"', '\\"')
    text = text.replace("\n", " ").replace("\r", "")
    return text.strip()

# ---------------------------------------------------------------------------
# Task file generation
# ---------------------------------------------------------------------------

def build_email_task(sender: str, subject: str, body_snippet: str,
                     date_str: str, uid: str) -> str:
    now = datetime.now(timezone.utc)
    iso_ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    safe_sender = sanitize_for_yaml(sender)
    safe_subject = sanitize_for_yaml(subject)
    # Body snippet for task description (first 500 chars)
    snippet = body_snippet[:500].replace("\n", "\n> ")

    priority = "medium"
    # Heuristic: urgent keywords bump to high
    lower_subj = subject.lower()
    if any(kw in lower_subj for kw in ["urgent", "asap", "critical", "important", "action required"]):
        priority = "high"

    return (
        "---\n"
        "type: email\n"
        f"priority: {priority}\n"
        "status: pending\n"
        f"created: {iso_ts}\n"
        "source: gmail_watcher.py\n"
        f"email_from: \"{safe_sender}\"\n"
        f"email_subject: \"{safe_subject}\"\n"
        f"email_date: \"{sanitize_for_yaml(date_str)}\"\n"
        f"email_uid: \"{uid}\"\n"
        "---\n"
        "\n"
        "## Task Description\n"
        f"Email received from **{sender}**.\n\n"
        f"**Subject**: {subject}\n\n"
        f"**Preview**:\n> {snippet}\n"
        "\n"
        "## Required Outcome\n"
        "Read and process this email. Determine if a response is needed, "
        "extract any action items, and produce a summary with recommended next steps.\n"
        "\n"
        "## Processing Checklist\n"
        "- [ ] analyze email content\n"
        "- [ ] extract action items\n"
        "- [ ] determine if response needed\n"
        "- [ ] generate plan for follow-up\n"
    )


def write_task(sender: str, subject: str, body: str,
               date_str: str, uid: str) -> str:
    now = datetime.now(timezone.utc)
    name = now.strftime("TASK_%Y%m%d_%H%M%S.md")
    dest = os.path.join(NEEDS_ACTION_DIR, name)

    counter = 0
    while os.path.exists(dest):
        counter += 1
        base = name.replace(".md", f"_{counter}.md")
        dest = os.path.join(NEEDS_ACTION_DIR, base)
        name = base

    content = build_email_task(sender, subject, body, date_str, uid)

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
# IMAP connection and scanning
# ---------------------------------------------------------------------------

def connect_imap(cfg: dict) -> imaplib.IMAP4_SSL:
    server = cfg.get("imap_server", "imap.gmail.com")
    port = cfg.get("imap_port", 993)
    email_addr = cfg.get("email", "")
    password = cfg.get("app_password", "")

    if not email_addr or not password:
        log("FATAL: Gmail credentials not configured in config.json")
        raise ValueError("Missing Gmail credentials")

    conn = imaplib.IMAP4_SSL(server, port)
    conn.login(email_addr, password)
    return conn


def fetch_unread_emails(conn: imaplib.IMAP4_SSL, cfg: dict,
                        registry: set) -> list:
    """Fetch unread emails, return list of (uid, sender, subject, body, date)."""
    folder = cfg.get("check_folder", "INBOX")
    max_emails = cfg.get("max_emails_per_poll", 5)

    conn.select(folder, readonly=not cfg.get("mark_as_read", False))

    # Search for unseen messages
    status, data = conn.search(None, "UNSEEN")
    if status != "OK" or not data[0]:
        return []

    uid_list = data[0].split()
    results = []

    for uid_bytes in uid_list[-max_emails:]:
        uid = uid_bytes.decode("utf-8")

        if uid in registry:
            continue

        status, msg_data = conn.fetch(uid_bytes, "(RFC822)")
        if status != "OK":
            continue

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        sender = decode_header_value(msg.get("From", "Unknown"))
        subject = decode_header_value(msg.get("Subject", "(No Subject)"))
        date_str = msg.get("Date", "")
        body = extract_body(msg)

        results.append((uid, sender, subject, body, date_str))

        # Mark as read if configured
        if cfg.get("mark_as_read", False):
            conn.store(uid_bytes, "+FLAGS", "\\Seen")

    return results

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def scan_gmail(cfg: dict, registry: set) -> set:
    """Single scan: connect, fetch unread, create tasks, return updated registry."""
    try:
        conn = connect_imap(cfg)
    except Exception as exc:
        log(f"error connecting to Gmail: {exc}")
        return registry

    try:
        emails = fetch_unread_emails(conn, cfg, registry)

        for uid, sender, subject, body, date_str in emails:
            try:
                task_name = write_task(sender, subject, body, date_str, uid)
                registry.add(uid)
                save_registry(registry)
                log(f"email detected — from: {sender[:50]}, subject: {subject[:60]} → task: {task_name}")
            except OSError as exc:
                log(f"error creating task for email UID {uid}: {exc}")

        if not emails:
            log("scan complete — no new emails")
    except Exception as exc:
        log(f"error scanning Gmail: {exc}")
    finally:
        try:
            conn.logout()
        except Exception:
            pass

    return registry


def main() -> None:
    print("")
    print("========================================")
    print("  Silver Tier AI Employee — Gmail Watcher")
    print("  Email Perception Layer Active")
    print("========================================")
    print("")

    config = load_config()
    gmail_cfg = config.get("gmail", {})
    poll_interval = config.get("watchers", {}).get("poll_interval_seconds", 30)

    if not gmail_cfg.get("email") or not gmail_cfg.get("app_password"):
        log("FATAL: Gmail credentials not set in config.json — fill in gmail.email and gmail.app_password")
        print("\nERROR: Configure Gmail credentials in config.json first.")
        print("  1. Enable 2FA on your Google account")
        print("  2. Generate an App Password at https://myaccount.google.com/apppasswords")
        print("  3. Set gmail.email and gmail.app_password in config.json")
        sys.exit(1)

    os.makedirs(NEEDS_ACTION_DIR, exist_ok=True)

    registry = load_registry()
    log(f"gmail watcher started — monitoring {gmail_cfg.get('email', 'N/A')}")
    log(f"registry loaded — {len(registry)} email(s) already processed")
    log(f"mode — polling ({poll_interval}s interval)")

    single_run = "--once" in sys.argv

    try:
        while True:
            registry = scan_gmail(gmail_cfg, registry)
            if single_run:
                log("single scan complete — exiting")
                break
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        log("gmail watcher stopped (keyboard interrupt)")
        print("\n  Gmail Watcher shut down. Goodbye.\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
