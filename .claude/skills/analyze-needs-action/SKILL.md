# Skill: analyze-needs-action

## Tier
Silver

## Purpose

Scan the `Needs_Action/` folder, read all pending markdown task files, extract structured metadata, classify each task by type, and output a JSON task list for downstream processing.

## Trigger

Invoked before task processing to produce a structured inventory of pending work. Can be called standalone for reporting or as a prerequisite step in a higher-order execution loop.

## Execution Steps

1. List all `.md` files in `Needs_Action/` (exclude hidden files and `.gitkeep`).
2. If no task files exist, output an empty JSON array `[]` and stop.
3. For each `.md` file found:
   a. Read the full file content.
   b. Parse YAML frontmatter and extract all metadata fields (`type`, `priority`, `status`, `created`, `source`, and any additional fields).
   c. Parse the `## Task Description` section and generate a one-line summary (first sentence or first 120 characters, whichever is shorter).
   d. Classify the task into one of the following categories based on frontmatter `type` and task description content:
      - `email` — task originates from or relates to email content
      - `message` — task originates from or relates to a chat message, notification, or communication
      - `file` — task originates from a file event (new file detected, file processing)
      - `finance` — task relates to invoices, payments, budgets, or financial data
      - `general` — fallback category if none of the above match
   e. Assign a unique `id` using the pattern: `NA-<index>` where `<index>` is the 1-based position in the file list sorted alphabetically by filename.
4. Assemble the output as a JSON array sorted by `priority` (high → medium → low), then by `created` (oldest first).

## Classification Rules

| Category   | Match Criteria                                                                                         |
|------------|--------------------------------------------------------------------------------------------------------|
| `email`    | Frontmatter `type` contains `email` OR `source` contains `email` OR description mentions email/inbox   |
| `message`  | Frontmatter `type` contains `message`, `chat`, `notification`, or `alert`                              |
| `file`     | Frontmatter `type` contains `file` OR `source` is `watcher.py` OR description mentions file detection  |
| `finance`  | Frontmatter `type` contains `finance`, `invoice`, `payment`, `budget` OR description matches these     |
| `general`  | No other category matched                                                                              |

## Output Format

```json
[
  {
    "id": "NA-1",
    "type": "file",
    "priority": "high",
    "summary": "New file detected in Inbox requiring processing",
    "source_file": "TASK_20260224_091500.md"
  },
  {
    "id": "NA-2",
    "type": "email",
    "priority": "medium",
    "summary": "Forward from client regarding Q1 deliverables",
    "source_file": "TASK_20260224_100000.md"
  }
]
```

### Field Definitions

| Field         | Type     | Description                                                        |
|---------------|----------|--------------------------------------------------------------------|
| `id`          | `string` | Unique identifier in `NA-<index>` format                          |
| `type`        | `string` | Classified category: `email`, `message`, `file`, `finance`, `general` |
| `priority`    | `string` | Priority from frontmatter: `high`, `medium`, or `low`             |
| `summary`     | `string` | One-line summary extracted from `## Task Description`              |
| `source_file` | `string` | Original filename in `Needs_Action/`                               |

## Constraints

- Read-only operation. This skill does not modify, move, or delete any files.
- Operates only within the vault root directory. Never access files outside it.
- If a file cannot be parsed (missing frontmatter, corrupt markdown), skip it and include an entry in the output with `"type": "general"` and `"summary": "PARSE ERROR — unable to extract metadata"`.
- Output must be valid JSON. No trailing commas, no comments.
- Follow all policies defined in `Company_Handbook.md`.

## Invocation

Use this skill to get a structured snapshot of all pending work before processing. Useful for:
- Pre-execution analysis in autonomous loops
- Reporting and dashboard enrichment
- Prioritization decisions in multi-task queues
- Integration with higher-tier agent orchestration
