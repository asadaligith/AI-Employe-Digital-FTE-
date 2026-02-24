# Skill: generate-plan-md

## Tier
Silver

## Purpose

Convert an analyzed task into a structured, executable `Plan.md` file. This skill bridges the gap between task analysis and task execution by producing a step-by-step plan with clear objectives, ordered actions, and approval gates.

## Trigger

After a task has been analyzed (typically after `analyze-needs-action` has run). Invoked when a pending task requires a structured execution plan before processing.

## Input

```json
{
  "task_id": "string",
  "task_summary": "string",
  "task_type": "string"
}
```

| Field          | Type     | Description                                                              |
|----------------|----------|--------------------------------------------------------------------------|
| `task_id`      | `string` | Unique task identifier (e.g., `NA-1` from analyze output)               |
| `task_summary` | `string` | One-line summary of what the task requires                               |
| `task_type`    | `string` | Classified type: `email`, `message`, `file`, `finance`, or `general`    |

## Output

```json
{
  "plan_path": "Plans/PLAN_<task_id>_<timestamp>.md",
  "status": "created"
}
```

## Execution Steps

1. **Validate input** — Confirm `task_id`, `task_summary`, and `task_type` are present and non-empty. If any field is missing, fail with a logged alert.
2. **Define objective** — Write a clear, single-sentence objective derived from `task_summary`.
3. **Break into steps** — Decompose the objective into ordered, actionable steps. Each step must be:
   - Concrete (no vague language like "handle" or "process")
   - Independently verifiable (can confirm done/not done)
   - Scoped to a single action
4. **Mark approval requirements** — For each step, determine if it requires approval before execution:
   - `auto` — can be executed autonomously (default for Bronze Tier)
   - `review` — requires human review before proceeding (used when actions are irreversible or external-facing)
5. **Assign priority and estimated complexity** — Carry forward the task priority and tag complexity as `simple`, `moderate`, or `complex`.
6. **Generate Plan.md file** — Assemble the plan using the format below and save to `Plans/`.
7. **Return output** — Return the plan file path and `"status": "created"`.

## Plan.md Format

```markdown
---
task_id: <task_id>
task_type: <task_type>
priority: <priority>
complexity: <simple|moderate|complex>
status: pending
created: <ISO 8601 UTC timestamp>
---

# Plan: <objective>

## Objective
<Single-sentence objective>

## Context
- **Task ID**: <task_id>
- **Type**: <task_type>
- **Summary**: <task_summary>

## Steps

- [ ] **Step 1**: <action description> `[auto]`
- [ ] **Step 2**: <action description> `[auto]`
- [ ] **Step 3**: <action description> `[review]`

## Approval Gates
- <List any steps marked `[review]` and why they require approval>

## Completion Criteria
- <What must be true for this plan to be considered fully executed>
```

## Side Effects

- Creates a new `Plan.md` file in the `Plans/` directory.
- Creates the `Plans/` directory if it does not exist.

## Constraints

- Operates only within the vault root directory.
- Does not modify the original task file in `Needs_Action/` or `Done/`.
- Does not execute any plan steps — this skill only generates the plan.
- Follows all policies defined in `Company_Handbook.md`.
- Plan filenames use the pattern: `PLAN_<task_id>_<YYYYMMDD_HHMMSS>.md`.

## Failure Conditions

- Missing or empty `task_id`, `task_summary`, or `task_type` — log alert in `Dashboard.md` and do not create a plan file.
- Unable to write to `Plans/` directory — log alert in `Dashboard.md`.

## Example Usage

**Input**:
```json
{
  "task_id": "NA-1",
  "task_summary": "Forward from client regarding Q1 deliverables",
  "task_type": "email"
}
```

**Generated file**: `Plans/PLAN_NA-1_20260224_120000.md`

```markdown
---
task_id: NA-1
task_type: email
priority: medium
complexity: simple
status: pending
created: 2026-02-24T12:00:00Z
---

# Plan: Process client email regarding Q1 deliverables

## Objective
Extract action items from client email about Q1 deliverables and prepare a structured response.

## Steps

- [ ] **Step 1**: Read and parse the source email content `[auto]`
- [ ] **Step 2**: Extract key requests and deadlines `[auto]`
- [ ] **Step 3**: Draft response summary for review `[review]`

## Approval Gates
- Step 3 requires review: outbound client communication must be verified before sending.

## Completion Criteria
- All action items extracted and documented
- Response draft saved to task result
```

## Invocation

Use this skill after `analyze-needs-action` has produced a task list. Call once per task that requires a structured execution plan. Integrates into the Silver Tier processing pipeline between analysis and execution.
