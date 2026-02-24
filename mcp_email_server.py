#!/usr/bin/env python3
"""
mcp_email_server.py — Silver Tier MCP Email Server

A Model Context Protocol (MCP) server that provides email-sending capability
via SMTP. Enforces mandatory approval checks before any email is sent.

This server exposes a single tool: `send_email`

Protocol: MCP over stdio (JSON-RPC 2.0)
Transport: stdin/stdout

Usage:
    python mcp_email_server.py

Configure in .claude/settings.json:
{
  "mcpServers": {
    "email": {
      "command": "python",
      "args": ["mcp_email_server.py"],
      "cwd": "<vault_path>"
    }
  }
}
"""

import os
import sys
import json
import smtplib
import re
import tempfile
import shutil
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR = SCRIPT_DIR

CONFIG_FILE = os.path.join(VAULT_DIR, "config.json")
LOGS_DIR = os.path.join(VAULT_DIR, "Logs")
DASHBOARD_FILE = os.path.join(VAULT_DIR, "Dashboard.md")

# Import approval gate
sys.path.insert(0, VAULT_DIR)
try:
    from approval_gate import check_approval, mark_approval_executed
except ImportError:
    def check_approval(action_type, target):
        return {"approved": False, "reason": "approval_gate module not found"}
    def mark_approval_executed(path):
        return False


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_file() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def load_config() -> dict:
    if not os.path.isfile(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def log_email_action(recipient: str, subject: str, body: str,
                     status: str, approval_file: str,
                     message_id: str = "", error: str = "") -> str:
    """Create a log file in Logs/ for the email action. Returns log path."""
    os.makedirs(LOGS_DIR, exist_ok=True)
    fname = f"EMAIL_{now_file()}.md"
    fpath = os.path.join(LOGS_DIR, fname)

    content = (
        "---\n"
        "type: email_log\n"
        "action: send_email\n"
        f"recipient: {recipient}\n"
        f"subject: \"{subject}\"\n"
        f"status: {status}\n"
        f"approval_file: {approval_file}\n"
        f"timestamp: {now_iso()}\n"
        "---\n"
        "\n"
        "## Email Details\n"
        f"- **To**: {recipient}\n"
        f"- **Subject**: {subject}\n"
        f"- **MCP Response**: {message_id or error or 'N/A'}\n"
        "\n"
        "## Body\n"
        f"{body}\n"
    )

    try:
        with open(fpath, "w", encoding="utf-8") as fh:
            fh.write(content)
    except OSError:
        pass

    return f"Logs/{fname}"


def update_dashboard(message: str) -> None:
    if not os.path.isfile(DASHBOARD_FILE):
        return
    ts = now_iso()
    entry = f"- {ts} : {message}\n"
    try:
        with open(DASHBOARD_FILE, "r", encoding="utf-8") as fh:
            content = fh.read()
        content = content.replace("## Recent Activity\n", f"## Recent Activity\n{entry}", 1)
        with open(DASHBOARD_FILE, "w", encoding="utf-8") as fh:
            fh.write(content)
    except OSError:
        pass


def send_email_smtp(recipient: str, subject: str, body: str,
                    attachment_path: str = None) -> dict:
    """Actually send an email via SMTP. Returns {success, message_id, error}."""
    config = load_config()
    smtp_cfg = config.get("smtp", {})

    server = smtp_cfg.get("server", "smtp.gmail.com")
    port = smtp_cfg.get("port", 587)
    email_addr = smtp_cfg.get("email", "")
    password = smtp_cfg.get("app_password", "")
    from_name = smtp_cfg.get("from_name", "AI Employee")

    if not email_addr or not password:
        return {"success": False, "message_id": None,
                "error": "SMTP credentials not configured in config.json"}

    # Build message
    if attachment_path:
        msg = MIMEMultipart()
        msg.attach(MIMEText(body, "plain"))

        # Validate attachment is within vault
        abs_attach = os.path.abspath(os.path.join(VAULT_DIR, attachment_path))
        if not abs_attach.startswith(os.path.abspath(VAULT_DIR)):
            return {"success": False, "message_id": None,
                    "error": "Attachment path outside vault boundary"}
        if not os.path.isfile(abs_attach):
            return {"success": False, "message_id": None,
                    "error": f"Attachment not found: {attachment_path}"}
        if os.path.getsize(abs_attach) > 10 * 1024 * 1024:
            return {"success": False, "message_id": None,
                    "error": "Attachment exceeds 10MB limit"}

        with open(abs_attach, "rb") as af:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(af.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename={os.path.basename(abs_attach)}"
        )
        msg.attach(part)
    else:
        msg = MIMEText(body, "plain")

    msg["From"] = f"{from_name} <{email_addr}>"
    msg["To"] = recipient
    msg["Subject"] = subject

    try:
        with smtplib.SMTP(server, port) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(email_addr, password)
            smtp.send_message(msg)
        return {"success": True, "message_id": f"sent-{now_file()}", "error": None}
    except Exception as exc:
        return {"success": False, "message_id": None, "error": str(exc)}


def handle_send_email(params: dict) -> dict:
    """Handle the send_email MCP tool call with full approval enforcement."""
    recipient = params.get("recipient", "")
    subject = params.get("subject", "")
    body = params.get("body", "")
    attachment = params.get("attachment_path")

    # Validate required fields
    if not recipient:
        return {"status": "failed", "error": "missing recipient"}
    if not subject:
        return {"status": "failed", "error": "missing subject"}
    if not body:
        return {"status": "failed", "error": "missing body"}

    # Basic email format check
    if not re.match(r"[^@]+@[^@]+\.[^@]+", recipient):
        return {"status": "failed", "error": "invalid email format"}

    # MANDATORY: Check approval
    approval = check_approval("send_email", recipient)
    if not approval.get("approved"):
        reason = approval.get("reason", "no valid approval")
        log_path = log_email_action(
            recipient, subject, body, "blocked",
            "none", error=f"No approval: {reason}"
        )
        update_dashboard(
            f"BLOCKED email to {recipient} — {reason}. Log: {log_path}"
        )
        return {
            "status": "failed",
            "error": f"no_valid_approval: {reason}",
            "logged_at": log_path
        }

    approval_file = approval.get("file", "")

    # Send the email
    result = send_email_smtp(recipient, subject, body, attachment)

    if result["success"]:
        log_path = log_email_action(
            recipient, subject, body, "success",
            approval_file, message_id=result["message_id"]
        )
        mark_approval_executed(approval_file)
        update_dashboard(
            f"Sent email to {recipient} — subject: \"{subject}\". "
            f"Approval: {approval_file}. Log: {log_path}"
        )
        return {
            "status": "success",
            "message_id": result["message_id"],
            "logged_at": log_path
        }
    else:
        log_path = log_email_action(
            recipient, subject, body, "failed",
            approval_file, error=result["error"]
        )
        update_dashboard(
            f"FAILED to send email to {recipient} — {result['error']}. "
            f"Approval: {approval_file}. Log: {log_path}"
        )
        return {
            "status": "failed",
            "error": result["error"],
            "logged_at": log_path
        }


# ---------------------------------------------------------------------------
# MCP Protocol Handler (JSON-RPC 2.0 over stdio)
# ---------------------------------------------------------------------------

MCP_SERVER_INFO = {
    "name": "vault-email",
    "version": "1.0.0",
}

MCP_TOOLS = [
    {
        "name": "send_email",
        "description": (
            "Send an email via SMTP. REQUIRES a valid, non-expired approval file "
            "in Pending_Approval/ with status: approved. Will refuse to send without approval."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "recipient": {
                    "type": "string",
                    "description": "Email address of the recipient"
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject line"
                },
                "body": {
                    "type": "string",
                    "description": "Email body content (plain text)"
                },
                "attachment_path": {
                    "type": "string",
                    "description": "Vault-relative path to attachment file (optional)"
                }
            },
            "required": ["recipient", "subject", "body"]
        }
    }
]


def handle_mcp_request(request: dict) -> dict:
    """Process a single MCP JSON-RPC request and return a response."""
    method = request.get("method", "")
    req_id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": MCP_SERVER_INFO,
            }
        }

    elif method == "notifications/initialized":
        return None  # No response for notifications

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": MCP_TOOLS}
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        if tool_name == "send_email":
            result = handle_send_email(tool_args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {"type": "text", "text": json.dumps(result, indent=2)}
                    ]
                }
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
            }

    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        }


def main():
    """MCP server main loop — read JSON-RPC from stdin, write to stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"}
            }
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
            continue

        response = handle_mcp_request(request)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
