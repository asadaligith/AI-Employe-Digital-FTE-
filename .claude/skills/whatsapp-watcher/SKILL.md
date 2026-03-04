# Skill: whatsapp-watcher

## Tier
Silver

## Purpose

Monitor `Inbox/whatsapp/` for exported WhatsApp chat `.txt` files, parse conversations into structured messages, and create task files in `Needs_Action/` for agent processing.

## Trigger

Activated as a perception-layer watcher. Runs continuously via `watcher_manager.py` or as a standalone script. Detects new WhatsApp chat export files dropped into the watch directory.

## Input

WhatsApp chat export `.txt` files in `Inbox/whatsapp/`. Supported formats:

```
[DD/MM/YYYY, HH:MM:SS] Contact Name: Message text
DD/MM/YYYY, HH:MM - Contact Name: Message text
[MM/DD/YY, HH:MM:SS AM/PM] Contact Name: Message text
```

## Output

Structured `TASK_WA_*.md` files in `Needs_Action/` with:

```yaml
type: message
priority: medium | high
status: pending
created: <ISO 8601>
source: whatsapp_watcher.py
whatsapp_contact: "<primary contact>"
whatsapp_file: "<source filename>"
message_count: <number>
```

## Execution Steps

1. **Scan** — List `.txt` files in `Inbox/whatsapp/` (skip hidden files).
2. **Deduplicate** — Compute SHA-256 hash of each file; skip files already in `.whatsapp_registry.json`.
3. **Parse** — Extract messages from WhatsApp export format (sender, timestamp, text).
4. **Classify** — Detect priority based on urgent keywords (urgent, asap, emergency, critical, etc.).
5. **Build task** — Generate structured markdown task with conversation preview (last 10 messages).
6. **Write** — Atomic write of `TASK_WA_*.md` to `Needs_Action/`.
7. **Register** — Update `.whatsapp_registry.json` to prevent reprocessing.
8. **Log** — Record all events to `watcher.log`.

## Configuration

In `config.json`:

```json
{
  "whatsapp": {
    "watch_dir": "Inbox/whatsapp",
    "max_messages_per_task": 50
  },
  "watchers": {
    "whatsapp_enabled": true
  }
}
```

## Side Effects

- Creates task files in `Needs_Action/`.
- Updates `.whatsapp_registry.json` registry file.
- Appends to `watcher.log`.

## Constraints

- Operates only within the vault root directory.
- Does not send messages or interact with WhatsApp externally.
- Processes exported chat files only (file-based perception).
- Registry prevents duplicate processing of the same file.
- Maximum messages per task configurable (default 50, uses most recent).

## Usage

```bash
# Standalone — single scan
python whatsapp_watcher.py --once

# Standalone — continuous polling
python whatsapp_watcher.py

# Via watcher manager (recommended)
python watcher_manager.py
```

## How to Export WhatsApp Chats

1. Open WhatsApp on your phone.
2. Open the chat you want to export.
3. Tap the three-dot menu (Android) or contact name (iOS).
4. Select **Export Chat** > **Without Media**.
5. Save/transfer the `.txt` file to `Inbox/whatsapp/` in the vault.
