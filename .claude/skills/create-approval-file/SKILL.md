# Skill: create-approval-file

## Tier
Silver

## Purpose

Create a structured human approval request file before executing any sensitive, external-facing, or risky action. This skill acts as a safety gate — no high-risk action proceeds without explicit human sign-off recorded in the vault.

## Trigger

Before executing any action that is external-facing, irreversible, or classified as medium/high risk. Typically invoked by other skills (e.g., `generate-linkedin-business-post`, `generate-plan-md`) when a step is marked `[review]`, or when a task involves outbound communication, financial operations, or data modification.

## Input

```json
{
  "action_type": "string",
  "description": "string",
  "target": "string",
  "risk_level": "low | medium | high"
}
```

| Field         | Type     | Description                                                                    |
|---------------|----------|--------------------------------------------------------------------------------|
| `action_type` | `string` | Category of action (e.g., `send_email`, `publish_post`, `delete_file`, `payment`) |
| `description` | `string` | Clear explanation of what will happen if approved                              |
| `target`      | `string` | Who or what is affected (e.g., "client@example.com", "LinkedIn company page") |
| `risk_level`  | `string` | Risk classification: `low`, `medium`, or `high`                               |

## Output

```json
{
  "approval_file": "Pending_Approval/APPROVAL_<YYYYMMDD_HHMMSS>.md",
  "status": "pending"
}
```

## Execution Steps

1. **Validate input** — Confirm all four fields (`action_type`, `description`, `target`, `risk_level`) are present and non-empty. If any field is missing, fail with a logged alert in `Dashboard.md`.

2. **Normalize risk level** — If `risk_level` is not one of `low`, `medium`, `high`, default to `high` (fail-safe).

3. **Determine urgency window** based on risk level:

   | Risk Level | Urgency         | Auto-Expire           |
   |------------|------------------|-----------------------|
   | `low`      | Standard         | 72 hours              |
   | `medium`   | Elevated         | 48 hours              |
   | `high`     | Immediate review | 24 hours              |

4. **Generate approval file** — Assemble a structured markdown file with full context for the human reviewer.

5. **Save to `Pending_Approval/`** — Write the file. Create the directory if it does not exist.

6. **Log to Dashboard** — Add a timestamped entry under `## Recent Activity` noting the approval request was created, and add an alert under `## Alerts` for `medium` and `high` risk items.

7. **Return output** — Return the approval file path and `"status": "pending"`.

## Approval File Format

```markdown
---
type: approval_request
action_type: <action_type>
risk_level: <low|medium|high>
status: pending
created: <ISO 8601 UTC timestamp>
expires: <ISO 8601 UTC timestamp based on urgency window>
---

# Approval Request

## Action
**Type**: <action_type>
**Risk Level**: <risk_level>

## Description
<description — what will happen if this is approved>

## Target
<target — who or what is affected>

## Context
- **Requested by**: autonomous agent (Silver Tier)
- **Created**: <timestamp>
- **Expires**: <timestamp>
- **Source task**: <task_id if available, otherwise "direct invocation">

## Risk Assessment
<Brief risk summary based on risk_level>:
- `low`: Routine action with minimal impact. Auto-expires in 72h.
- `medium`: Action affects external systems or contacts. Requires review within 48h.
- `high`: Irreversible or high-impact action. Requires immediate review within 24h.

## Decision

> **To approve**: Change `status: pending` to `status: approved` in frontmatter.
> **To reject**: Change `status: pending` to `status: rejected` in frontmatter.
> **To request changes**: Add notes under `## Reviewer Notes` and set `status: revision_requested`.

- [ ] Reviewed by human operator
- [ ] Decision recorded

## Reviewer Notes
<space for human reviewer comments>
```

## Side Effects

- Creates an approval request file in `Pending_Approval/`.
- Creates the `Pending_Approval/` directory if it does not exist.
- Adds a `## Recent Activity` entry in `Dashboard.md`.
- Adds an `## Alerts` entry in `Dashboard.md` for `medium` and `high` risk requests.

## Constraints

- Operates only within the vault root directory.
- Does **not** execute the requested action — this skill only creates the approval request.
- The agent must **never** proceed with the action until the approval file's frontmatter `status` is changed to `approved` by a human.
- Expired approval requests (past their `expires` timestamp) must be treated as `rejected`.
- Follows all policies defined in `Company_Handbook.md`.
- Approval filenames use the pattern: `APPROVAL_<YYYYMMDD_HHMMSS>.md`.

## Failure Conditions

- Missing or empty `action_type` — log alert in `Dashboard.md`, do not create file.
- Missing or empty `description` — log alert in `Dashboard.md`, do not create file.
- Missing or empty `target` — log alert in `Dashboard.md`, do not create file.
- Missing or empty `risk_level` — default to `high` and proceed (fail-safe, not fail-open).

## Example Usage

**Input**:
```json
{
  "action_type": "send_email",
  "description": "Send invoice #2024-0892 for $4,500 to client for Q1 consulting services",
  "target": "billing@clientcorp.com",
  "risk_level": "high"
}
```

**Generated file**: `Pending_Approval/APPROVAL_20260224_150000.md`

**Dashboard alert**:
```
- 2026-02-24T15:00:00Z : APPROVAL REQUIRED (high) — send_email to billing@clientcorp.com. Review within 24h. File: APPROVAL_20260224_150000.md
```

## Invocation

Use this skill as a safety gate before any sensitive action. Other skills should call this when:
- A plan step is marked `[review]` in `generate-plan-md`
- A LinkedIn post is ready for publishing in `generate-linkedin-business-post`
- A task involves outbound communication, financial transactions, or irreversible changes
- Any action crosses the vault boundary or affects external systems
