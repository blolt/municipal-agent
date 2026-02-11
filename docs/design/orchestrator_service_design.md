# Orchestrator Service Design

---

## 0. Customer Purpose & High-Level Overview

The **Orchestrator Service** is the central execution engine of the Municipal Agent. It hosts the LangGraph agent runtime and exposes a streaming SSE API that emits fine-grained events (reasoning tokens, tool status) as they occur.

The service is **stateless at the process level** — any instance can handle any request because conversation state is offloaded to PostgreSQL via LangGraph's `AsyncPostgresSaver`.

### 0.1 Glossary

*   **Orchestrator Service:** The microservice that hosts the LangGraph runtime and executes agent logic. Port 8000.
*   **LangGraph:** The library used to define the agent's control flow as a stateful graph with conditional routing.
*   **AsyncPostgresSaver:** LangGraph's built-in checkpointer that persists agent state to PostgreSQL after every node transition.
*   **AgentState:** A `TypedDict` containing the current conversation messages, thread ID, correlation ID, and routing decision (`next_action`).
*   **SSE (Server-Sent Events):** The streaming protocol used by the `/v1/agent/run` endpoint.
*   **ChatOllama:** LangChain's interface to Ollama, used with model `llama3.2:3b` at temperature=0.

### 0.2 Core Value Propositions

1.  **Real-Time Transparency:** Users see the agent reasoning and working in real-time via SSE streaming.
2.  **Unified Logic:** The same agent graph serves all clients (Discord, future web UI) via the same SSE endpoint.
3.  **Resumable State:** Every node transition is checkpointed, enabling multi-turn conversations that survive restarts.

### 0.3 High-Level Strategy

*   **MVP (P0 - Steel Thread):** A single agent with reasoning, tool execution, and response nodes. Ollama (llama3.2:3b) for LLM.
*   **Production (P1 - Extension):** Hierarchical multi-agent system with specialized sub-agents running as sub-graphs.

---

## 1. System Requirements

1.  **Stream by Default:** All agent invocations use `astream_events()`, emitting SSE events.
2.  **Stateless Process:** Any instance handles any request; state lives in PostgreSQL.
3.  **Synchronous Dependencies:** Call Context and Execution services via HTTP within the reasoning loop.
4.  **Checkpoint Every Step:** Persist state after every node transition for resumability.

---

## 2. Architecture & Internal Design

### 2.1 API Layer (FastAPI)

*   **`POST /v1/agent/run`** — Streaming SSE endpoint. Accepts `AgentRunRequest`, returns `StreamingResponse` with `text/event-stream`.
*   **`POST /process`** — Synchronous endpoint. Accepts message, invokes graph with `ainvoke()`, returns complete response.
*   **`GET /health`** — Health check.

### 2.2 Agent Graph (LangGraph)

The agent is a 3-node LangGraph with conditional routing:

```
                    ┌──────────┐
                    │ START    │
                    └────┬─────┘
                         │
                         ▼
                ┌────────────────┐
           ┌───▶│   reasoning    │◀───┐
           │    │ (LLM decides)  │    │
           │    └───────┬────────┘    │
           │            │             │
           │     next_action?         │
           │     ┌──────┴──────┐      │
           │     │             │      │
           │  call_tool     respond   │
           │     │             │      │
           │     ▼             ▼      │
           │ ┌──────────┐ ┌────────┐  │
           └─┤tool_call │ │respond │  │
             │(execute) │ │(done)  │  │
             └──────────┘ └───┬────┘  │
                              │       │
                              ▼       │
                         ┌────────┐   │
                         │  END   │   │
                         └────────┘   │
```

**Nodes:**

*   **`reasoning`** — Invokes ChatOllama (llama3.2:3b, temperature=0) with conversation history. The LLM response is inspected for tool_calls. Sets `next_action` to `"call_tool"` or `"respond"`.
*   **`tool_call`** — Extracts tool name and arguments from the LLM response. Calls `ExecutionServiceClient.execute_tool()`. Appends the tool result as a `ToolMessage` to conversation history. Routes back to `reasoning`.
*   **`respond`** — Terminal node. Marks the graph execution as complete.

**Conditional Routing:** After `reasoning`, the `next_action` field in `AgentState` determines whether to proceed to `tool_call` or `respond`.

### 2.3 Agent State

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # Conversation history with auto-reduction
    thread_id: str                            # Checkpoint key for conversation continuity
    correlation_id: str                       # Links to Context Service event log
    next_action: str                          # Routing: "call_tool" or "respond"
```

### 2.4 Integration Clients

*   **`ContextServiceClient`** — Async HTTP client (httpx) to Context Service.
    *   `POST /events` — Log agent processing events for audit trail.
*   **`ExecutionServiceClient`** — Async HTTP client (httpx) to Execution Service.
    *   `GET /tools` — Discover available MCP tools at startup.
    *   `POST /execute` — Execute a tool with name and arguments.

### 2.5 Streaming Event Mapping

LangGraph's `astream_events()` emits internal events that are mapped to the SSE schema:

| LangGraph Event | SSE Event | Data |
|----------------|-----------|------|
| `on_chat_model_stream` | `thinking` | `{ content: token_text }` |
| `on_tool_start` | `tool_start` | `{ name: tool_name, args: input_dict }` |
| `on_tool_end` | `tool_result` | `{ name: tool_name, result: output_str }` |
| (graph complete) | `done` | `{ usage: { tokens: 0 } }` |

### 2.6 Lifespan Management

On startup (`@asynccontextmanager` lifespan):
1.  Initialize `AsyncPostgresSaver` with database connection.
2.  Create `ContextServiceClient` and `ExecutionServiceClient`.
3.  Compile the agent graph with the checkpointer.

On shutdown:
1.  Close HTTP clients.
2.  Close database connections.

---

## 3. Interfaces & Interactions

### 3.1 Inbound: Discord Service → Orchestrator

*   **Trigger:** Discord Service receives a user message.
*   **Action:** `POST /v1/agent/run` with SSE streaming.
*   **Data:**
    *   Input: `{ input: str, thread_id: str, correlation_id?: str, config?: dict }`
    *   Output: SSE stream of events.

### 3.2 Outbound: Orchestrator → Execution Service

*   **Trigger:** LLM requests a tool call during reasoning.
*   **Action:** `POST /execute` (synchronous HTTP).
*   **Data:**
    *   Input: `{ tool_name: str, arguments: dict, timeout?: float }`
    *   Output: `{ status: str, output: any, execution_time_ms: float }`

### 3.3 Outbound: Orchestrator → Context Service

*   **Trigger:** Agent invocation start, completion, or error.
*   **Action:** `POST /events` (synchronous HTTP, non-blocking for user flow).
*   **Data:** `InternalEvent` with correlation_id, event_type, source, payload.

### 3.4 SSE Event Schema

```json
{ "type": "thinking", "content": "string" }
{ "type": "tool_start", "name": "string", "args": {} }
{ "type": "tool_result", "name": "string", "result": "string" }
{ "type": "done", "usage": { "tokens": 0 } }
```

---

## 4. Technology Stack & Trade-offs

### 4.1 LangGraph

*   **Why:** Native streaming via `astream_events()`, built-in checkpointing with `AsyncPostgresSaver`, conditional routing.
*   **Trade-off:** Python-centric, couples to LangChain ecosystem.

### 4.2 FastAPI (StreamingResponse)

*   **Why:** Standard Python async framework. Generator-based streaming maps directly to LangGraph's async generators.
*   **Trade-off:** HTTP/1.1 chunked transfer is verbose.

### 4.3 Ollama (ChatOllama)

*   **Why:** Local LLM with zero API cost. Model `llama3.2:3b` with `temperature=0` for deterministic output.
*   **Trade-off:** Limited capability vs cloud providers. Swappable via LangChain's `ChatModel` interface.

### 4.4 Synchronous RPC to Downstream Services

*   **Why:** The agent cannot proceed without tool results. Async queues would add latency and complexity.
*   **Trade-off:** If Execution Service is down, the agent blocks. Mitigated by timeouts.

---

## 5. External Dependencies

### 5.1 Infrastructure

*   **PostgreSQL (port 5433):** `AsyncPostgresSaver` for checkpoint persistence.
*   **Ollama (port 11434):** LLM runtime.

### 5.2 Internal Services

*   **Context Service (port 8001):** Event logging.
*   **Execution Service (port 8002):** Tool discovery and execution.

---

## 6. Operational Considerations

### 6.1 Error Handling

*   **Tool Errors:** Error returned to agent as an observation. Agent can retry with corrected arguments or report failure.
*   **LLM Errors:** Caught and logged. SSE stream terminated with error event.
*   **Context Service Errors:** Logged as warning, does not block user flow.

### 6.2 Safety

*   **Recursion Limit:** LangGraph enforces maximum graph steps to prevent infinite tool-call loops.
*   **Timeouts:** Configurable timeouts on tool execution and LLM calls.
*   **Service Token Auth:** Validates internal service tokens from callers.

### 6.3 Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://...localhost:5433/...` | PostgreSQL connection |
| `CONTEXT_SERVICE_URL` | `http://localhost:8001` | Context Service base URL |
| `EXECUTION_SERVICE_URL` | `http://localhost:8002` | Execution Service base URL |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API base URL |
| `PORT` | `8000` | Service port |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## 7. Future Roadmap

### 7.1 Sub-Agents (P1)

*   Define specialized sub-graphs (Coding Agent, Research Agent).
*   Route sub-agent events through the main SSE stream.

### 7.2 Approval Workflows (P1)

*   Emit `approval_required` events for high-risk actions.
*   Suspend graph execution, resume from checkpoint after approval.

### 7.3 Provider Flexibility (P1)

*   Swap Ollama for cloud LLM providers (OpenAI, Anthropic) via LangChain `ChatModel` interface.
