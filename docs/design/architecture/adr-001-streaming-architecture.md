# ADR-001: Streaming vs Batch Agent Architecture

**Status:** Accepted
**Date:** 2026-01-24
**Accepted:** 2026-02-07
**Decision:** Option A — Add streaming endpoint to Orchestrator Service

## Context

The Agentic Bridge system currently supports **asynchronous batch processing** via message queues:

```
[Discord/Slack/Email] → Ingress → Queue → Orchestrator → Queue → Egress
```

This works well for platforms with inherent async expectations (email, Discord DMs). However, we need to support **real-time streaming** for web/app interfaces where users expect a Claude Code-like experience:

- Immediate feedback ("thinking" indicators)
- Token-by-token response streaming
- Live tool execution status
- Mid-stream approval requests
- Continued agent work after partial responses

## Decision Drivers

1. **User Experience**: Web users expect real-time feedback, not "please wait" spinners
2. **Code Reuse**: Minimize dual maintenance between streaming and batch paths
3. **Logical Separation**: Keep concerns cleanly separated (auth, transport, orchestration)
4. **Operational Simplicity**: Avoid unnecessary service proliferation
5. **Industrial Use Cases**: Support domain-specific tools and indexed context

## Options Analysis

### Option A: Add Streaming Endpoint to Orchestrator Service

**Description**: Extend the existing Orchestrator with a `/stream` SSE endpoint that uses LangGraph's `astream_events()`.

```
Batch Path:  Ingress → Queue → Orchestrator.process_queue_event() → Queue → Egress
Stream Path: Web UI → Orchestrator /stream (SSE) → Direct response
```

**Implementation**:
```python
@app.get("/stream")
async def stream_response(request: StreamRequest):
    async def event_generator():
        async for event in agent_graph.astream_events(input, version="v2"):
            if event["event"] == "on_chat_model_stream":
                yield f"data: {json.dumps({'type': 'token', 'content': event['data']})}\n\n"
            elif event["event"] == "on_tool_start":
                yield f"data: {json.dumps({'type': 'tool_start', 'name': event['name']})}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**Pros**:
- ✅ Maximum code reuse (same graph, nodes, state, checkpointer)
- ✅ No new service to deploy/monitor
- ✅ LangGraph natively supports streaming via `astream_events()`
- ✅ Simplest operational model

**Cons**:
- ❌ Mixes transport concerns (HTTP/SSE) with orchestration logic
- ❌ Auth, rate limiting, session management added to orchestrator
- ❌ Harder to scale streaming and batch independently
- ❌ WebSocket support would require significant changes

**Code Reuse**: ~95% (same graph, nodes, state)
**New Code**: SSE endpoint, event formatting

---

### Option B: New Gateway Service (Thin Proxy)

**Description**: Create a lightweight Gateway Service that handles web connections and proxies to Orchestrator.

```
Batch Path:  Ingress → Queue → Orchestrator → Queue → Egress
Stream Path: Web UI → Gateway (SSE/WS) → Orchestrator /stream → Gateway → Web UI
```

**Implementation**: Gateway calls Orchestrator's streaming endpoint and forwards events to clients.

**Pros**:
- ✅ Clean separation of concerns (auth, sessions in Gateway)
- ✅ Can add WebSocket support without touching Orchestrator
- ✅ Independent scaling of web tier
- ✅ Orchestrator still owns all agent logic

**Cons**:
- ❌ New service to deploy/monitor
- ❌ Extra network hop adds latency
- ❌ Still requires streaming endpoint in Orchestrator
- ❌ Gateway becomes "dumb pipe" with limited value

**Code Reuse**: ~90% (Orchestrator unchanged, new Gateway)
**New Code**: Gateway service, SSE proxy logic

---

### Option C: New Gateway Service (Smart Streaming)

**Description**: Gateway Service owns web connections AND directly invokes the shared LangGraph agent.

```
Batch Path:  Ingress → Queue → Orchestrator → Queue → Egress
Stream Path: Web UI → Gateway (SSE/WS) → [Shared Agent Graph] → Gateway → Web UI
```

**Key Insight**: Extract the agent graph (nodes, state, tools) into a shared library that both Orchestrator and Gateway import.

```
libs/
├── agentic-common/           # Logging, utilities (exists)
└── agentic-agent/            # NEW: Shared agent components
    ├── graph.py              # Graph definition
    ├── nodes.py              # Node implementations
    ├── state.py              # AgentState TypedDict
    └── tools.py              # Tool definitions

services/
├── orchestrator-service/     # Batch: Queue consumer, uses agentic-agent
└── gateway-service/          # Stream: SSE/WS, uses agentic-agent
```

**Pros**:
- ✅ Clean separation: Gateway owns streaming, Orchestrator owns batch
- ✅ **Single source of truth** for agent logic (shared library)
- ✅ No network hop for streaming (Gateway runs graph directly)
- ✅ Gateway can handle auth, sessions, rate limiting
- ✅ WebSocket support straightforward
- ✅ Independent scaling and deployment

**Cons**:
- ❌ New service to deploy/monitor
- ❌ Shared library requires careful versioning
- ❌ Two services need database access (checkpointer)
- ❌ More complex initial setup

**Code Reuse**: ~85% (shared agent library)
**New Code**: Gateway service, shared library extraction

---

### Option D: Unified Service with Mode Switch

**Description**: Single service handles both batch (queue) and streaming (HTTP) based on entry point.

```
Unified Orchestrator:
  - Queue Consumer → process_batch() → Queue Publisher
  - HTTP /stream   → process_stream() → SSE Response

Both paths use: shared_agent_graph.invoke() or .astream_events()
```

**Pros**:
- ✅ Single service, single deployment
- ✅ Maximum code reuse (100% shared graph)
- ✅ Simpler operations

**Cons**:
- ❌ Service becomes "fat" with mixed concerns
- ❌ Auth/session logic mixed with queue consumption
- ❌ Cannot scale streaming and batch independently
- ❌ Blast radius: streaming bugs can affect batch processing

**Code Reuse**: ~100%
**New Code**: SSE endpoint, mode detection

---

## LangGraph Streaming Capabilities

LangGraph natively supports streaming via multiple modes:

| Mode | Description | Use Case |
|------|-------------|----------|
| `values` | Full state after each node | Debugging, state inspection |
| `updates` | State deltas after each node | Efficient UI updates |
| `messages` | LLM tokens + metadata | Chat UI token streaming |
| `custom` | User-defined data via `get_stream_writer()` | Progress updates, tool status |
| `debug` | Maximum detail | Development, tracing |

**Key APIs**:
- `graph.astream(input, stream_mode=["updates", "custom"])` - Async streaming
- `graph.astream_events(input, version="v2")` - Fine-grained event stream
- `get_stream_writer()` - Emit custom data from nodes

**Implication**: The existing `agent_graph` can stream with zero changes to node logic—only the invocation pattern changes from `ainvoke()` to `astream_events()`.

---

## Streaming Protocol Comparison

| Protocol | Direction | Complexity | Browser Support | Use Case |
|----------|-----------|------------|-----------------|----------|
| **SSE** | Server→Client | Low | Native | Token streaming, status updates |
| **WebSocket** | Bidirectional | Medium | Native | Mid-stream user input, cancellation |
| **HTTP/2 Push** | Server→Client | Low | Native | Alternative to SSE |
| **gRPC Streaming** | Bidirectional | High | Via proxy | Service-to-service |

**Recommendation**: Start with **SSE** for simplicity. Add WebSocket later if bidirectional needs emerge (e.g., mid-stream cancellation, follow-up questions before completion).

---

## Shared Component Analysis

Components that can be shared between streaming and batch paths:

| Component | Shareable? | Notes |
|-----------|------------|-------|
| `AgentState` | ✅ Yes | TypedDict, no dependencies |
| `graph.py` | ✅ Yes | Graph structure, node wiring |
| `nodes.py` | ✅ Yes | Node implementations |
| `ExecutionServiceClient` | ✅ Yes | Tool execution |
| `ContextServiceClient` | ✅ Yes | Event logging |
| `AsyncPostgresSaver` | ⚠️ Partial | Both services need DB access |
| Queue consumer logic | ❌ No | Batch-specific |
| SSE/WebSocket handling | ❌ No | Stream-specific |

**Minimum Shared Library** (`libs/agentic-agent/`):
- `state.py` - AgentState definition
- `graph.py` - Graph factory function
- `nodes.py` - Node implementations
- `tools.py` - Tool definitions (future)

---

## Recommendation

### Short-term: Option A (Add Streaming to Orchestrator)

For MVP, add a `/stream` SSE endpoint to the existing Orchestrator:

1. Minimal new code
2. No new services to deploy
3. Validates streaming UX with real users
4. LangGraph's `astream_events()` does the heavy lifting

### Medium-term: Migrate to Option C (Shared Library + Gateway)

Once streaming is validated:

1. Extract agent logic to `libs/agentic-agent/`
2. Create Gateway Service for web/app clients
3. Refactor Orchestrator to use shared library
4. Add WebSocket support if needed

This provides a migration path that:
- Starts simple and validates assumptions
- Evolves to clean separation as complexity grows
- Maintains single source of truth for agent logic

---

## Event Schema for Streaming

Proposed SSE event types for web clients:

```typescript
type StreamEvent =
  | { type: "thinking"; content: string }           // Agent reasoning
  | { type: "token"; content: string }              // LLM output token
  | { type: "tool_start"; name: string; args: object }
  | { type: "tool_progress"; name: string; progress: number }
  | { type: "tool_result"; name: string; result: object }
  | { type: "approval_required"; action: string; options: string[] }
  | { type: "error"; message: string }
  | { type: "done"; summary: string }
```

---

## Open Questions

1. **Checkpointer Sharing**: If both Gateway and Orchestrator run the graph, how do we handle checkpoint conflicts? Options:
   - Read-only checkpoints for Gateway (streaming is stateless)
   - Separate checkpoint namespaces
   - Gateway always creates new threads

2. **Authentication**: How do web users authenticate?
   - JWT tokens passed in SSE connection
   - Session cookies
   - API keys for B2B

3. **Rate Limiting**: Where is rate limiting enforced?
   - Gateway (recommended for web)
   - Orchestrator
   - Both (defense in depth)

4. **Approval Flow**: How do mid-stream approvals work?
   - Gateway holds connection open, waits for user response
   - Agent suspends, resumes from checkpoint after approval

---

## Decision

**Option A was implemented for MVP.** The Orchestrator Service exposes a streaming SSE endpoint at `POST /v1/agent/run` using LangGraph's `astream_events()`.

### Implementation Notes

*   **Endpoint:** `POST /v1/agent/run` in `orchestrator_service/main.py`
*   **Streaming:** FastAPI `StreamingResponse` with `text/event-stream` media type
*   **Event Mapping:** LangGraph events mapped to SSE schema:
    *   `on_chat_model_stream` → `{"type": "thinking", "content": ...}`
    *   `on_tool_start` → `{"type": "tool_start", "name": ..., "args": ...}`
    *   `on_tool_end` → `{"type": "tool_result", "name": ..., "result": ...}`
    *   Completion → `{"type": "done", "usage": {"tokens": 0}}`
*   **Client:** Discord Service consumes this stream via `OrchestratorClient.stream_event()` using httpx
*   **Batch Fallback:** `POST /process` endpoint provides synchronous (non-streaming) access to the same graph

### Why Option A Was Sufficient

The queue-based batch path (Ingress → Queue → Orchestrator → Queue → Egress) was eliminated entirely. Discord Service acts as a Platform Adapter that calls the Orchestrator's SSE endpoint directly and handles response delivery itself. This made the Gateway Service (Option B/C) unnecessary for MVP — there is no separate web client requiring WebSocket multiplexing.

Option C (shared agent library + Gateway) remains the recommended path if a web UI is added in P1.

---

## References

- [LangGraph Streaming Documentation](https://docs.langchain.com/oss/python/langgraph/streaming)
- [LangGraph Streaming 101: 5 Modes](https://dev.to/sreeni5018/langgraph-streaming-101-5-modes-to-build-responsive-ai-applications-4p3f)
- [Beyond Request-Response: Real-time Bidirectional Streaming Multi-agent Systems](https://developers.googleblog.com/en/beyond-request-response-architecting-real-time-bidirectional-streaming-multi-agent-system/)
- [AI Agent Architecture: Best Practices](https://www.patronus.ai/ai-agent-development/ai-agent-architecture)
- [Mastering LangGraph Streaming](https://sparkco.ai/blog/mastering-langgraph-streaming-advanced-techniques-and-best-practices)
