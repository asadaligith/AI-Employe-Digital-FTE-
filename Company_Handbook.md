# Company Handbook

## Communication Rules
- All communication occurs through vault files only.
- No conversational output outside of structured markdown.
- Alerts and status updates are logged in Dashboard.md.

## Risk Thresholds
- High priority tasks must be processed first.
- If a task cannot be completed, log a blocking alert in Dashboard.md.

## Approval Requirements
- Bronze Tier operates autonomously with no human approval required.
- Silver Tier requires human approval for all external-facing actions:
  - Outbound email (always requires approval)
  - LinkedIn posts (always requires approval)
  - Financial transactions (always requires approval)
  - Any action that crosses the vault boundary
- Approval workflow:
  - Agent creates approval file in `Pending_Approval/`
  - Human reviews and sets `status: approved` or `status: rejected`
  - Expired approvals (past `expires` timestamp) are treated as rejected
  - One approval = one action. No bulk approvals.
- Risk levels and expiry windows:
  - Low risk: 72 hours
  - Medium risk: 48 hours
  - High risk: 24 hours (immediate review required)

## External Action Policy
- No external action may execute without a valid, non-expired approval file.
- All external actions are logged in `Logs/` with full audit trail.
- MCP server calls require both approval AND valid configuration.
- Failed external actions are logged and alerted in Dashboard.md.

## Task Handling Policy
- Tasks must follow the mandatory schema (frontmatter metadata + checklist).
- Files missing metadata are rejected and logged as alerts.
- Tasks are processed in priority order: high → medium → low.
- Completed tasks are moved to Done/. Never deleted.
- No task may be skipped.
