# Discord Service Design

---

## 0. Customer Purpose & High-Level Overview

The **Discord Service** is an inbound Platform Adapter that maintains a persistent WebSocket connection to Discord, normalizes incoming messages to the canonical `InternalEvent` schema, and forwards them to the Orchestrator Service via HTTP.

**Response delivery** is handled by the Orchestrator via **Discord MCP tools** — the agent decides how and when to respond to Discord using `discord_send_message`, `discord_edit_message`, and `discord_add_reaction` tools executed through the Execution Service.

### 0.1 Glossary

*   **Discord Service:** Inbound Platform Adapter for Discord. Maintains WebSocket to Discord, forwards events to Orchestrator. Port 8003.
*   **Platform Adapter:** A service that handles communication with an external platform. The Discord Service handles inbound only; outbound is via MCP tools.
*   **Discord MCP Server:** A stdin/stdout JSON-RPC 2.0 server running inside the Execution Service that exposes Discord REST API actions as MCP tools (`discord_send_message`, `discord_edit_message`, `discord_add_reaction`).
*   **InternalEvent:** The canonical Pydantic schema for normalized events. Includes correlation_id, source, content, routing context, and metadata.
*   **RoutingContext:** Pydantic model containing reply_channel_id, reply_thread_id, forward destinations, and conversation context.
*   **GatewayClient:** HTTP client that sends events to the Orchestrator's `/process` endpoint (fire-and-forget).
*   **DiscordGatewayHandler:** Subclass of `discord.Client` that handles incoming Discord events and forwards them to the Orchestrator.

### 0.2 Core Value Propositions

1.  **Real-Time Responsiveness:** Persistent WebSocket for low-latency message reception.
2.  **Platform Isolation:** Confines Discord-specific dependencies (`discord.py`) to a single service.
3.  **Agent-Controlled Responses:** The agent decides how to respond via MCP tool calls, enabling richer interaction patterns (multi-message responses, reactions, edits).

### 0.3 High-Level Strategy

*   **MVP (P0 - Steel Thread):** Discord bot that receives text messages and forwards them to the Orchestrator. Responses delivered via Discord MCP tools (with automatic fallback in the Orchestrator).
*   **Production (P1 - Extension):** Rich media support, slash commands, reaction handling, multi-channel threading.

---

## 1. System Requirements

1.  **Maintain Connectivity:** Persistent WebSocket connection to Discord via `discord.py` with automatic reconnection.
2.  **Normalize Events:** Convert `discord.Message` to `InternalEvent` with full metadata extraction (including `source: "discord"` for Orchestrator fallback detection).
3.  **Forward Events:** Fire-and-forget event forwarding to Orchestrator `/process` endpoint.
4.  **Retry on Failure:** Exponential backoff (3 attempts) for Orchestrator communication errors.
5.  **Health Reporting:** Separate FastAPI health server for container orchestration.

---

## 2. Architecture & Internal Design

### 2.1 Component Overview

```
┌─────────────────────────────────────────────────────┐
│                  Discord Service                     │
│                                                      │
│  ┌──────────────────────┐  ┌──────────────────────┐ │
│  │ DiscordGatewayHandler│  │   Health Server      │ │
│  │   (discord.Client)   │  │   (FastAPI :8003)    │ │
│  │                      │  │   /health, /ready    │ │
│  │  on_message()        │  └──────────────────────┘ │
│  │  on_message_edit()   │                            │
│  │  on_reaction_add()   │  ┌──────────────────────┐ │
│  │  _normalize_message()│  │   GatewayClient      │ │
│  └──────────┬───────────┘  │   (httpx async)      │ │
│             │              │   send_event()        │ │
│             └──────────────┤   (fire-and-forget)   │ │
│                            └──────────────────────┘ │
└─────────────────────────────────────────────────────┘
         │                              │
         │ WebSocket (inbound)          │ HTTP POST /process
         ▼                              ▼
    Discord Gateway              Orchestrator Service
                                        │
                                        │ tool_call: discord_send_message
                                        ▼
                                 Execution Service
                                        │
                                        │ JSON-RPC (stdio)
                                        ▼
                                 Discord MCP Server
                                        │
                                        │ REST API
                                        ▼
                                 Discord REST API
```

### 2.2 DiscordGatewayHandler

*   **Role:** Receive Discord events via WebSocket and forward to Orchestrator.
*   **Extends:** `discord.Client`
*   **Intents:** `message_content`, `guild_messages`, `dm_messages`
*   **Responsibilities:**
    *   **`on_message()`** — Primary handler. Ignores bot messages, normalizes to InternalEvent, fire-and-forget via `asyncio.create_task()`.
    *   **`_forward_event()`** — Background task that calls `GatewayClient.send_event()`. Logs errors without raising.
    *   **`on_message_edit()`** — Stubbed for MVP. Logs edits, no processing.
    *   **`on_reaction_add()`** — Stubbed for MVP. Logs reactions, no processing.
    *   **`_normalize_message()`** — Converts `discord.Message` to `InternalEvent`.

### 2.3 Event Normalization

`_normalize_message()` extracts:

| Discord Field | InternalEvent Field | Notes |
|--------------|---------------------|-------|
| `message.id` | `source_event_id` | String |
| `message.channel.id` | `source_channel_id` | String |
| `message.author.id` | `source_user_id` | String |
| `message.author.display_name` | `source_user_name` | Display name |
| `message.content` | `content` | Raw text |
| `message.attachments` | `attachments` | List of {id, filename, url, content_type, size} |
| `message.channel.id` | `routing.reply_channel_id` | For response delivery |
| `message.thread` | `routing.reply_thread_id` | If threaded |
| `message.guild` | `metadata.guild_id/name` | Server context |
| `message.mentions` | `metadata.mentions` | List of user IDs |
| (hardcoded) | `metadata.source` | Always `"discord"` — used by Orchestrator fallback |
| (auto-generated) | `correlation_id` | UUID for distributed tracing |

### 2.4 GatewayClient

*   **Role:** HTTP client for Orchestrator Service communication.
*   **Base URL:** Configurable via `GATEWAY_SERVICE_URL` environment variable.
*   **Auth:** JWT Bearer token via `Authorization` header (generated from shared secret).
*   **Timeout:** 120 seconds (agent processing + MCP tool calls can take time).
*   **Methods:**
    *   **`send_event(event)`** — POST to `/process`, waits for completion (fire-and-forget from the handler's perspective via `asyncio.create_task()`). Retry with exponential backoff (3 attempts, 4-10s delays).
*   **Error Handling:** Catches `HTTPStatusError` and `RequestError` with detailed structured logging.

### 2.5 Response Delivery (via MCP)

Response delivery is **not** handled by the Discord Service. Instead:

```
1. User sends message in Discord
2. Discord Service normalizes to InternalEvent, forwards to Orchestrator
3. Orchestrator invokes agent graph (LangGraph)
4. Agent calls discord_send_message tool (via Execution Service → Discord MCP Server)
5. Discord MCP Server calls Discord REST API → message appears in channel
6. Fallback: if agent didn't call discord_send_message, Orchestrator auto-delivers
```

The **fallback** (step 6) ensures responses always reach Discord even if the LLM generates a plain text response without calling the tool (important for llama3.2:3b reliability).

### 2.6 Discord MCP Server

Located at `services/execution-service/mcp_servers/discord_server.py`. Runs as a subprocess managed by the Execution Service's `SubprocessRuntime`.

**Tools:**

| Tool | Parameters | Description |
|------|-----------|-------------|
| `discord_send_message` | `channel_id: str, content: str` | Send a message to a channel |
| `discord_edit_message` | `channel_id: str, message_id: str, content: str` | Edit an existing message |
| `discord_add_reaction` | `channel_id: str, message_id: str, emoji: str` | Add a reaction |

*   **Protocol:** Line-delimited JSON-RPC 2.0 over stdin/stdout (same as filesystem and fetch MCP servers).
*   **API:** Discord REST API v10 via `httpx` (synchronous — MCP servers process one request at a time).
*   **Auth:** `DISCORD_BOT_TOKEN` from environment (inherited via `SubprocessRuntime`).

### 2.7 Concurrent Architecture

`main.py` runs two tasks concurrently via `asyncio.gather()`:
1.  **Discord Bot** — `discord.Client.start()` (WebSocket to Discord)
2.  **Health Server** — `uvicorn` serving FastAPI on port 8003

Signal handlers (SIGINT, SIGTERM) gracefully cancel both tasks.

---

## 3. Interfaces & Interactions

### 3.1 Inbound: Discord → Discord Service

*   **Protocol:** Discord WebSocket (managed by `discord.py`)
*   **Events Handled:** `on_message`, `on_message_edit` (stubbed), `on_reaction_add` (stubbed)
*   **Filter:** Bot messages are ignored (`message.author.bot`)

### 3.2 Outbound: Discord Service → Orchestrator

*   **Trigger:** Normalized InternalEvent from Discord message.
*   **Action:** `POST /process` (synchronous, fire-and-forget from handler via `asyncio.create_task()`).
*   **Data:**
    *   Input: `{ thread_id: str, message: str, correlation_id: str, metadata: { source: "discord", ... } }`
    *   Output: `ProcessEventResponse` (not used by Discord Service — response delivery is via MCP).
*   **Timeout:** 120 seconds.

### 3.3 Outbound: Orchestrator → Discord (via MCP)

*   **Protocol:** Discord REST API v10 (via Discord MCP Server in Execution Service)
*   **Actions:**
    *   `discord_send_message` — Agent sends response to the channel
    *   `discord_edit_message` — Agent edits a previous response
    *   `discord_add_reaction` — Agent reacts to a message
*   **Fallback:** Orchestrator auto-calls `discord_send_message` if agent didn't call it.

### 3.4 Health API (Port 8003)

*   `GET /health` — Returns `{ status: "healthy", service: "discord-service", version: "0.1.0" }`
*   `GET /ready` — Returns `{ status: "ready", service: "discord-service", version: "0.1.0" }`

### 3.5 InternalEvent Schema

```python
class InternalEvent(BaseModel):
    correlation_id: str          # UUID for tracing
    source: EventSource          # DISCORD | SLACK | TWILIO | IMAP | API
    source_event_id: str         # Discord message ID
    source_channel_id: str       # Discord channel ID
    source_user_id: str          # Discord user ID
    source_user_name: str | None # Display name
    content_type: ContentType    # TEXT | IMAGE | AUDIO | FILE | REACTION | EDIT
    content: str                 # Message text
    attachments: list[dict]      # File metadata
    routing: RoutingContext       # Reply routing info
    timestamp: datetime           # UTC
    metadata: dict                # Platform-specific data (includes source="discord")
```

---

## 4. Technology Stack & Trade-offs

### 4.1 discord.py

*   **Why:** Gold standard for Discord bots. Async-native, handles WebSocket reconnection, rate limiting, and intent management.
*   **Trade-off:** Python-only. Acceptable since all services are Python.

### 4.2 httpx (Async)

*   **Why:** Async HTTP client for forwarding events to Orchestrator.
*   **Trade-off:** Slightly more complex than `requests` but necessary for async operation.

### 4.3 Discord MCP Server (httpx sync)

*   **Why:** Uses synchronous `httpx` for Discord REST API calls inside the MCP server. MCP servers process one request at a time via stdin/stdout, so async is unnecessary.
*   **Trade-off:** No WebSocket gateway connection — only REST API. This avoids conflicts with the Discord Service's gateway connection.

### 4.4 Pydantic (InternalEvent)

*   **Why:** Schema validation ensures only well-formed events reach the Orchestrator.
*   **Trade-off:** Serialization overhead is negligible for message-rate traffic.

---

## 5. External Dependencies

### 5.1 Discord Platform

*   **Discord Gateway:** WebSocket connection for real-time events (Discord Service).
*   **Discord REST API:** Message sending/editing/reactions (Discord MCP Server via Execution Service).
*   **Requirements:** Bot Token, Application ID, Message Content Intent (privileged).

### 5.2 Orchestrator Service

*   **HTTP API:** `POST /process` (synchronous).
*   **Network:** `http://orchestrator-service:8000` (Docker) or `http://localhost:8000` (local dev).
*   **Auth:** JWT Bearer token via `Authorization` header.

### 5.3 Execution Service (Discord MCP)

*   **MCP Config:** `config/mcp_servers.json` — `discord` server entry.
*   **Environment:** `DISCORD_BOT_TOKEN` passed to Execution Service container, inherited by MCP subprocess.

---

## 6. Operational Considerations

### 6.1 Error Handling

| Scenario | Response |
|----------|----------|
| **Orchestrator Down** | Logged by `_forward_event()`. No user-facing error (fire-and-forget). |
| **Orchestrator Timeout** | Retry with exponential backoff (3 attempts). If all fail, logged. |
| **Discord MCP Error** | Agent receives tool error in message history. Orchestrator fallback may still deliver. |
| **Fallback Delivery Fails** | Logged by Orchestrator. User doesn't receive a response. |
| **Invalid Bot Token** | Fatal startup error (Discord Service). MCP tools return errors (Execution Service). |

### 6.2 Safety & Security

*   **Token Management:** Bot Token injected via environment variables to both Discord Service and Execution Service containers.
*   **Input Validation:** `InternalEvent` Pydantic validation rejects malformed data.
*   **Bot Message Filter:** `message.author.bot` check prevents self-reply loops.
*   **MCP Isolation:** Discord MCP server runs as a sandboxed subprocess with no WebSocket gateway connection.

### 6.3 Configuration

| Variable | Service | Default | Description |
|----------|---------|---------|-------------|
| `DISCORD_BOT_TOKEN` | Discord Service, Execution Service | (required) | Discord bot authentication token |
| `DISCORD_APPLICATION_ID` | Discord Service | (required) | Discord application ID |
| `GATEWAY_SERVICE_URL` | Discord Service | `http://orchestrator-service:8000` | Orchestrator Service URL |
| `SERVICE_AUTH_SECRET` | Discord Service | `dev-secret-change-me` | Shared secret for JWT auth |
| `HEALTH_PORT` | Discord Service | `8003` | Health server port |
| `LOG_LEVEL` | Discord Service | `INFO` | Logging level |
| `LOG_FORMAT` | Discord Service | `json` | Log output format |

---

## 7. Future Roadmap

### 7.1 Rich Content (P1)

*   Support image/file attachments in requests and responses.
*   Embed formatting for tool results via additional MCP tools.

### 7.2 Slash Commands (P1)

*   `/reset` — Clear conversation thread.
*   `/help` — Display available commands.
*   `/status` — Show agent status.

### 7.3 Reaction Handling (P1)

*   Process reactions as event signals (e.g., thumbs-up for approval workflows).
*   Forward as InternalEvent to Orchestrator.

### 7.4 Sharding (P1)

*   Configure `discord.py` sharding if guild count exceeds 2000.
