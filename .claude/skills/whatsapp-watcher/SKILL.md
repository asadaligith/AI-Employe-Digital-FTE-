# Skill: whatsapp-watcher

## Tier
Silver

## Purpose

Connect to WhatsApp Web via Playwright browser automation, monitor for unread conversations, extract messages, and create structured task files in `Needs_Action/` for agent processing.

## Trigger

Activated as a perception-layer watcher using browser automation. Runs continuously via `watcher_manager.py` or as a standalone script. Detects unread WhatsApp conversations directly from `web.whatsapp.com`.

## Input

Unread WhatsApp conversations via a persistent Chromium browser session connected to WhatsApp Web.

**Requirements:**
- Playwright installed (`pip install playwright && playwright install chromium`)
- One-time QR code scan via `--setup` mode
- Persistent session stored at `~/.whatsapp_session` (outside vault for security)

## Output

Structured `TASK_WA_*.md` files in `Needs_Action/` with:

```yaml
type: message
priority: medium | high
status: pending
created: <ISO 8601>
source: whatsapp_watcher.py
whatsapp_contact: "<primary contact>"
whatsapp_chat: "<chat/group name>"
message_count: <number>
```

## Execution Steps

1. **Launch browser** — Start persistent Chromium context using saved session.
2. **Navigate** — Go to `web.whatsapp.com`.
3. **Check login** — Verify session is active (side panel visible). If expired, log error and return.
4. **Find unread** — Locate all chats with unread message badges.
5. **Extract messages** — For each unread chat: open conversation, scrape messages (sender, timestamp, text).
6. **Deduplicate** — SHA-256 hash of `sender|timestamp|text`; skip messages already in `.whatsapp_registry.json`.
7. **Build task** — Generate structured markdown task with conversation preview (last 10 messages).
8. **Write** — Atomic write of `TASK_WA_*.md` to `Needs_Action/`.
9. **Register** — Update `.whatsapp_registry.json` to prevent reprocessing.
10. **Cleanup** — Close browser gracefully.
11. **Log** — Record all events to `watcher.log`.

## Configuration

In `config.json`:

```json
{
  "whatsapp": {
    "watch_dir": "Inbox/whatsapp",
    "max_messages_per_task": 50,
    "session_path": "~/.whatsapp_session",
    "headless": true,
    "mode": "web"
  },
  "watchers": {
    "whatsapp_enabled": true
  }
}
```

- `session_path`: Directory for persistent browser state (outside vault for security)
- `headless`: `true` for automated runs, forced `false` during `--setup`
- `mode`: `"web"` for Playwright-based WhatsApp Web automation

## Side Effects

- Creates task files in `Needs_Action/`.
- Updates `.whatsapp_registry.json` registry file.
- Appends to `watcher.log`.
- Reads from `web.whatsapp.com` (outbound HTTPS connection).
- Stores browser session in `~/.whatsapp_session`.

## Constraints

- Operates only within the vault root directory (except session storage).
- Does not send WhatsApp messages — read-only monitoring.
- Session expires after ~14 days; requires re-running `--setup`.
- Circuit breaker in `watcher_manager.py`: 3 consecutive failures stops the watcher thread.
- Multiple fallback CSS selectors per element for resilience against WhatsApp Web DOM changes.

## Setup

```bash
# Install Playwright (one-time)
pip install playwright
playwright install chromium

# WSL2 may need system dependencies:
sudo npx playwright install-deps chromium

# First-time login — scan QR code in browser window
python whatsapp_watcher.py --setup
```

## Usage

```bash
# Single scan
python whatsapp_watcher.py --once

# Continuous polling
python whatsapp_watcher.py

# Via watcher manager (recommended)
python watcher_manager.py
```

## Session Expiry

WhatsApp Web sessions expire after approximately 14 days of inactivity. When this happens:

1. The watcher logs: `ERROR: WhatsApp session expired`
2. The circuit breaker in `watcher_manager.py` stops the thread after 3 failures
3. Re-run `python whatsapp_watcher.py --setup` to scan a new QR code
