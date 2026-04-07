#!/usr/bin/env python3
"""WhatsApp Web Watcher — Silver Tier Perception Layer (Playwright).

Connects to WhatsApp Web via a persistent Chromium browser session,
monitors for unread conversations, extracts messages, and creates
structured TASK_*.md files in Needs_Action/.

First-time setup requires scanning a QR code in a headed browser.
Subsequent runs reuse the saved session (headless by default).

Usage:
  python whatsapp_watcher.py --setup    # one-time QR code login (headed)
  python whatsapp_watcher.py --once     # single scan then exit
  python whatsapp_watcher.py            # continuous polling
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

# ---------------------------------------------------------------------------
# Playwright availability check
# ---------------------------------------------------------------------------

PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass

VAULT_DIR = os.path.dirname(os.path.abspath(__file__))
NEEDS_ACTION_DIR = os.path.join(VAULT_DIR, "Needs_Action")
REGISTRY_FILE = os.path.join(VAULT_DIR, ".whatsapp_registry.json")
CONFIG_FILE = os.path.join(VAULT_DIR, "config.json")
LOG_FILE = os.path.join(VAULT_DIR, "watcher.log")

DEFAULT_POLL_INTERVAL = 30  # seconds
DEFAULT_MAX_MESSAGES = 50
DEFAULT_SESSION_PATH = os.path.expanduser("~/.whatsapp_session")

WHATSAPP_URL = "https://web.whatsapp.com"

URGENT_KEYWORDS = [
    "urgent", "asap", "emergency", "immediately", "critical",
    "deadline", "important", "priority", "help", "sos",
]

shutdown_requested = False

# ---------------------------------------------------------------------------
# CSS selectors with fallbacks (WhatsApp Web DOM)
# ---------------------------------------------------------------------------

SELECTORS = {
    "side_panel": [
        '#pane-side',
        '[data-testid="chat-list"]',
    ],
    "unread_badge": [
        '[data-testid="icon-unread-count"]',
        'span[aria-label*="unread message"]',
        'span.x1rg5ohu[aria-label]',
    ],
    "chat_item": [
        '[data-testid="cell-frame-container"]',
        '#pane-side [role="listitem"]',
        '#pane-side > div > div > div > div',
    ],
    "message_in": [
        '.message-in',
        'div[class*="message-in"]',
        '[data-testid="msg-container"]',
    ],
    "message_text": [
        '.selectable-text',
        '.copyable-text',
        'span[dir="ltr"]',
        'span.selectable-text',
    ],
    "msg_timestamp": [
        '[data-testid="msg-meta"] span',
        'span[data-testid="msg-time"]',
        'div[data-pre-plain-text]',
    ],
    "msg_sender": [
        'span[data-testid="msg-text"]',
        'span[aria-label]._ao3e',
    ],
    "chat_header": [
        'header span[dir="auto"][title]',
        '#main header span[title]',
        'header [data-testid="conversation-info-header"] span[title]',
    ],
    "qr_code": [
        'div[data-testid="qrcode"] canvas',
        'canvas[aria-label*="Scan"]',
        'canvas[role="img"]',
    ],
    "search_box": [
        '[data-testid="chat-list-search"]',
        'div[contenteditable="true"][data-tab="3"]',
    ],
    "conversation_panel": [
        '#main',
        '[data-testid="conversation-panel-wrapper"]',
    ],
}

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
    """Load registry of processed message hashes. Returns {msg_hash: timestamp}."""
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
        tmp_fd, tmp_path = tempfile.mkstemp(dir=VAULT_DIR, suffix=".tmp")
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            json.dump(registry, fh, indent=2)
        os.replace(tmp_path, REGISTRY_FILE)
    except OSError as exc:
        log(f"WARNING: could not save registry: {exc}")


def message_hash(sender: str, timestamp: str, text: str) -> str:
    """SHA-256 hash of sender|timestamp|text for deduplication."""
    content = f"{sender}|{timestamp}|{text}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Selector helpers
# ---------------------------------------------------------------------------


def try_selectors(page_or_el, selector_key: str, timeout: int = 5000):
    """Try multiple fallback selectors, return the first match or None."""
    selectors = SELECTORS.get(selector_key, [])
    for sel in selectors:
        try:
            el = page_or_el.wait_for_selector(sel, timeout=timeout)
            if el:
                return el
        except Exception:
            continue
    return None


def query_all_selectors(page_or_el, selector_key: str) -> list:
    """Try multiple fallback selectors for query_selector_all, return first non-empty result."""
    selectors = SELECTORS.get(selector_key, [])
    for sel in selectors:
        try:
            results = page_or_el.query_selector_all(sel)
            if results:
                return results
        except Exception:
            continue
    return []


# ---------------------------------------------------------------------------
# WhatsApp Web Session
# ---------------------------------------------------------------------------


class WhatsAppWebSession:
    """Manages a persistent Chromium browser session for WhatsApp Web."""

    def __init__(self, session_path: str, headless: bool = True):
        self.session_path = session_path
        self.headless = headless
        self._playwright = None
        self._context = None
        self._page = None

    def start_browser(self) -> bool:
        """Launch a persistent Chromium browser context. Returns True on success."""
        if not PLAYWRIGHT_AVAILABLE:
            log("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
            return False
        try:
            os.makedirs(self.session_path, exist_ok=True)
            self._playwright = sync_playwright().start()
            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=self.session_path,
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
                locale="en-US",
            )
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
            return True
        except Exception as exc:
            log(f"ERROR starting browser: {exc}")
            self._cleanup()
            return False

    def stop_browser(self) -> None:
        """Gracefully close browser and Playwright."""
        self._cleanup()

    def _cleanup(self) -> None:
        try:
            if self._context:
                self._context.close()
        except Exception:
            pass
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        self._context = None
        self._page = None
        self._playwright = None

    def navigate(self) -> bool:
        """Navigate to WhatsApp Web. Returns True on success."""
        if not self._page:
            return False
        try:
            self._page.goto(WHATSAPP_URL, wait_until="domcontentloaded", timeout=30000)
            return True
        except Exception as exc:
            log(f"ERROR navigating to WhatsApp Web: {exc}")
            return False

    def is_logged_in(self, timeout: int = 15000) -> bool:
        """Check if the WhatsApp Web session is active (side panel visible)."""
        if not self._page:
            return False
        el = try_selectors(self._page, "side_panel", timeout=timeout)
        return el is not None

    def wait_for_login(self, timeout: int = 120000) -> bool:
        """Wait for QR code scan and successful login.

        Used in --setup mode. Shows the QR code page and waits for
        the user to scan it with their phone.
        Returns True if login succeeded within timeout.
        """
        if not self._page:
            return False
        log("waiting for QR code scan... please scan with your phone")
        log(f"timeout: {timeout // 1000} seconds")

        # Wait for side panel to appear (indicates successful login)
        el = try_selectors(self._page, "side_panel", timeout=timeout)
        if el:
            log("login successful — session saved")
            return True

        log("ERROR: login timed out — QR code not scanned in time")
        return False

    def get_unread_chats(self) -> list:
        """Find all chat elements that have an unread message badge.

        Returns a list of chat element handles.
        """
        if not self._page:
            return []

        # First, ensure side panel is loaded
        side = try_selectors(self._page, "side_panel", timeout=10000)
        if not side:
            return []

        # Find all unread badges
        unread_elements = query_all_selectors(self._page, "unread_badge")
        if not unread_elements:
            return []

        # For each unread badge, walk up to the chat item container
        chat_elements = []
        for badge in unread_elements:
            try:
                # Walk up through parent elements to find the clickable chat row
                chat_item = badge.evaluate_handle("""
                    el => {
                        let current = el;
                        for (let i = 0; i < 10; i++) {
                            current = current.parentElement;
                            if (!current) return null;
                            if (current.getAttribute('role') === 'listitem') return current;
                            if (current.getAttribute('data-testid') === 'cell-frame-container') return current;
                            if (current.getAttribute('tabindex') === '-1' && current.parentElement &&
                                current.parentElement.id === 'pane-side') return current;
                        }
                        // Fallback: return a reasonable ancestor
                        current = el;
                        for (let i = 0; i < 8; i++) {
                            current = current.parentElement;
                            if (!current) return null;
                        }
                        return current;
                    }
                """)
                if chat_item:
                    chat_elements.append(chat_item.as_element())
            except Exception:
                continue

        log(f"found {len(chat_elements)} unread chat(s)")
        return chat_elements

    def open_chat(self, chat_element) -> str:
        """Click on a chat element to open the conversation.

        Returns the contact/group name, or empty string on failure.
        """
        if not self._page or not chat_element:
            return ""
        try:
            chat_element.click()
            # Wait for conversation panel to load
            time.sleep(1.5)
            conv = try_selectors(self._page, "conversation_panel", timeout=5000)
            if not conv:
                return ""

            # Extract chat name from header
            header = try_selectors(self._page, "chat_header", timeout=3000)
            if header:
                name = header.get_attribute("title") or header.inner_text()
                return name.strip()
            return ""
        except Exception as exc:
            log(f"ERROR opening chat: {exc}")
            return ""

    def extract_messages(self, max_messages: int = 50) -> list:
        """Extract messages from the currently open conversation.

        Returns list of dicts: [{"sender": str, "timestamp": str, "text": str}, ...]
        """
        if not self._page:
            return []

        messages = []
        # Wait for messages to load
        time.sleep(1)

        # Find all message containers (incoming and outgoing)
        msg_elements = []
        for sel_key in ("message_in",):
            found = query_all_selectors(self._page, sel_key)
            msg_elements.extend(found)

        # Also get outgoing messages
        out_selectors = ['.message-out', 'div[class*="message-out"]']
        for sel in out_selectors:
            try:
                found = self._page.query_selector_all(sel)
                if found:
                    msg_elements.extend(found)
                    break
            except Exception:
                continue

        if not msg_elements:
            return []

        # Limit to most recent messages
        if len(msg_elements) > max_messages:
            msg_elements = msg_elements[-max_messages:]

        for msg_el in msg_elements:
            try:
                msg_data = self._parse_message_element(msg_el)
                if msg_data:
                    messages.append(msg_data)
            except Exception:
                continue

        return messages

    def _parse_message_element(self, msg_el) -> dict:
        """Parse a single message element into a structured dict."""
        text = ""
        sender = "Unknown"
        timestamp = ""

        # Extract text content
        text_els = []
        for sel in SELECTORS["message_text"]:
            try:
                text_els = msg_el.query_selector_all(sel)
                if text_els:
                    break
            except Exception:
                continue

        if text_els:
            text = " ".join(
                t.inner_text().strip() for t in text_els if t.inner_text().strip()
            )

        if not text:
            return {}

        # Determine sender: check for data-pre-plain-text attribute or class
        try:
            pre_plain = msg_el.query_selector("div[data-pre-plain-text]")
            if pre_plain:
                attr = pre_plain.get_attribute("data-pre-plain-text") or ""
                # Format: "[HH:MM, DD/MM/YYYY] Sender Name: "
                match = re.search(r"\]\s*(.+?):\s*$", attr)
                if match:
                    sender = match.group(1).strip()
                ts_match = re.search(r"\[([^\]]+)\]", attr)
                if ts_match:
                    timestamp = ts_match.group(1).strip()
        except Exception:
            pass

        # Check if message-out (sent by user)
        try:
            classes = msg_el.get_attribute("class") or ""
            if "message-out" in classes:
                sender = "You"
        except Exception:
            pass

        # Fallback timestamp from msg-meta
        if not timestamp:
            for sel in SELECTORS["msg_timestamp"]:
                try:
                    ts_el = msg_el.query_selector(sel)
                    if ts_el:
                        timestamp = ts_el.inner_text().strip()
                        break
                except Exception:
                    continue

        if not timestamp:
            timestamp = datetime.now(timezone.utc).strftime("%H:%M")

        return {
            "sender": sender,
            "timestamp": timestamp,
            "text": text[:2000],  # Limit text length
        }


# ---------------------------------------------------------------------------
# Preserved helper functions (unchanged contract)
# ---------------------------------------------------------------------------


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
        if sender.lower() in ("system", "you", "", "unknown"):
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
    contact: str,
    chat_name: str,
    priority: str,
) -> str:
    """Build TASK_*.md content from parsed WhatsApp Web messages."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    safe_contact = sanitize_yaml(contact)
    safe_chat = sanitize_yaml(chat_name)

    # Build conversation preview (last 10 messages)
    preview_msgs = messages[-10:]
    preview_lines = []
    for m in preview_msgs:
        text_preview = m["text"][:150]
        preview_lines.append(f"> **{m['sender']}** ({m['timestamp']}): {text_preview}")
    preview = "\n".join(preview_lines)

    msg_count = len(messages)
    senders = set(
        m["sender"] for m in messages
        if m["sender"].lower() not in ("system", "", "unknown")
    )

    task = (
        f"---\n"
        f"type: message\n"
        f"priority: {priority}\n"
        f"status: pending\n"
        f"created: {ts}\n"
        f"source: whatsapp_watcher.py\n"
        f'whatsapp_contact: "{safe_contact}"\n'
        f'whatsapp_chat: "{safe_chat}"\n'
        f"message_count: {msg_count}\n"
        f"---\n\n"
        f"## Task Description\n\n"
        f"WhatsApp conversation from **{chat_name}** (contact: {contact}).\n\n"
        f"**Source**: WhatsApp Web (Playwright)\n"
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


def write_task(task_content: str, chat_name: str) -> str:
    """Write task file to Needs_Action/ with atomic write. Returns filename."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", chat_name)[:30]
    task_filename = f"TASK_WA_{safe_name}_{ts}.md"
    task_path = os.path.join(NEEDS_ACTION_DIR, task_filename)

    try:
        os.makedirs(NEEDS_ACTION_DIR, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(dir=NEEDS_ACTION_DIR, suffix=".tmp")
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            fh.write(task_content)
        os.replace(tmp_path, task_path)
        log(f"task created: {task_filename}")
        return task_filename
    except OSError as exc:
        log(f"ERROR writing task: {exc}")
        return ""


# ---------------------------------------------------------------------------
# Scanning (main entry point called by watcher_manager.py)
# ---------------------------------------------------------------------------


def scan_whatsapp(config: dict, registry: dict) -> dict:
    """Single scan cycle: connect to WhatsApp Web, find unread chats,
    extract messages, create tasks.

    Returns updated registry.
    """
    if not PLAYWRIGHT_AVAILABLE:
        log("ERROR: playwright not installed — WhatsApp Web watcher disabled")
        return registry

    wa_config = config.get("whatsapp", {})
    max_messages = wa_config.get("max_messages_per_task", DEFAULT_MAX_MESSAGES)
    session_path = wa_config.get("session_path", DEFAULT_SESSION_PATH)
    session_path = os.path.expanduser(session_path)
    headless = wa_config.get("headless", True)

    # Check if session directory exists (has been set up)
    if not os.path.isdir(session_path):
        log("ERROR: no WhatsApp session found. Run: python whatsapp_watcher.py --setup")
        return registry

    session = WhatsAppWebSession(session_path=session_path, headless=headless)

    if not session.start_browser():
        return registry

    try:
        if not session.navigate():
            return registry

        # Check if logged in
        if not session.is_logged_in(timeout=20000):
            log("ERROR: WhatsApp session expired. Run: python whatsapp_watcher.py --setup")
            return registry

        # Find unread chats
        unread_chats = session.get_unread_chats()
        if not unread_chats:
            log("no unread chats found")
            return registry

        new_count = 0
        for chat_el in unread_chats:
            try:
                chat_name = session.open_chat(chat_el)
                if not chat_name:
                    continue

                messages = session.extract_messages(max_messages)
                if not messages:
                    log(f"WARNING: no messages extracted from chat '{chat_name}'")
                    continue

                # Deduplicate: check if we've already processed these messages
                new_messages = []
                for m in messages:
                    mhash = message_hash(m["sender"], m["timestamp"], m["text"])
                    if mhash not in registry:
                        new_messages.append(m)
                        registry[mhash] = datetime.now(timezone.utc).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        )

                if not new_messages:
                    log(f"chat '{chat_name}': all messages already processed")
                    continue

                # Build and write task
                contact = get_primary_contact(new_messages)
                priority = detect_priority(new_messages)
                task_content = build_whatsapp_task(
                    new_messages, contact, chat_name, priority
                )
                task_file = write_task(task_content, chat_name)

                if task_file:
                    new_count += 1
                    log(f"chat '{chat_name}': {len(new_messages)} new message(s) → {task_file}")

            except Exception as exc:
                log(f"ERROR processing chat: {exc}")
                continue

        if new_count:
            log(f"scan complete: {new_count} new task(s) created")
        else:
            log("scan complete: no new tasks")

        save_registry(registry)
    finally:
        session.stop_browser()

    return registry


# ---------------------------------------------------------------------------
# Setup mode (QR code login)
# ---------------------------------------------------------------------------


def setup_session(config: dict) -> bool:
    """Interactive setup: open headed browser for QR code scan.

    Returns True if login succeeded.
    """
    if not PLAYWRIGHT_AVAILABLE:
        log("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
        return False

    wa_config = config.get("whatsapp", {})
    session_path = wa_config.get("session_path", DEFAULT_SESSION_PATH)
    session_path = os.path.expanduser(session_path)

    log(f"setup mode: session will be saved to {session_path}")

    session = WhatsAppWebSession(session_path=session_path, headless=False)

    if not session.start_browser():
        return False

    try:
        if not session.navigate():
            return False

        # Check if already logged in
        if session.is_logged_in(timeout=5000):
            log("already logged in — session is valid")
            return True

        # Wait for QR scan
        log("QR code should be visible in the browser window")
        log("scan it with WhatsApp on your phone (Settings > Linked Devices > Link a Device)")
        success = session.wait_for_login(timeout=120000)
        if success:
            # Give it a moment to fully sync
            time.sleep(3)
        return success
    finally:
        session.stop_browser()


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

    # Setup mode
    if "--setup" in sys.argv:
        config = load_config()
        success = setup_session(config)
        sys.exit(0 if success else 1)

    single_run = "--once" in sys.argv

    log("WhatsApp Web watcher started" + (" (single scan)" if single_run else ""))

    if not PLAYWRIGHT_AVAILABLE:
        log("FATAL: playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    config = load_config()
    poll_interval = config.get("watchers", {}).get(
        "poll_interval_seconds", DEFAULT_POLL_INTERVAL
    )

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

    log("WhatsApp Web watcher stopped")


if __name__ == "__main__":
    main()
