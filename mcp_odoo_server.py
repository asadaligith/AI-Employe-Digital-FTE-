#!/usr/bin/env python3
"""
mcp_odoo_server.py — Gold Tier MCP Server for Odoo Operations

A Model Context Protocol (MCP) server exposing Odoo ERP operations as tools.
Enforces mandatory approval checks for write operations.

Protocol: MCP over stdio (JSON-RPC 2.0)
Transport: stdin/stdout

Tools:
    - odoo_get_invoices(state, limit) — List invoices
    - odoo_get_payments(limit) — List payments
    - odoo_get_contacts(limit) — List contacts
    - odoo_create_invoice(partner_id, lines) — Create invoice (requires approval)
    - odoo_financial_summary() — Get financial overview

Usage:
    python mcp_odoo_server.py

Configure in .claude/settings.json:
{
  "mcpServers": {
    "vault-odoo": {
      "command": "python3",
      "args": ["mcp_odoo_server.py"],
      "cwd": "."
    }
  }
}
"""

import os
import sys
import json
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR = SCRIPT_DIR
LOGS_DIR = os.path.join(VAULT_DIR, "Logs")
DASHBOARD_FILE = os.path.join(VAULT_DIR, "Dashboard.md")

sys.path.insert(0, VAULT_DIR)

try:
    from approval_gate import check_approval, create_approval_file, mark_approval_executed
except ImportError:
    def check_approval(action_type, target):
        return {"approved": False, "reason": "approval_gate module not found"}
    def create_approval_file(**kwargs):
        return {"approval_file": None, "status": "failed", "error": "module not found"}
    def mark_approval_executed(path):
        return False

try:
    from action_logger import log_action
except ImportError:
    def log_action(*args, **kwargs):
        return {}

try:
    from odoo_client import OdooClient, OdooError
except ImportError:
    OdooClient = None
    OdooError = Exception


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def update_dashboard(message: str) -> None:
    if not os.path.isfile(DASHBOARD_FILE):
        return
    ts = now_iso()
    entry = f"- {ts} : {message}\n"
    try:
        with open(DASHBOARD_FILE, "r", encoding="utf-8") as fh:
            content = fh.read()
        content = content.replace("## Recent Activity\n",
                                  f"## Recent Activity\n{entry}", 1)
        with open(DASHBOARD_FILE, "w", encoding="utf-8") as fh:
            fh.write(content)
    except OSError:
        pass


def _get_client() -> "OdooClient":
    """Create and authenticate an Odoo client."""
    if OdooClient is None:
        raise OdooError("odoo_client module not available")
    client = OdooClient.from_config()
    client.authenticate()
    return client


# ---------------------------------------------------------------------------
# Tool Handlers
# ---------------------------------------------------------------------------

def handle_get_invoices(params: dict) -> dict:
    try:
        client = _get_client()
        state = params.get("state")
        limit = params.get("limit", 20)
        invoices = client.get_invoices(state=state, limit=limit)
        log_action("odoo_get_invoices", f"state={state}", "success",
                   metadata={"count": len(invoices)})
        return {"status": "success", "invoices": invoices, "count": len(invoices)}
    except Exception as exc:
        log_action("odoo_get_invoices", "odoo", "failure", error=str(exc))
        return {"status": "failed", "error": str(exc)}


def handle_get_payments(params: dict) -> dict:
    try:
        client = _get_client()
        limit = params.get("limit", 20)
        payments = client.get_payments(limit=limit)
        log_action("odoo_get_payments", "odoo", "success",
                   metadata={"count": len(payments)})
        return {"status": "success", "payments": payments, "count": len(payments)}
    except Exception as exc:
        log_action("odoo_get_payments", "odoo", "failure", error=str(exc))
        return {"status": "failed", "error": str(exc)}


def handle_get_contacts(params: dict) -> dict:
    try:
        client = _get_client()
        limit = params.get("limit", 50)
        contacts = client.get_contacts(limit=limit)
        log_action("odoo_get_contacts", "odoo", "success",
                   metadata={"count": len(contacts)})
        return {"status": "success", "contacts": contacts, "count": len(contacts)}
    except Exception as exc:
        log_action("odoo_get_contacts", "odoo", "failure", error=str(exc))
        return {"status": "failed", "error": str(exc)}


def handle_create_invoice(params: dict) -> dict:
    partner_id = params.get("partner_id")
    lines = params.get("lines", [])

    if not partner_id:
        return {"status": "failed", "error": "missing partner_id"}
    if not lines:
        return {"status": "failed", "error": "missing invoice lines"}

    # MANDATORY: Check approval
    target = f"partner:{partner_id}"
    approval = check_approval("odoo_create_invoice", target)
    if not approval.get("approved"):
        reason = approval.get("reason", "no valid approval")

        # Create approval request if none exists
        if "no matching" in reason:
            total = sum(
                l.get("price_unit", 0) * l.get("quantity", 1) for l in lines
            )
            create_approval_file(
                action_type="odoo_create_invoice",
                description=f"Create invoice for partner {partner_id}, "
                            f"{len(lines)} line(s), total ~{total:.2f}",
                target=target,
                risk_level="high",
                source_task="mcp_odoo_server",
            )

        log_action("odoo_create_invoice", target, "failure",
                   error=f"No approval: {reason}")
        update_dashboard(f"BLOCKED Odoo invoice creation — {reason}")
        return {"status": "failed", "error": f"no_valid_approval: {reason}"}

    try:
        client = _get_client()
        result = client.create_invoice(partner_id, lines)
        mark_approval_executed(approval.get("file", ""))
        log_action("odoo_create_invoice", target, "success",
                   metadata={"invoice_id": result["invoice_id"]})
        update_dashboard(
            f"Odoo invoice created: {result['name']} for partner {partner_id}"
        )
        return {"status": "success", **result}
    except Exception as exc:
        log_action("odoo_create_invoice", target, "failure", error=str(exc))
        return {"status": "failed", "error": str(exc)}


def handle_financial_summary(params: dict) -> dict:
    try:
        client = _get_client()
        summary = client.get_financial_summary()
        log_action("odoo_financial_summary", "odoo", "success")
        return {"status": "success", **summary}
    except Exception as exc:
        log_action("odoo_financial_summary", "odoo", "failure", error=str(exc))
        return {"status": "failed", "error": str(exc)}


# ---------------------------------------------------------------------------
# MCP Protocol (JSON-RPC 2.0 over stdio)
# ---------------------------------------------------------------------------

MCP_SERVER_INFO = {
    "name": "vault-odoo",
    "version": "1.0.0",
}

MCP_TOOLS = [
    {
        "name": "odoo_get_invoices",
        "description": "List invoices from Odoo ERP. Optionally filter by state.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "description": "Filter by state: draft, posted, cancel. Omit for all."
                },
                "limit": {
                    "type": "integer",
                    "description": "Max invoices to return (default 20)"
                },
            },
        },
    },
    {
        "name": "odoo_get_payments",
        "description": "List payments from Odoo ERP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max payments to return (default 20)"
                },
            },
        },
    },
    {
        "name": "odoo_get_contacts",
        "description": "List business contacts from Odoo ERP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max contacts to return (default 50)"
                },
            },
        },
    },
    {
        "name": "odoo_create_invoice",
        "description": (
            "Create a draft invoice in Odoo. REQUIRES approval. "
            "Will create an approval request if none exists."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "partner_id": {
                    "type": "integer",
                    "description": "Odoo partner (customer) ID"
                },
                "lines": {
                    "type": "array",
                    "description": "Invoice lines: [{product_id, quantity, price_unit, name}]",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "integer"},
                            "quantity": {"type": "number"},
                            "price_unit": {"type": "number"},
                            "name": {"type": "string"},
                        },
                    },
                },
            },
            "required": ["partner_id", "lines"],
        },
    },
    {
        "name": "odoo_financial_summary",
        "description": "Get aggregated financial overview: receivables, payables, overdue.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]

TOOL_HANDLERS = {
    "odoo_get_invoices": handle_get_invoices,
    "odoo_get_payments": handle_get_payments,
    "odoo_get_contacts": handle_get_contacts,
    "odoo_create_invoice": handle_create_invoice,
    "odoo_financial_summary": handle_financial_summary,
}


def handle_mcp_request(request: dict) -> dict:
    """Process a single MCP JSON-RPC request."""
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
            },
        }

    elif method == "notifications/initialized":
        return None

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": MCP_TOOLS},
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        handler = TOOL_HANDLERS.get(tool_name)
        if handler:
            result = handler(tool_args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {"type": "text", "text": json.dumps(result, indent=2)}
                    ]
                },
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
            }

    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }


def main():
    """MCP server main loop — JSON-RPC over stdio."""
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
                "error": {"code": -32700, "message": "Parse error"},
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
