# Skill: send-email-mcp

## Tier
Silver

## Purpose

Send an email via a configured MCP (Model Context Protocol) email server. This is the only skill authorized to perform outbound email — it enforces a mandatory approval check before any message leaves the vault.

## Trigger

After a human-approved email action exists in `Pending_Approval/`. Never invoked directly without a preceding `create-approval-file` approval gate.

## Input

```json
{
  "recipient": "string",
  "subject": "string",
  "body": "string",
  "attachment_path": "string | null"
}
```

| Field             | Type              | Required | Description                                                    |
|-------------------|-------------------|----------|----------------------------------------------------------------|
| `recipient`       | `string`          | Yes      | Email address of the recipient                                |
| `subject`         | `string`          | Yes      | Email subject line                                            |
| `body`            | `string`          | Yes      | Email body content (plain text)                               |
| `attachment_path` | `string` or `null`| No       | Vault-relative path to attachment file, or `null` if none     |

## Output

```json
{
  "status": "success | failed",
  "message_id": "string | null",
  "logged_at": "Logs/EMAIL_<YYYYMMDD_HHMMSS>.md"
}
```

## Execution Steps

1. **Validate input** — Confirm `recipient`, `subject`, and `body` are present and non-empty.
   - Validate `recipient` contains a basic email format (`*@*.*`).
   - If `attachment_path` is provided, confirm the file exists within the vault root.
   - On any validation failure, return `"status": "failed"` and log the error.

2. **Verify approval exists** — Scan `Pending_Approval/` for an approval file where:
   - `action_type` is `send_email`
   - `target` matches `recipient`
   - `status` is `approved` in frontmatter
   - `expires` timestamp has not passed
   - If no valid approval is found, **halt immediately**. Return `"status": "failed"` with reason `"no_valid_approval"`. Log alert in `Dashboard.md`.

3. **Validate attachment** (if provided):
   - Confirm the file path is within the vault boundary.
   - Confirm the file exists and is readable.
   - Reject files larger than 10MB.
   - On failure, return `"status": "failed"` and log the error.

4. **Call email MCP server** — Invoke the configured MCP email tool with:
   ```json
   {
     "to": "<recipient>",
     "subject": "<subject>",
     "body": "<body>",
     "attachments": ["<attachment_path>"] or []
   }
   ```
   - If the MCP server is unavailable or returns an error, return `"status": "failed"` with the error detail.

5. **Log the action** — Create a send log file in `Logs/`:
   ```markdown
   ---
   type: email_log
   action: send_email
   recipient: <recipient>
   subject: <subject>
   status: <success|failed>
   approval_file: <path to approval file>
   timestamp: <ISO 8601 UTC>
   ---

   ## Email Details
   - **To**: <recipient>
   - **Subject**: <subject>
   - **Attachment**: <attachment_path or "none">
   - **MCP Response**: <message_id or error>

   ## Body
   <email body content>
   ```

6. **Update approval file** — Change the approval file's frontmatter `status` from `approved` to `executed`.

7. **Update Dashboard** — Add a timestamped entry under `## Recent Activity`:
   - On success: `Sent email to <recipient> — subject: "<subject>". Approval: <approval_file>.`
   - On failure: `FAILED to send email to <recipient> — reason: <error>. Approval: <approval_file>.`

8. **Return output** — Return status, message ID (if available), and log file path.

## Safety Rules

- **Approval is mandatory**. This skill must **never** send an email without a valid, non-expired approval file with `status: approved`.
- **No bulk sends**. One approval = one email. Each send requires its own approval.
- **No vault escape**. Attachments must be within the vault root. Paths containing `..` are rejected.
- **No silent failures**. Every send attempt (success or failure) is logged in `Logs/` and `Dashboard.md`.
- **Expired approvals are rejected**. If the approval's `expires` timestamp has passed, treat it as unapproved.

## Side Effects

- Sends an external email via MCP server.
- Creates a log file in `Logs/` directory (creates directory if needed).
- Updates the approval file status to `executed`.
- Adds entries to `Dashboard.md` under `## Recent Activity`.
- On failure, adds an alert under `## Alerts` in `Dashboard.md`.

## Constraints

- Operates within the vault root for all file operations.
- Requires a configured and reachable MCP email server.
- Does not modify `watcher.py`, `backup.sh`, or `Company_Handbook.md`.
- Follows all policies defined in `Company_Handbook.md`.
- Log filenames use the pattern: `EMAIL_<YYYYMMDD_HHMMSS>.md`.

## Failure Conditions

| Condition                        | Behavior                                             |
|----------------------------------|------------------------------------------------------|
| Missing `recipient`              | Return failed, log alert                            |
| Missing `subject`                | Return failed, log alert                            |
| Missing `body`                   | Return failed, log alert                            |
| Invalid email format             | Return failed, log alert                            |
| No valid approval found          | Halt, return failed, log alert                      |
| Expired approval                 | Halt, return failed, log alert                      |
| Attachment not found             | Return failed, log alert                            |
| Attachment outside vault         | Return failed, log alert                            |
| Attachment exceeds 10MB          | Return failed, log alert                            |
| MCP server unavailable           | Return failed, log alert                            |
| MCP server returns error         | Return failed, log error detail                     |

## Example Usage

**Input**:
```json
{
  "recipient": "billing@clientcorp.com",
  "subject": "Invoice #2024-0892 — Q1 Consulting Services",
  "body": "Hi,\n\nPlease find attached the invoice for Q1 consulting services.\n\nAmount: $4,500\nDue date: March 15, 2026\n\nPlease let us know if you have any questions.\n\nBest regards",
  "attachment_path": "Documents/invoice-2024-0892.pdf"
}
```

**Prerequisite**: Approval file `Pending_Approval/APPROVAL_20260224_150000.md` exists with `status: approved`.

**On success**:
- Email sent via MCP
- Log created: `Logs/EMAIL_20260224_153000.md`
- Approval file updated to `status: executed`
- Dashboard updated: `Sent email to billing@clientcorp.com — subject: "Invoice #2024-0892". Approval: APPROVAL_20260224_150000.md`

## Invocation

Use this skill only after `create-approval-file` has generated an approval request and a human has set `status: approved`. This is the final execution step in the email pipeline:

```
analyze-needs-action → generate-plan-md → create-approval-file → [human approval] → send-email-mcp
```
