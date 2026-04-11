#!/usr/bin/env python3
"""
mcp_social_server.py — Gold Tier MCP Server for Social Media Operations

A Model Context Protocol (MCP) server exposing social media operations as tools.
Generates drafts and posts after approval.

Protocol: MCP over stdio (JSON-RPC 2.0)
Transport: stdin/stdout

Tools:
    - social_generate_draft(platform, topic, audience, goal) — Generate post draft
    - social_post(platform, approval_file) — Post after approval
    - social_list_drafts() — List pending drafts

Usage:
    python mcp_social_server.py

Configure in .claude/settings.json:
{
  "mcpServers": {
    "vault-social": {
      "command": "python3",
      "args": ["mcp_social_server.py"],
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
DASHBOARD_FILE = os.path.join(VAULT_DIR, "Dashboard.md")

sys.path.insert(0, VAULT_DIR)

try:
    from approval_gate import check_approval, mark_approval_executed
except ImportError:
    def check_approval(action_type, target):
        return {"approved": False, "reason": "approval_gate module not found"}
    def mark_approval_executed(path):
        return False

try:
    from action_logger import log_action
except ImportError:
    def log_action(*args, **kwargs):
        return {}

try:
    from social_media_manager import (
        generate_social_post, execute_social_post, list_drafts,
    )
except ImportError:
    def generate_social_post(**kwargs):
        return {"error": "social_media_manager module not available"}
    def execute_social_post(platform, approval_file):
        return {"status": "failed", "details": "module not available"}
    def list_drafts():
        return []


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


# ---------------------------------------------------------------------------
# Tool Handlers
# ---------------------------------------------------------------------------

def handle_generate_draft(params: dict) -> dict:
    platform = params.get("platform", "")
    topic = params.get("topic", "")
    audience = params.get("audience", "business professionals")
    goal = params.get("goal", "awareness")

    if not platform:
        return {"status": "failed", "error": "missing platform"}
    if not topic:
        return {"status": "failed", "error": "missing topic"}

    result = generate_social_post(
        platform=platform,
        topic=topic,
        audience=audience,
        goal=goal,
    )

    if "error" in result:
        log_action("social_generate_draft", platform, "failure",
                   error=result["error"])
        return {"status": "failed", "error": result["error"]}

    log_action("social_generate_draft", platform, "success",
               metadata={"draft_path": result["draft_path"]})
    update_dashboard(
        f"Social media draft created: {result['draft_path']} ({platform})"
    )

    return {
        "status": "success",
        "draft_path": result["draft_path"],
        "platform": result["platform"],
        "char_count": len(result["post_content"]),
        "content_preview": result["post_content"][:200],
    }


def handle_post(params: dict) -> dict:
    platform = params.get("platform", "")
    approval_file = params.get("approval_file", "")

    if not platform:
        return {"status": "failed", "error": "missing platform"}
    if not approval_file:
        return {"status": "failed", "error": "missing approval_file"}

    # Check approval
    action_type = f"{platform}_post"
    approval = check_approval(action_type, approval_file)
    if not approval.get("approved"):
        # Also check generic social_media_post
        approval = check_approval("social_media_post", approval_file)

    if not approval.get("approved"):
        reason = approval.get("reason", "no valid approval")
        log_action("social_post", f"{platform}:{approval_file}", "failure",
                   error=f"No approval: {reason}")
        return {"status": "failed", "error": f"no_valid_approval: {reason}"}

    result = execute_social_post(platform, approval_file)

    if result["status"] == "posted":
        mark_approval_executed(approval.get("file", ""))
        log_action("social_media_post", platform, "success",
                   metadata={"details": result["details"]})
        update_dashboard(f"Social media posted: {platform} — {result['details']}")
    elif result["status"] == "ready_manual":
        log_action("social_media_post", platform, "success",
                   metadata={"mode": "manual"})
    else:
        log_action("social_media_post", platform, "failure",
                   error=result.get("details", "unknown error"))

    return result


def handle_list_drafts(params: dict) -> dict:
    drafts = list_drafts()
    return {"status": "success", "drafts": drafts, "count": len(drafts)}


# ---------------------------------------------------------------------------
# MCP Protocol (JSON-RPC 2.0 over stdio)
# ---------------------------------------------------------------------------

MCP_SERVER_INFO = {
    "name": "vault-social",
    "version": "1.0.0",
}

MCP_TOOLS = [
    {
        "name": "social_generate_draft",
        "description": (
            "Generate a social media post draft for Facebook, Instagram, or Twitter. "
            "Creates a draft file in Pending_Approval/ for human review."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "description": "Platform: facebook, instagram, or twitter",
                    "enum": ["facebook", "instagram", "twitter"],
                },
                "topic": {
                    "type": "string",
                    "description": "Topic or subject of the post",
                },
                "audience": {
                    "type": "string",
                    "description": "Target audience (default: business professionals)",
                },
                "goal": {
                    "type": "string",
                    "description": "Post goal: awareness, lead_generation, update, engagement",
                    "enum": ["awareness", "lead_generation", "update", "engagement"],
                },
            },
            "required": ["platform", "topic"],
        },
    },
    {
        "name": "social_post",
        "description": (
            "Publish a social media post after approval. Requires a valid approval "
            "and the draft file path. Posts via API if keys are configured, otherwise "
            "marks as ready for manual posting."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "description": "Platform: facebook, instagram, or twitter",
                    "enum": ["facebook", "instagram", "twitter"],
                },
                "approval_file": {
                    "type": "string",
                    "description": "Path to the draft/approval file in Pending_Approval/",
                },
            },
            "required": ["platform", "approval_file"],
        },
    },
    {
        "name": "social_list_drafts",
        "description": "List all pending social media post drafts.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]

TOOL_HANDLERS = {
    "social_generate_draft": handle_generate_draft,
    "social_post": handle_post,
    "social_list_drafts": handle_list_drafts,
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
