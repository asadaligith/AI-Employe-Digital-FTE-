#!/usr/bin/env python3
"""
watcher_manager.py — Silver Tier Watcher Orchestrator

Runs both the filesystem watcher (Inbox/) and Gmail watcher concurrently
using threads. Provides a single entry point for all perception-layer monitoring.

Usage:
    python watcher_manager.py              # run all enabled watchers
    python watcher_manager.py --once       # single scan cycle then exit
"""

import os
import sys
import json
import threading
import time
import signal
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR = SCRIPT_DIR
CONFIG_FILE = os.path.join(VAULT_DIR, "config.json")
LOG_FILE = os.path.join(VAULT_DIR, "watcher.log")

shutdown_event = threading.Event()


def log(message: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{ts} : [manager] {message}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def load_config() -> dict:
    if not os.path.isfile(CONFIG_FILE):
        return {"watchers": {"gmail_enabled": True, "filesystem_enabled": True}}
    with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def run_filesystem_watcher(single_run: bool) -> None:
    """Run the filesystem watcher (watcher.py) in this thread."""
    sys.path.insert(0, VAULT_DIR)
    try:
        import watcher
    except ImportError:
        log("ERROR: could not import watcher.py")
        return

    log("filesystem watcher thread started")

    registry = watcher.load_registry()
    try:
        while not shutdown_event.is_set():
            registry = watcher.scan_inbox(registry)
            registry = watcher.sweep_completed(registry)
            if single_run:
                break
            shutdown_event.wait(timeout=watcher.POLL_INTERVAL)
    except Exception as exc:
        log(f"filesystem watcher error: {exc}")

    log("filesystem watcher thread stopped")


def run_gmail_watcher(single_run: bool) -> None:
    """Run the Gmail watcher in this thread."""
    sys.path.insert(0, VAULT_DIR)
    try:
        import gmail_watcher
    except ImportError:
        log("ERROR: could not import gmail_watcher.py")
        return

    config = load_config()
    gmail_cfg = config.get("gmail", {})
    poll_interval = config.get("watchers", {}).get("poll_interval_seconds", 30)

    if not gmail_cfg.get("email") or not gmail_cfg.get("app_password"):
        log("gmail watcher skipped — credentials not configured in config.json")
        return

    log("gmail watcher thread started")

    registry = gmail_watcher.load_registry()
    try:
        while not shutdown_event.is_set():
            registry = gmail_watcher.scan_gmail(gmail_cfg, registry)
            if single_run:
                break
            shutdown_event.wait(timeout=poll_interval)
    except Exception as exc:
        log(f"gmail watcher error: {exc}")

    log("gmail watcher thread stopped")


def signal_handler(signum, frame):
    log("shutdown signal received")
    shutdown_event.set()


def main() -> None:
    print("")
    print("========================================")
    print("  Silver Tier — Watcher Manager")
    print("  Unified Perception Layer")
    print("========================================")
    print("")

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    config = load_config()
    watchers_cfg = config.get("watchers", {})
    single_run = "--once" in sys.argv

    threads = []

    # Filesystem watcher (Inbox/ → Needs_Action/)
    if watchers_cfg.get("filesystem_enabled", True):
        t = threading.Thread(
            target=run_filesystem_watcher,
            args=(single_run,),
            name="filesystem-watcher",
            daemon=True
        )
        threads.append(t)
        log("filesystem watcher enabled")
    else:
        log("filesystem watcher disabled in config")

    # Gmail watcher (IMAP → Needs_Action/)
    if watchers_cfg.get("gmail_enabled", True):
        t = threading.Thread(
            target=run_gmail_watcher,
            args=(single_run,),
            name="gmail-watcher",
            daemon=True
        )
        threads.append(t)
        log("gmail watcher enabled")
    else:
        log("gmail watcher disabled in config")

    if not threads:
        log("no watchers enabled — nothing to do")
        return

    log(f"starting {len(threads)} watcher(s)")

    for t in threads:
        t.start()

    if single_run:
        for t in threads:
            t.join(timeout=60)
        log("single scan complete — all watchers finished")
    else:
        try:
            while not shutdown_event.is_set():
                # Check thread health
                alive = [t for t in threads if t.is_alive()]
                if not alive:
                    log("all watcher threads have stopped")
                    break
                shutdown_event.wait(timeout=5)
        except KeyboardInterrupt:
            shutdown_event.set()

        for t in threads:
            t.join(timeout=10)

    log("watcher manager stopped")
    print("\n  Watcher Manager shut down. Goodbye.\n")


if __name__ == "__main__":
    main()
