# Municipal Agent: System Architecture

## 0. Customer Purpose & High-Level Overview

Municipal Agent enables businesses to deploy autonomous AI agents that translate unstructured human intent into deterministic business actions. Users interact with agents through platform integrations (Discord) and receive real-time, streaming responses as the agent reasons and executes tools.

The system follows a **streaming-first architecture** where the Orchestrator Service always executes in streaming mode, emitting fine-grained Server-Sent Events (SSE) that clients consume directly.

### 0.1 Glossary

*   **Streaming-First Architecture:** A design where the agent graph always executes in streaming mode via SSE. Clients connect directly to the Orchestrator's streaming endpoint.
*   **Platform Adapter:** A service that translates between an external platform (Discord, Slack) and the Orchestrator Service. It handles the full bidirectional communication loop within a single service.
*   **Orchestrator Service:** The central microservice that hosts and executes the LangGraph agent. Exposes a streaming SSE API at `/v1/agent/run`.
*   **Context Service:** Event logging and knowledge retrieval service backed by PostgreSQL with Apache AGE.
*   **Execution Service:** Sandboxed tool execution gateway using MCP (Model Context Protocol) servers.
*   **Discord Service:** The Platform Adapter for Discord. Maintains a persistent WebSocket connection to Discord and streams responses from the Orchestrator.
*   **LangGraph:** A library for building stateful, multi-actor applications with LLMs, used to define the agent's execution graph.
*   **MCP (Model Context Protocol):** A JSON-RPC 2.0 protocol for standardized tool discovery and execution.
*   **SSE (Server-Sent Events):** HTTP-based unidirectional streaming protocol used by the Orchestrator to emit agent events.
*   **InternalEvent:** The canonical Pydantic schema used by Platform Adapters to normalize external events before sending to the Orchestrator.

### 0.2 Core Value Propositions

1.  **Unified Execution Path:** The Orchestrator Service runs identically regardless of the trigger source. All clients consume the same SSE stream.
2.  **Real-Time User Experience:** Streaming-first design provides immediate feedback—thinking indicators, tool status, and token streaming.
3.  **Sandboxed Tool Execution:** MCP-based tool execution with path validation ensures agents can safely interact with filesystems and external services.

### 0.3 High-Level Strategy

*   **MVP (P0 - Steel Thread):** A single agent handling queries via Discord, backed by Ollama (llama3.2:3b) with filesystem tools.
*   **Production (P1 - Extension):** Multiple specialized agents, web UI with WebSocket, approval workflows, multi-tenant isolation.

---

## 1. System Requirements

To achieve the value propositions, the system must:

1.  **Execute agents in streaming mode by default:** All agent invocations use LangGraph's `astream_events()`, emitting SSE events.
2.  **Decouple input from execution:** The Orchestrator Service does not know about the source platform; it processes inputs and streams events.
3.  **Maintain conversation state:** LangGraph checkpointing via `AsyncPostgresSaver` enables multi-turn conversations.
4.  **Isolate tool execution:** Tools run in sandboxed MCP server subprocesses with path validation.
5.  **Log all agent activity:** Every agent invocation is recorded as an immutable event in the Context Service.

---

## 2. Architecture & Internal Design

### 2.1 System Diagram

```
                               ┌─────────────────────────┐
                               │   Orchestrator Service  │
                               │      (Port 8000)        │
                               │  ┌───────────────────┐  │
                               │  │   Agent Graph     │  │
                               │  │  (LangGraph)      │  │
                               │  └─────────┬─────────┘  │
                               └──────┬─────┼──────┬─────┘
                                      │     │      │
                            HTTP POST │     │      │ HTTP POST
                                      ▼     │      ▼
                          ┌──────────────┐  │  ┌──────────────┐
                          │   Context    │  │  │  Execution   │
                          │   Service   │  │  │   Service    │
                          │ (Port 8001) │  │  │ (Port 8002)  │
                          └──────┬───────┘  │  └──────┬───────┘
                                 │          │         │
                                 ▼          │         ▼
                          ┌──────────────┐  │  ┌──────────────┐
                          │  PostgreSQL  │  │  │  MCP Servers │
                          │  (Port 5433) │  │  │  (Subprocess)│
                          └──────────────┘  │  └──────────────┘
                                            │
                                     SSE Stream
                                   /v1/agent/run
                                            │
                   ┌────────────────────────┴───────────────────────┐
                   │                                                │
                   ▼                                                ▼
            ┌─────────────┐                                  ┌─────────────┐
            │  Web Client │                                  │   Discord   │
            │  (Future)   │                                  │   Service   │
            └─────────────┘                                  │ (Port 8003) │
                                                             └──────┬──────┘
                                                                    │
                                                              Discord WebSocket
                                                                    │
                                                                    ▼
                                                             ┌─────────────┐
                                                             │   Discord   │
                                                             │  Platform   │
                                                             └─────────────┘
```

### 2.2 Component Overview

| Component | Location | Port | Responsibility |
|-----------|----------|------|----------------|
| **Orchestrator Service** | `services/orchestrator-service/` | 8000 | Hosts LangGraph agent, executes reasoning, streams SSE events |
| **Context Service** | `services/context-service/` | 8001 | Event logging, knowledge graph queries (PostgreSQL + Apache AGE) |
| **Execution Service** | `services/execution-service/` | 8002 | Sandboxed MCP tool execution with path validation |
| **Discord Service** | `services/discord-service/` | 8003 | Platform Adapter: Discord WebSocket ↔ Orchestrator SSE |

**Infrastructure:**

| Component | Port | Purpose |
|-----------|------|---------|
| **PostgreSQL 16** | 5433 | Persistent storage: events, checkpoints, knowledge graph (AGE) |
| **Ollama** | 11434 | Local LLM hosting (llama3.2:3b) |

### 2.3 Orchestrator Service

*   **Role:** Execute agent logic using LangGraph and stream results via SSE.
*   **Responsibilities:**
    *   **Graph Execution:** Run the 3-node LangGraph (reasoning → tool_call → respond) with conditional routing.
    *   **Streaming:** Emit SSE events mapped from LangGraph's `astream_events()`:
        *   `thinking`: LLM token stream from `on_chat_model_stream` events.
        *   `tool_start`: Tool invocation initiated, with name and arguments.
        *   `tool_result`: Tool output returned from Execution Service.
        *   `done`: Graph execution complete.
    *   **Checkpointing:** Persist agent state at every node transition via `AsyncPostgresSaver`.
    *   **Tool Invocation:** Call Execution Service via synchronous HTTP (`/execute`, `/tools`).
    *   **Event Logging:** Post events to Context Service (`/events`) for audit trail.

### 2.4 Context Service

*   **Role:** Immutable event logging and knowledge retrieval.
*   **Responsibilities:**
    *   **Event Logging:** Accept and store `InternalEvent` objects via `POST /events` using asyncpg.
    *   **Knowledge Queries:** Execute graph queries against Apache AGE via `POST /query` (MVP: hardcoded queries).
    *   **Database Management:** Manage asyncpg connection pool (2-10 connections).

### 2.5 Execution Service

*   **Role:** Sandboxed tool discovery and execution via MCP.
*   **Responsibilities:**
    *   **Tool Discovery:** Enumerate tools from all configured MCP servers via `GET /tools`.
    *   **Tool Execution:** Route tool calls to the correct MCP server via `POST /execute`.
    *   **Path Validation:** Validate all filesystem paths against sandbox directory to prevent escapes.
    *   **MCP Server Management:** Spawn and manage MCP server subprocesses communicating via JSON-RPC 2.0 over stdio.

### 2.6 Discord Service (Platform Adapter)

*   **Role:** Bidirectional communication between Discord and the Orchestrator.
*   **Responsibilities:**
    *   **Connection:** Maintain persistent WebSocket to Discord via discord.py.
    *   **Normalization:** Convert `discord.Message` to `InternalEvent` schema (Pydantic).
    *   **Streaming:** POST to Orchestrator `/v1/agent/run` and consume SSE stream.
    *   **Delivery:** Update Discord messages in real-time with debounced edits (1s interval).
    *   **Error Handling:** Retry with exponential backoff (3 attempts), graceful error messages.
    *   **Health:** Separate FastAPI health server on port 8003.

---

## 3. Interfaces & Interactions

### 3.1 Steel Thread Flow (Discord)

The primary end-to-end flow:

```
User sends message in Discord
        │
        ▼
Discord Service: on_message()
  ├── Normalize to InternalEvent
  ├── Send "Thinking..." placeholder to Discord
  └── POST /v1/agent/run (SSE) to Orchestrator
        │
        ▼
Orchestrator Service: /v1/agent/run
  ├── reasoning node: LLM decides action (call_tool or respond)
  │   ├── If call_tool:
  │   │   ├── POST /execute to Execution Service
  │   │   ├── Emit tool_start + tool_result SSE events
  │   │   └── Loop back to reasoning
  │   └── If respond:
  │       └── Emit done SSE event
  ├── POST /events to Context Service (audit log)
  └── Stream SSE events back to caller
        │
        ▼
Discord Service: consume SSE stream
  ├── Accumulate text chunks
  ├── Edit Discord message every 1s (debounced)
  └── Final edit with complete response
```

### 3.2 Orchestrator API

*   `POST /v1/agent/run` — Streaming endpoint (SSE)
    *   Input: `{ input: str, thread_id: str, correlation_id?: str, config?: dict }`
    *   Output: SSE stream of `AgentEvent` objects
*   `POST /process` — Synchronous endpoint
    *   Input: `{ thread_id: str, message: str, correlation_id: str }`
    *   Output: `{ response: str, thread_id: str, correlation_id: str }`
*   `GET /health` — Health check

### 3.3 Context Service API

*   `POST /events` — Log an event
    *   Input: `InternalEvent` (correlation_id, event_type, source, payload)
    *   Output: `{ event_id: str, created_at: str }`
*   `POST /query` — Knowledge graph query
    *   Input: `KnowledgeQuery` (query, strategies)
    *   Output: Query results
*   `GET /health` — Health check

### 3.4 Execution Service API

*   `GET /tools` — List available MCP tools
    *   Output: `{ tools: [{ name, description, input_schema }] }`
*   `POST /execute` — Execute a tool
    *   Input: `{ tool_name: str, arguments: dict, timeout?: float }`
    *   Output: `{ status: str, output: any, execution_time_ms: float }`
*   `GET /health` — Health check with MCP server status

### 3.5 Discord Service

*   No public API — receives events via Discord WebSocket
*   `GET /health` — Health check (port 8003)
*   `GET /ready` — Readiness check (port 8003)

### 3.6 SSE Event Schema

```json
{ "type": "thinking", "content": "string" }
{ "type": "tool_start", "name": "string", "args": {} }
{ "type": "tool_result", "name": "string", "result": "string" }
{ "type": "done", "usage": { "tokens": 0 } }
```

---

## 4. Technology Stack & Trade-offs

### 4.1 SSE for Streaming

*   **Why:** Simple unidirectional streaming over HTTP/1.1. Native support in httpx and FastAPI's `StreamingResponse`.
*   **Trade-off:** No bidirectional communication. Sufficient for MVP where clients only send a single request and receive a stream. WebSocket upgrade path available for P1 web UI.

### 4.2 LangGraph for Agent Orchestration

*   **Why:** Provides stateful graph execution with native streaming (`astream_events()`), built-in checkpointing (`AsyncPostgresSaver`), and conditional routing.
*   **Trade-off:** Couples agent logic to LangChain ecosystem. Acceptable given the streaming and checkpointing benefits.

### 4.3 Ollama for LLM

*   **Why:** Local LLM hosting eliminates API costs and latency to external providers during development. Model: llama3.2:3b with temperature=0 for deterministic output.
*   **Trade-off:** Limited model capability compared to cloud providers. Provider-agnostic via LangChain's `ChatModel` interface allows future migration.

### 4.4 MCP for Tool Execution

*   **Why:** Standardized JSON-RPC 2.0 protocol for tool discovery and execution. Subprocess isolation provides security boundary.
*   **Trade-off:** Subprocess management adds complexity. Each MCP server is a separate process communicating via stdin/stdout.

### 4.5 PostgreSQL for All Persistence

*   **Why:** Single database handles events (relational), checkpoints (LangGraph's `AsyncPostgresSaver`), and knowledge graph (Apache AGE extension). Reduces infrastructure complexity.
*   **Trade-off:** AGE extension adds Docker image complexity. MVP uses hardcoded graph queries.

---

## 5. External Dependencies

### 5.1 Infrastructure

*   **PostgreSQL 16:** Event storage, checkpoint persistence, knowledge graph (AGE). Port 5433.
*   **Ollama:** Local LLM runtime. Port 11434. Model pulled on first use.

### 5.2 Libraries

*   **LangGraph + LangChain:** Agent orchestration and LLM abstraction.
*   **FastAPI:** HTTP framework for all services.
*   **discord.py:** Discord WebSocket client.
*   **asyncpg:** Async PostgreSQL driver.
*   **httpx:** Async HTTP client for inter-service communication.
*   **structlog:** Structured logging (via `libs/agentic-common`).
*   **Pydantic:** Schema validation across all services.

---

## 6. Operational Considerations

### 6.1 Error Handling

*   **Orchestrator failure:** Discord Service receives HTTP error, sends error message to Discord channel.
*   **Execution Service failure:** Orchestrator catches tool execution errors, feeds error back to LLM as observation.
*   **Context Service failure:** Orchestrator logs warning but continues processing (event logging is non-blocking for the user flow).
*   **Discord rate limits:** Debounced message editing (1s interval) stays well within Discord's rate limits.

### 6.2 Safety & Security

*   **Path Validation:** Execution Service validates all filesystem paths against a sandbox directory. Path traversal attempts are rejected.
*   **Process Isolation:** MCP servers run as separate subprocesses with controlled environments.
*   **Service Tokens:** Discord Service authenticates to Orchestrator via service token header.

### 6.3 Observability

*   **Structured Logging:** All services use `structlog` via `libs/agentic-common` with correlation ID propagation.
*   **Event Audit Trail:** Context Service stores immutable event log for every agent invocation.
*   **Health Checks:** All services expose `/health` endpoints for container orchestration.

---

## 7. Future Roadmap

### 7.1 Web UI (P1)

*   Add a Gateway Service for WebSocket support, authentication, and rate limiting.
*   Web clients connect via WebSocket; Gateway forwards to Orchestrator SSE.

### 7.2 Multi-Agent Architecture (P1)

*   Router agent delegates to specialized sub-agents.
*   Agent Registry Service for configuration management.

### 7.3 Additional Platform Adapters (P1)

*   Slack Service, Email Service following the same Platform Adapter pattern as Discord Service.

### 7.4 Advanced Knowledge Retrieval (P1)

*   Dynamic Cypher query generation for Apache AGE.
*   pgvector integration for semantic search.
