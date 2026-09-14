"""
Model Context Protocol (MCP) — Minimal Production-Grade Server Demo
Illustrating Tier 1 Primitives: Tools (with strict JSON schemas) and Resources over stdio JSON-RPC 2.0.
"""

import sys
import json
from typing import Any, Dict

PROTOCOL_VERSION = "2024-11-05"

# Simulated enterprise data store
DATABASE = {
    "users": [
        {"id": 1, "name": "Alice", "role": "admin"},
        {"id": 2, "name": "Bob", "role": "engineer"},
    ]
}

def send_response(response_obj: Dict[str, Any]) -> None:
    """Send newline-delimited JSON-RPC 2.0 message over stdout."""
    payload = json.dumps(response_obj)
    sys.stdout.write(payload + "\n")
    sys.stdout.flush()

def handle_initialize(req_id: Any, params: Dict[str, Any]) -> None:
    send_response({
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": True},
                "resources": {"subscribe": False, "listChanged": True}
            },
            "serverInfo": {
                "name": "enterprise-demo-mcp",
                "version": "1.0.0"
            }
        }
    })

def handle_tools_list(req_id: Any) -> None:
    send_response({
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "tools": [
                {
                    "name": "lookup_user",
                    "description": "Look up an enterprise user by numerical ID.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "integer",
                                "description": "The exact user ID to look up"
                            }
                        },
                        "required": ["user_id"],
                        "additionalProperties": False
                    }
                }
            ]
        }
    })

def handle_tools_call(req_id: Any, params: Dict[str, Any]) -> None:
    name = params.get("name")
    args = params.get("arguments", {})

    if name == "lookup_user":
        user_id = args.get("user_id")
        user = next((u for u in DATABASE["users"] if u["id"] == user_id), None)
        if user:
            content = [{"type": "text", "text": json.dumps(user)}]
            send_response({"jsonrpc": "2.0", "id": req_id, "result": {"content": content}})
        else:
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": f"User ID {user_id} not found"}
            })
    else:
        send_response({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Tool '{name}' not found"}
        })

def handle_resources_list(req_id: Any) -> None:
    send_response({
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "resources": [
                {
                    "uri": "db://enterprise/users/schema",
                    "name": "User Table Schema",
                    "description": "PostgreSQL schema definition for analytical users table",
                    "mimeType": "application/json"
                }
            ]
        }
    })

def handle_resources_read(req_id: Any, params: Dict[str, Any]) -> None:
    uri = params.get("uri")
    if uri == "db://enterprise/users/schema":
        schema = {
            "table": "users",
            "columns": ["id INTEGER PRIMARY KEY", "name VARCHAR(100)", "role VARCHAR(50)"]
        }
        send_response({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(schema)
                    }
                ]
            }
        })
    else:
        send_response({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32602, "message": f"Resource URI '{uri}' not found"}
        })

def main() -> None:
    """Event loop consuming JSON-RPC 2.0 frames from stdin."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            send_response({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
            continue

        method = msg.get("method")
        req_id = msg.get("id")

        if method == "initialize":
            handle_initialize(req_id, msg.get("params", {}))
        elif method == "notifications/initialized":
            # Handshake complete; no response required for notification
            pass
        elif method == "tools/list":
            handle_tools_list(req_id)
        elif method == "tools/call":
            handle_tools_call(req_id, msg.get("params", {}))
        elif method == "resources/list":
            handle_resources_list(req_id)
        elif method == "resources/read":
            handle_resources_read(req_id, msg.get("params", {}))
        elif method == "ping":
            send_response({"jsonrpc": "2.0", "id": req_id, "result": {}})
        else:
            if req_id is not None:
                send_response({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method '{method}' not implemented"}})

if __name__ == "__main__":
    main()
