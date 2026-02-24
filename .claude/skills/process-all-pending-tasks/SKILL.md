# Skill: process-all-pending-tasks

## Tier
Silver

## Purpose

Execute the full Silver Tier task processing pipeline. This is the top-level orchestration skill that coordinates all other Silver skills into a single deterministic execution cycle — from analysis through planning, skill routing, execution, and archival.

## Trigger

Scheduled execution (e.g., daily automated run) or manual trigger. This skill replaces the Bronze `bronze-autonomous-loop` as the primary entry point at Silver Tier.

## Input

No input required. The skill reads vault state directly.

## Output

```json
{
  "processed_tasks": 0,
  "approved_tasks": 0,
  "pending_approval": 0,
  "failed_tasks": 0,
  "status": "complete"
}
```

## Execution Steps

### Phase 1: Initialize

1. **Load policies** — Read `Company_Handbook.md` to load current operational rules.
2. **Validate vault structure** — Confirm required directories exist:
   - `Inbox/`
   - `Needs_Action/`
   - `Done/`
   - `Backups/`
   - Create `Plans/`, `Pending_Approval/`, `Logs/` if they do not exist (Silver Tier directories).
3. **If vault structure is invalid** (missing `Needs_Action/`, `Done/`, or `Company_Handbook.md`), log alert in `Dashboard.md` and halt.

### Phase 2: Analyze

4. **Invoke `analyze-needs-action`** — Scan `Needs_Action/` for all pending `.md` files.
5. **If no tasks found** — Update `Dashboard.md` to record idle check with current timestamp, return `{ "processed_tasks": 0, "status": "complete" }`, and stop.
6. **Receive task list** — Structured JSON array sorted by priority then timestamp.

### Phase 3: Plan

7. **For each task** in the analyzed list (priority order):
   a. **Invoke `validate-task-schema`** — Validate frontmatter and required sections.
      - On failure: log alert in `Dashboard.md`, skip task, increment `failed_tasks`.
   b. **Invoke `generate-plan-md`** — Create an execution plan with steps and approval gates.
   c. **Record plan path** for execution in Phase 4.

### Phase 4: Route and Execute

8. **For each planned task**, read its `Plan.md` and process each step:

   a. **Check for approval gates** — If any step is marked `[review]`:
      - **Invoke `create-approval-file`** for the gated action.
      - **Check if approval already exists** (from a previous run):
        - `status: approved` → proceed with execution.
        - `status: pending` → skip this task (leave for next run), increment `pending_approval`.
        - `status: rejected` → mark task as blocked, log alert, skip.
        - `status: revision_requested` → skip this task, log for review.
      - Tasks with pending approvals are **not** moved to `Done/`.

   b. **Route to skill by task type**:

      | Task Type   | Skill Invoked                        | Requires Approval |
      |-------------|--------------------------------------|-------------------|
      | `email`     | `send-email-mcp`                     | Yes (always)      |
      | `message`   | Process inline (write result)        | If external       |
      | `file`      | Process inline (Bronze-style)        | No                |
      | `finance`   | Process inline (write result)        | Yes (always)      |
      | `general`   | Process inline (Bronze-style)        | No                |
      | Marketing   | `generate-linkedin-business-post`    | Yes (always)      |

   c. **Execute non-gated steps** — For steps marked `[auto]`:
      - Read task description and required outcome.
      - Reason through the objective and produce a concrete result.
      - Write the result into the task file under `## Result`.

   d. **Mark completed steps** — Check off `[x]` for each executed step in the plan.

### Phase 5: Complete

9. **For each fully executed task** (all steps done, all approvals cleared):
   a. Mark all `## Processing Checklist` items as `[x]` in the task file.
   b. Add `## Completion Notes` with summary and UTC timestamp.
   c. Change frontmatter `status: pending` to `status: completed`.
   d. Move task file from `Needs_Action/` to `Done/`.
   e. Update plan file `status` to `completed`.

### Phase 6: Update Dashboard

10. **Invoke `update-dashboard`** with final state:
    - Count remaining files in `Needs_Action/` → pending tasks.
    - Count files completed today in `Done/` → completed today.
    - Count files in `Pending_Approval/` with `status: pending` → awaiting approval.
    - Set `Last Execution` to current UTC timestamp.
    - Add `## Recent Activity` entry summarizing the full run.
    - Update or clear `## Alerts` as appropriate.

### Phase 7: Return

11. **Return output**:
```json
{
  "processed_tasks": "<number fully completed>",
  "approved_tasks": "<number that had approvals and were executed>",
  "pending_approval": "<number waiting on human approval>",
  "failed_tasks": "<number that failed validation or processing>",
  "status": "complete"
}
```

## Pipeline Flow

```
┌─────────────────────────────────────────────────────────┐
│                  process-all-pending-tasks               │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Phase 1: Initialize                                    │
│    └─ Load policies, validate vault                     │
│                                                         │
│  Phase 2: Analyze                                       │
│    └─ analyze-needs-action                              │
│         └─ Returns JSON task list                       │
│                                                         │
│  Phase 3: Plan                                          │
│    ├─ validate-task-schema (per task)                   │
│    └─ generate-plan-md (per task)                       │
│         └─ Returns Plan.md with steps + gates           │
│                                                         │
│  Phase 4: Route & Execute                               │
│    ├─ [review] steps → create-approval-file             │
│    │    └─ Wait for human approval (or skip)            │
│    ├─ email tasks → send-email-mcp                      │
│    ├─ marketing tasks → generate-linkedin-business-post │
│    └─ other tasks → inline processing                   │
│                                                         │
│  Phase 5: Complete                                      │
│    └─ Write results, move to Done/                      │
│                                                         │
│  Phase 6: Update Dashboard                              │
│    └─ update-dashboard                                  │
│                                                         │
│  Phase 7: Return summary                                │
└─────────────────────────────────────────────────────────┘
```

## Side Effects

- Creates `Plans/`, `Pending_Approval/`, `Logs/` directories if missing.
- Creates plan files in `Plans/`.
- Creates approval files in `Pending_Approval/` for gated actions.
- Creates log files in `Logs/` for external actions.
- Modifies task files (adds results, marks checklists, updates status).
- Moves completed tasks from `Needs_Action/` to `Done/`.
- Updates `Dashboard.md` with activity, counts, and alerts.

## Constraints

- Operates only within the vault root directory.
- Runs once per invocation — does not loop or poll.
- Does not modify `watcher.py`, `backup.sh`, or `Company_Handbook.md`.
- Does not delete any file from `Done/`.
- Does not skip any task — failed tasks are logged, not ignored.
- Tasks awaiting approval are left in `Needs_Action/` for the next run.
- Follows all policies defined in `Company_Handbook.md`.
- Idempotent: re-running with no tasks in `Needs_Action/` produces no side effects.

## Failure Conditions

| Condition                          | Behavior                                                  |
|------------------------------------|-----------------------------------------------------------|
| Vault structure missing            | Log alert in `Dashboard.md`, halt entire run              |
| `Company_Handbook.md` missing      | Log alert, halt — policies cannot be loaded               |
| Task fails schema validation       | Log alert, skip task, continue with remaining tasks       |
| Plan generation fails              | Log alert, skip task, continue                            |
| Approval pending                   | Skip task, leave in `Needs_Action/`, continue             |
| Approval rejected                  | Mark blocked, log alert, skip task, continue              |
| MCP server unavailable             | Log failure, skip email task, continue                    |
| Task processing error              | Log blocking alert, skip task, continue                   |

## Example Usage

**Daily automated run with 3 tasks**:

```
Input: (none)

Run summary:
- Scanned Needs_Action/: 3 tasks found
- Task NA-1 (file, high): processed inline → moved to Done/
- Task NA-2 (email, medium): plan created, approval requested → pending
- Task NA-3 (general, low): processed inline → moved to Done/

Output:
{
  "processed_tasks": 2,
  "approved_tasks": 0,
  "pending_approval": 1,
  "failed_tasks": 0,
  "status": "complete"
}
```

## Invocation

This is the primary Silver Tier entry point. Use for:
- Scheduled daily/hourly automated processing
- Manual trigger to flush all pending work
- End-to-end pipeline testing

Supersedes `bronze-autonomous-loop` at Silver Tier while maintaining backward compatibility with Bronze task schema and vault structure.
