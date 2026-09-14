# What Is New This Week Track

> **Focus**: Rapid, rigorous architectural evaluations of emerging systems, protocols, and developer infrastructure.  
> **Framing**: Deep-dive technical teardowns: "What fundamental distributed systems problem does this solve, what is the exact wire protocol, and where are the operational and security boundary traps in production?"

---

## Chapter Index

| Week / Module | Topic | Notes | Interactive Explainer |
| :--- | :--- | :--- | :--- |
| `01` | **Model Context Protocol (MCP): The $N \times M$ Integration Bus** | [notes.md](01-model-context-protocol/notes.md) | [article.html](01-model-context-protocol/article.html) |

---

## Architectural Focus: Model Context Protocol (MCP)

### The $N \times M$ Problem & Open Protocol Standardization
Prior to protocol standardization, connecting $N$ foundational model hosts (Claude Desktop, Cursor, custom enterprise orchestration agents) to $M$ enterprise data sources and internal tools (Postgres, GitHub, Jira, Datadog) required bespoke point-to-point glue code.

MCP adopts the Language Server Protocol (LSP) architectural pattern:
- **Host**: The LLM runtime coordinator (maintains user interaction, context window, and security posture).
- **Client**: An in-process entity within the host maintaining a strict 1:1 transport connection with an MCP server.
- **Server**: A lightweight, isolated process exposing domain-specific context, tools, and prompts without needing direct access to foundational model API keys.

```
+-------------------------------------------------------------+
| Host Application (e.g. IDE, Agent Runtime)                  |
|  +-------------------------+   +-------------------------+  |
|  |       MCP Client A      |   |       MCP Client B      |  |
+--+------------|------------+---+------------|------------+--+
                | JSON-RPC 2.0                | JSON-RPC 2.0
                | (stdio / SSE)               | (stdio / SSE)
+---------------v-------------+ +-------------v---------------+
| Server A: Postgres Context  | | Server B: GitHub Operations |
| - Resources: db://schemas   | | - Tools: create_pr, merge   |
| - Tools: execute_query      | | - Prompts: pr_review_flow   |
+-----------------------------+ +-----------------------------+
```

### Core Primitives
1. **Tools**: Executable operations executed by the server on behalf of the host. Tools must expose strict JSON Schema input definitions so model invocations are validated prior to execution.
2. **Resources**: Passive, read-only contexts identified by standardized URIs (`postgres://prod/users/schema`). Servers can push list-change notifications, allowing hosts to hydrate context dynamically without polling.
3. **Prompts**: Versioned, parameterized prompt templates surfaced by the server to guide models through domain-specific workflows.

### Wire Protocol: JSON-RPC 2.0
All interactions use bi-directional JSON-RPC 2.0 messages over standard I/O (`stdio` for local co-located processes) or HTTP Server-Sent Events (`SSE` for remote infrastructure). A mandatory initialization handshake enforces explicit capability negotiation:

```json
// Client -> Server (Handshake Request)
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "roots": { "listChanged": true },
      "sampling": {}
    },
    "clientInfo": { "name": "EnterpriseAgentHost", "version": "1.0.0" }
  }
}
```

### Security Boundaries & Trust Architecture
- **Credential Isolation**: Database credentials, GitHub tokens, and enterprise secrets stay inside the server process. The LLM host never sees the raw credential; the MCP server never sees the host's foundational model API keys.
- **Human-In-The-Loop (HITL)**: Tool calls are treated as unauthenticated execution requests until explicitly authorized by the host application's policy engine or user confirmation.
- **Read/Write Segregation**: Resources are strictly read-only vectors; mutations must be gated exclusively as Tools with structured input sanitization to eliminate prompt-injection-driven execution paths.

---

*Note: As new weekly teardowns are completed, append rows to this table following the format in [CONTRIBUTING.md](../CONTRIBUTING.md).*
