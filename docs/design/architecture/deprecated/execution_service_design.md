# Execution Service Design

> **DEPRECATED** (2026-02-07): This is the original Execution Service design. It has been superseded by the rewritten `execution_service_design.md` in `docs/design/`. Preserved for historical reference.

---

## 0. Customer Purpose & High-Level Overview

The **Execution Service** is a tool execution layer that provides sandboxed, observable execution of external tools and actions via the Model Context Protocol (MCP). It decouples tool execution from the Orchestrator's reasoning logic, ensuring that external integrations do not compromise the stability or security of the core system.

### 0.1 Glossary

*   **Execution Service:** A service that manages the lifecycle and execution of external tools via MCP servers, providing sandboxing, observability, and error handling.
*   **Model Context Protocol (MCP):** A standardized protocol (JSON-RPC 2.0) for AI systems to discover and invoke tools from external servers.
*   **MCP Server:** A process or service that implements the MCP protocol and exposes one or more tools for execution. Examples: `@modelcontextprotocol/server-filesystem` (file operations), `@modelcontextprotocol/server-slack` (Slack integration), `@modelcontextprotocol/server-postgres` (database queries).
*   **MCP Client:** A component that connects to MCP servers, discovers available tools, and invokes them on behalf of the Orchestrator. The Execution Service implements an MCP client. Examples: Python `mcp` SDK client, TypeScript `@modelcontextprotocol/sdk` client.
*   **Tool:** A discrete function or capability exposed by an MCP server (e.g., search, file read, API call).
*   **Orchestrator Service:** The service responsible for managing agent execution, state transitions, and tool invocation.
*   **Sandboxing:** The practice of isolating tool execution in restricted environments (e.g., containers, subprocesses) to prevent unauthorized access or system crashes.


### Core Value Propositions
1.  **Safety & Isolation:** Executes tools in sandboxed environments (e.g., Docker containers), ensuring that malicious or buggy code cannot crash the Orchestrator or access unauthorized file systems.
2.  **Universal Connectivity:** Implements the **Model Context Protocol (MCP)** to provide a standardized interface for connecting to any data source or API (Google Drive, Slack, GitHub) without writing custom adapters.
3.  **Auditability & Observability:** Logs every tool execution, including inputs, outputs, execution time, and error traces, providing a complete audit trail for compliance and debugging.

### High-Level Strategy
*   **MVP (P0 - Steel Thread):** A local execution environment that runs MCP servers as subprocesses. Focus on supporting a core set of tools (Search, File System) required for the initial agent.
*   **Production (P1 - Extension):** A distributed, containerized execution plane where tools run in ephemeral, isolated environments (e.g., Firecracker microVMs) with strict network policies and resource limits.

## 1. System Requirements

To achieve the value propositions, the Execution Service must:

1.  **MCP Compliance:** Fully implement the Model Context Protocol (Client) to discover and invoke tools from any MCP-compliant server.
2.  **Sandboxing:** Enforce strict isolation for tool execution. Failures in a tool must not propagate to the service itself.
3.  **Secret Management:** Securely inject API keys and credentials into tool environments at runtime, ensuring they are never logged or exposed in plain text.
4.  **Timeout & Resource Control:** Enforce hard timeouts and memory limits on all tool executions to prevent runaway processes.
5.  **Asynchronous Execution:** Support long-running tools (e.g., "Scrape this website") without blocking the request thread.

## 2. Architecture & Internal Design

The Execution Service serves as a bridge between the Orchestrator and the external world of MCP servers.

### Level 1: API Layer (RPC Interface)
*   **Role:** The entry point for the Orchestrator.
*   **Responsibility:**
    *   **Request Validation:** Ensures the tool call matches the expected schema.
    *   **Authentication:** Verifies the request comes from a trusted Orchestrator instance.

### Level 2: Connection Manager
*   **Role:** Manages the lifecycle of connections to MCP Servers.
*   **Responsibility:**
    *   **Server Discovery:** Locates the appropriate MCP server for a requested tool.
    *   **Connection Pooling:** Maintains active connections (Stdio or SSE) to frequently used servers to reduce latency.
    *   **Health Checks:** Periodically pings servers to ensure availability.

### Level 3: Runtime Manager
*   **Role:** Controls the physical execution environment.
*   **Responsibility:**
    *   **Process Management:** Spawns and kills subprocesses (MVP) or containers (P1).
    *   **Environment Injection:** Populates environment variables (API Keys) securely.
    *   **Log Capture:** Intercepts `stdout`/`stderr` from the tool for logging.

## 3. Interfaces & Interactions

### 3.1 Interaction with Orchestrator Service
*   **Tool Discovery:**
    *   **Trigger:** Orchestrator startup or refresh.
    *   **Action:** `GET /tools`
    *   **Data:** Returns a list of available tools and their JSON schemas (aggregated from all MCP servers).
*   **Tool Execution:**
    *   **Trigger:** Agent decides to call a tool.
    *   **Action:** `POST /execute`
    *   **Data:** `{ "tool_name": "search", "arguments": { "query": "..." } }`
    *   **Response:** `{ "status": "success", "output": "..." }`

### 3.2 Interaction with MCP Servers
*   **Protocol:** Model Context Protocol (JSON-RPC 2.0).
*   **Transport:**
    *   **Stdio:** For local servers (MVP).
    *   **SSE (Server-Sent Events):** For remote servers (P1).
*   **Key Methods:**
    *   `tools/list`: Discover capabilities.
    *   `tools/call`: Invoke a function.

## 4. Technology Stack & Trade-offs

### Python (FastAPI)
*   **Why:** Consistent with the Orchestrator (LangGraph); excellent support for subprocess management and async I/O.
*   **Trade-off:** Lower raw performance than Go/Rust, but sufficient for an I/O-bound service wrapping external tools.

### Pydantic
*   **Why:** Defines the internal data structures and automatically generates the JSON Schemas required by MCP and the LLM.
*   **Trade-off:** None; it's the standard for modern Python AI development.

### Model Context Protocol (MCP) SDK
*   **Why:** The emerging standard for AI tool interoperability. Prevents vendor lock-in to proprietary plugin ecosystems.
*   **Trade-off:** Protocol is still evolving; may require frequent updates to the SDK.

### Docker (P1)
*   **Why:** Industry standard for containerization and isolation.
*   **Trade-off:** Overhead of managing a container runtime; "Cold start" latency for new containers.

## 5. External Dependencies

### 5.1 MCP Servers
*   **Standard Library:** `mcp-server-core` (Task Management, Filesystem, Fetch). See `design/standard_tool_library.md`.
*   **Third-Party:** `slack`, `github`, `postgres`.

### 5.2 Secret Store (e.g., HashiCorp Vault or Env Vars)
*   **Role:** Stores API keys for external services (e.g., OpenAI Key, Slack Token).

## 6. Operational Considerations

### 6.1 Error Handling
*   **Tool Failure:** If a tool crashes or returns an error, the Execution Service wraps it in a structured `ToolError` object and returns it to the Orchestrator. The agent then sees this error and can try to self-correct.
*   **Timeout:** If a tool takes longer than `N` seconds, the Runtime Manager kills the process and returns a `TimeoutError`.

### 6.2 Safety & Security
*   **Input Sanitization:** Although tools are sandboxed, we validate all arguments against the schema to prevent obvious injection attacks.
*   **Principle of Least Privilege:** MCP servers are granted only the permissions they strictly need (e.g., read-only access to specific directories).

## 7. Future Roadmap & Alternatives

### 7.1 Serverless Execution (AWS Lambda / Cloud Run)
*   **Why:** Infinite scaling and zero maintenance of worker nodes.
*   **Trade-off:** Higher latency (cold starts) and difficult to maintain persistent connections (WebSockets/SSE) required for some MCP features.

### 7.2 WebAssembly (WASM) Runtime
*   **Why:** Near-instant startup times and perfect sandboxing.
*   **Trade-off:** Ecosystem is less mature than Docker; fewer tools support compiling to WASM currently.

## 8. Implementation Roadmap

### 8.1 Phase 1: MVP (P0) - The "Steel Thread"
**Goal:** Enable the Orchestrator to call local tools via MCP.

1.  **Service Setup:** Create a FastAPI service with the official `mcp` Python SDK.
2.  **Local Runtime:** Implement a `SubprocessRuntime` that can launch `npx` or `python` based MCP servers defined in a config file.
3.  **Tool Aggregation:** Implement the logic to query multiple local MCP servers and merge their tool lists into a single registry.
4.  **Integration:** Connect the Orchestrator to this service and verify it can call the `filesystem` tool.

### 8.2 Extension to Production (P1)
**Goal:** Secure, remote execution for multi-tenant workloads.

1.  **Containerization:** Replace `SubprocessRuntime` with `DockerRuntime`.
2.  **Security Hardening:** Implement network policies to restrict what domains tools can access.
3.  **Remote MCP:** Add support for connecting to remote MCP servers over SSE (e.g., a shared "Search Service").
