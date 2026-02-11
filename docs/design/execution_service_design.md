# Execution Service Design

---

## 0. Customer Purpose & High-Level Overview

The **Execution Service** provides sandboxed tool discovery and execution for the Municipal Agent system. It manages MCP (Model Context Protocol) server subprocesses, discovers available tools, validates execution arguments (including filesystem path sandboxing), and routes tool calls to the correct MCP server.

The service acts as a security boundary between the agent's tool requests and the host system.

### 0.1 Glossary

*   **Execution Service:** Sandboxed tool execution gateway. Port 8002.
*   **MCP (Model Context Protocol):** A JSON-RPC 2.0 protocol for standardized tool discovery and execution. Tools are hosted by MCP servers.
*   **MCP Server:** A subprocess that exposes tools via JSON-RPC 2.0 over stdin/stdout. Configured in `mcp_servers.json`.
*   **SubprocessRuntime:** Manages MCP server subprocess lifecycle (spawn, communicate, terminate).
*   **MCPClient:** JSON-RPC client for communicating with a single MCP server via stdin/stdout.
*   **ConnectionManager:** Orchestrates all MCP server connections, builds the tool registry, and routes execution requests.
*   **Tool Registry:** Internal mapping of tool_name → server_name used to route execution requests.
*   **Sandbox Directory:** A restricted filesystem path where all tool file operations must occur. Path traversal is rejected.

### 0.2 Core Value Propositions

1.  **Security Boundary:** Path validation and subprocess isolation prevent tools from accessing files outside the sandbox.
2.  **Protocol Standardization:** MCP provides a uniform interface for tool discovery and execution regardless of the underlying tool implementation.
3.  **Dynamic Discovery:** Tools are discovered at startup by querying each MCP server, enabling plug-and-play tool addition.

### 0.3 High-Level Strategy

*   **MVP (P0 - Steel Thread):** Filesystem tools (read_file, write_file) via MCP with sandbox path validation.
*   **Production (P1 - Extension):** Additional MCP servers for HTTP, database, and domain-specific tools.

---

## 1. System Requirements

1.  **Tool Discovery:** Enumerate all tools from configured MCP servers at startup via `tools/list`.
2.  **Sandboxed Execution:** Validate all filesystem paths against the sandbox directory before execution.
3.  **Subprocess Management:** Spawn, communicate with, and gracefully terminate MCP server subprocesses.
4.  **Timeout Handling:** Enforce configurable timeouts per tool execution (default 30s).
5.  **Health Reporting:** Expose `/health` with per-server connection status.

---

## 2. Architecture & Internal Design

### 2.1 API Layer (FastAPI)

*   **`GET /tools`** — List all available tools from all MCP servers. Returns `{ tools: [ToolSchema] }`.
*   **`POST /execute`** — Execute a named tool with arguments. Returns `{ status, output, execution_time_ms }`.
*   **`GET /health`** — Health check with MCP server status map (`{ servers: { name: "running"|"stopped" } }`).

### 2.2 Connection Manager

*   **Role:** Top-level orchestrator for all MCP server connections.
*   **Responsibilities:**
    *   **Startup:** Load server configs from `mcp_servers.json`, spawn all servers, build tool registry.
    *   **Tool Registry:** Map each tool_name to its server_name for routing.
    *   **Execution Routing:** On `/execute`, look up the server for the requested tool, validate paths, call the MCP server.
    *   **Path Validation:** Before calling filesystem tools, validate all path arguments against the sandbox directory.
    *   **Shutdown:** Gracefully terminate all MCP server subprocesses.

### 2.3 MCP Client

*   **Role:** JSON-RPC 2.0 client for a single MCP server.
*   **Protocol:** Communicates over stdin/stdout of the subprocess.
*   **Methods:**
    *   **`list_tools()`** — Send `tools/list` JSON-RPC request. Returns list of tool schemas.
    *   **`call_tool(name, arguments)`** — Send `tools/call` JSON-RPC request. Returns tool output.
*   **Request Tracking:** Maintains monotonic request_id counter for matching responses.
*   **Error Handling:** Catches JSON parse errors, timeouts, and server disconnections.

### 2.4 Subprocess Runtime

*   **Role:** Manage MCP server subprocess lifecycle.
*   **Responsibilities:**
    *   **Spawn:** `asyncio.create_subprocess_exec()` with stdin/stdout pipes and custom environment.
    *   **Communicate:** Read/write via `asyncio.StreamReader` / `asyncio.StreamWriter`.
    *   **Terminate:** Graceful termination with 5s timeout, then force kill (`SIGKILL`).
    *   **Tracking:** Maps server_name → subprocess for lifecycle management.

### 2.5 Path Validation

```
1. Extract path-like arguments from tool input
   (keys: path, file, filepath, directory, dir, source, destination, target, filename)
2. Resolve to absolute path
   - Relative paths resolved relative to sandbox directory
   - Absolute paths used as-is
3. Check resolved path starts with sandbox directory
   - If not: raise PathValidationError (400 response)
   - If yes: proceed with execution
4. Auto-create sandbox directory if missing
```

### 2.6 MCP Server Configuration

Loaded from `config/mcp_servers.json`:

```json
{
  "servers": [
    {
      "name": "filesystem",
      "command": "node",
      "args": ["path/to/mcp-server.js"],
      "env": { "SANDBOX_DIR": "/workspace" },
      "timeout": 30
    }
  ]
}
```

---

## 3. Interfaces & Interactions

### 3.1 Inbound: Orchestrator → Execution Service

*   **Tool Discovery:**
    *   **Action:** `GET /tools`
    *   **Output:** `{ tools: [{ name: str, description: str, input_schema: dict }] }`

*   **Tool Execution:**
    *   **Trigger:** Agent decides to call a tool during reasoning.
    *   **Action:** `POST /execute`
    *   **Data:**
        *   Input: `{ tool_name: str, arguments: dict, timeout?: float }`
        *   Output: `{ status: "success"|"error", output: any, error?: str, execution_time_ms: float }`

### 3.2 Outbound: Execution Service → MCP Servers

*   **Protocol:** JSON-RPC 2.0 over stdin/stdout.
*   **Methods:**
    *   `tools/list` — Discovery
    *   `tools/call` — Execution

### 3.3 Tool Schema

```python
class ToolSchema(BaseModel):
    name: str              # Tool identifier (e.g., "read_file")
    description: str       # Human-readable description
    input_schema: dict     # JSON Schema for tool arguments
```

### 3.4 Execute Response

```python
class ExecuteResponse(BaseModel):
    status: str            # "success" or "error"
    output: Any            # Tool output (varies by tool)
    error: str | None      # Error message if status="error"
    execution_time_ms: float  # Wall clock execution time
```

---

## 4. Technology Stack & Trade-offs

### 4.1 MCP (Model Context Protocol)

*   **Why:** Standardized protocol for tool interaction. Tools can be written in any language as long as they speak JSON-RPC 2.0 over stdio.
*   **Trade-off:** Subprocess management adds complexity (spawn, communicate, terminate, crash recovery).

### 4.2 JSON-RPC 2.0 over stdio

*   **Why:** Simple, language-agnostic protocol. No network configuration needed for subprocess communication.
*   **Trade-off:** Single-threaded per server. Cannot multiplex requests to the same server.

### 4.3 Path Validation (Allowlist Approach)

*   **Why:** Prevents path traversal attacks (e.g., `../../etc/passwd`). All paths must resolve within the sandbox.
*   **Trade-off:** Restricts tools to a single directory tree. Acceptable for sandboxed execution model.

---

## 5. External Dependencies

### 5.1 Infrastructure

*   **Workspace Volume:** Shared Docker volume (`/workspace`) for sandbox file operations.

### 5.2 MCP Servers

*   **Filesystem Server:** Provides `read_file`, `write_file`, and related file tools.
*   **Additional servers:** Configured via `mcp_servers.json`.

---

## 6. Operational Considerations

### 6.1 Error Handling

*   **Tool Not Found:** 404 response if tool_name not in registry.
*   **Path Validation Failure:** 400 response with error detail.
*   **Tool Timeout:** Execution terminated, error returned with `execution_time_ms`.
*   **MCP Server Crash:** Detected via subprocess exit. Server marked as "stopped" in health check.

### 6.2 Safety & Security

*   **Sandbox Enforcement:** All filesystem paths validated against `SANDBOX_DIRECTORY`.
*   **Process Isolation:** Each MCP server runs in its own subprocess with controlled environment variables.
*   **Timeout Enforcement:** Configurable per-request timeout (default 30s) prevents runaway executions.

### 6.3 Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8002` | Service port |
| `LOG_LEVEL` | `INFO` | Logging level |
| `MCP_CONFIG_PATH` | `config/mcp_servers.json` | Path to MCP server configuration |
| `DEFAULT_TIMEOUT` | `30` | Default tool execution timeout (seconds) |
| `SANDBOX_DIRECTORY` | `/workspace` | Sandbox root for file operations |
| `MAX_CONCURRENT_EXECUTIONS` | `10` | Max parallel tool executions |

---

## 7. Future Roadmap

### 7.1 Additional MCP Servers (P1)

*   HTTP/API tools for external service integration.
*   Database query tools for structured data access.
*   Domain-specific tools for business logic.

### 7.2 Tool Result Caching (P1)

*   Cache idempotent tool results to reduce redundant executions.

### 7.3 Crash Recovery (P1)

*   Automatic MCP server restart on subprocess crash.
*   Health monitoring with alerting.
