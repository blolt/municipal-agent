# Agentic Bridge

A microservices architecture for autonomous AI agents that bridges unstructured human intent with deterministic business logic. The system receives natural language input (via Discord or HTTP), routes it through a streaming AI agent powered by LangGraph, and executes tools via the Model Context Protocol (MCP).

The Orchestrator Service is the central "brain" — a LangGraph agent that reasons, calls tools, and responds, all delivered as a real-time SSE stream.

## Architecture

```
                               ┌─────────────────────────┐
                               │   Orchestrator Service  │
                               │  ┌───────────────────┐  │
                               │  │   Agent Graph     │  │
                               │  │  (LangGraph)      │  │
                               │  └─────────┬─────────┘  │
                               └────────────┼────────────┘
                                            │
                                            ▼
                                     Streaming API
                               (SSE /v1/agent/run)
                                            │
                   ┌────────────────────────┴───────────────────────┐
                   │                                                │
                   ▼                                                ▼
            ┌─────────────┐                                  ┌─────────────┐
            │  Web Client │                                  │   Discord   │
            │  (Browser)  │                                  │   Service   │
            └─────────────┘                                  └──────┬──────┘
                                                                    │
                                                                    ▼
                                                             Discord Gateway
```

**Single execution path:** All clients connect to the Orchestrator via SSE at `/v1/agent/run`. The Orchestrator streams events (`thinking`, `tool_start`, `tool_result`, `done`) back in real time.

## Services

| Service | Port | Purpose |
|---------|------|---------|
| **orchestrator-service** | 8000 | Core Agent Brain — LangGraph agent with streaming SSE API |
| **context-service** | 8001 | Event logging and state persistence (PostgreSQL + AGE + pgvector) |
| **execution-service** | 8002 | Sandboxed MCP tool execution (JSON-RPC 2.0 over stdio) |
| **discord-service** | 8003 | Discord bot integration — SSE client of the Orchestrator |

### Infrastructure

| Service | Port | Purpose |
|---------|------|---------|
| **PostgreSQL 16** | 5433 | Database with Apache AGE (graph) + pgvector (embeddings) |
| **Ollama** | 11434 | Local LLM inference (llama3.2:3b for MVP) |

## Tech Stack

- **Language:** Python 3.12
- **Framework:** FastAPI (all services)
- **Agent Framework:** LangGraph + LangChain
- **LLM:** Ollama (llama3.2:3b for MVP)
- **Database:** PostgreSQL 16 with Apache AGE (graph) + pgvector (embeddings)
- **Tool Protocol:** MCP (Model Context Protocol) — JSON-RPC 2.0 over stdio
- **Streaming:** SSE (Server-Sent Events)
- **Logging:** structlog (structured logging via shared library)

## Quick Start

```bash
# Clone and configure
cp .env.example .env
# Edit .env with your Discord bot token (optional — needed for Discord integration)

# Start all services
docker compose up -d

# Verify health
curl http://localhost:8000/health  # Orchestrator
curl http://localhost:8001/health  # Context
curl http://localhost:8002/health  # Execution
curl http://localhost:8003/health  # Discord

# Send a test message (streaming)
curl -N http://localhost:8000/v1/agent/run \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "thread_id": "test-1"}'
```

## Development Setup

**Prerequisites:** Python 3.12, [Poetry](https://python-poetry.org/), Docker

```bash
# Install dependencies (from project root)
poetry install

# Start infrastructure only
docker compose up postgres ollama -d

# Run a service locally (e.g., context-service)
cd services/context-service && uvicorn src.main:app --reload --port 8001
```

Each service is independently runnable. For local development, start the infrastructure containers (PostgreSQL, Ollama) and run individual services with `uvicorn`.

## Testing

**Framework:** pytest. Test markers defined in `pytest.ini`.

```bash
# Unit tests (per-service, no Docker required)
cd services/execution-service && pytest tests/unit/ -v
cd services/context-service && pytest tests/ -v
cd services/discord-service && pytest tests/ -v

# Integration tests (requires Docker test environment)
docker compose -f tests/integration/docker-compose.test.yml up -d
pytest tests/integration/ -v
docker compose -f tests/integration/docker-compose.test.yml down -v

# E2E smoke tests
docker compose -f tests/integration/docker-compose.test.yml up -d
pytest tests/e2e/test_smoke.py -v
docker compose -f tests/integration/docker-compose.test.yml down -v
```

**Test markers:** `e2e`, `smoke`, `golden_path`, `slow`

## Project Structure

```
agentic-bridge/
├── services/
│   ├── orchestrator-service/   # Core "Brain" — HTTP API + LangGraph agent
│   ├── context-service/        # Event logging + state persistence
│   ├── execution-service/      # MCP tool execution sandbox
│   └── discord-service/        # Discord bot integration
├── libs/
│   └── agentic-common/         # Shared library (structlog logging)
├── tests/
│   ├── integration/            # Cross-service integration tests
│   └── e2e/                    # End-to-end smoke + golden path tests
├── docs/
│   └── design/                 # Architecture, service design, and testing docs
├── docker-compose.yml          # Full stack (all services + infrastructure)
└── pyproject.toml              # Root Poetry config
```

## Shared Libraries

### `libs/agentic-common`

Shared utilities used by all services:

```python
from agentic_common import setup_logging, get_logger, bind_context
```

- **Logging:** Structured logging via `structlog` with correlation ID propagation

## Future Plans

- MCP tool servers (currently bundled with execution-service) may be spun off to separate public repositories as standalone MCP servers
- GCP Cloud Run deployment (reference architecture in `docs/design/architecture/gcp_deployment.md`)
- Sidecar deployment pattern for tighter service coupling (design in `docs/design/architecture/sidecar_deployment.md`)
