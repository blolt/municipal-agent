# Municipal Agent

An AI-powered municipal zoning assistant built on a streaming microservices architecture.

## Architecture

**Pattern:** Streaming-First - the Orchestrator Service is the central "brain" that always executes in streaming mode.

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

Single execution path:
- **Streaming endpoint:** Clients (Web, Discord Service) connect to `Orchestrator` via SSE.

## Services

| Service | Port | Purpose |
|---------|------|---------|
| **orchestrator-service** | 8000 | Core Agent Brain. Streaming API. |
| **context-service** | 8001 | Event logging, PostgreSQL + AGE + pgvector |
| **execution-service** | 8002 | Sandboxed MCP tool execution |
| **discord-service** | 8003 | Discord Bot Integration (client of Orchestrator) |

## Tech Stack

- **Language:** Python 3.12
- **Framework:** FastAPI (all services)
- **Agent Framework:** LangGraph + LangChain
- **LLM:** Ollama (llama3.2:3b for MVP)
- **Database:** PostgreSQL 16 with Apache AGE (graph) + pgvector (embeddings)
- **Tool Protocol:** MCP (Model Context Protocol)
- **Streaming:** SSE (Server-Sent Events)

## Project Structure

```
services/
├── orchestrator-service/   # Core "Brain". HTTP API + LangGraph
├── context-service/        # State + event persistence
├── execution-service/      # Tool execution sandbox
└── discord-service/        # Discord integration
```

## Shared Libraries

### `libs/agentic-common`
Shared utilities used by all services:
- **Logging**: Structured logging via `structlog`
- Import: `from agentic_common import setup_logging, get_logger, bind_context`

## Current Status

**Architecture:** Single Stream-First Orchestrator.

### Completed
- **Context Service** (event logging, state management)
- **Execution Service** (MCP tool execution, sandboxing)
- **Orchestrator Service** (Streaming API, LangGraph integration)
- **Discord Service** (Basic scaffolding, integration pending)

### In Progress
- verifying Discord Service -> Orchestrator integration
- end-to-end testing

## Testing

**Framework:** pytest (all tests). Test markers defined in `pytest.ini`.

```bash
# Unit tests (per-service, no Docker required)
cd services/execution-service && pytest tests/unit/ -v
cd services/context-service && pytest tests/ -v
cd services/discord-service && pytest tests/ -v

# Integration tests (requires tests/integration/docker-compose.test.yml)
# Note: This will spin up a separate test environment
docker compose -f tests/integration/docker-compose.test.yml up -d
pytest tests/integration/ -v
docker compose -f tests/integration/docker-compose.test.yml down -v

# E2E tests (requires full docker-compose.yml stack or test stack)
# For smoke tests (fastest):
docker compose -f tests/integration/docker-compose.test.yml up -d
pytest tests/e2e/test_smoke.py -v
docker compose -f tests/integration/docker-compose.test.yml down -v
```

**Test markers:** `e2e`, `smoke`, `golden_path`, `slow`

## Common Commands

```bash
# Start all services
docker compose up -d

# Run service tests
cd services/<service-name> && pytest

# Start individual service (dev)
cd services/<service-name> && uvicorn src.main:app --reload --port <port>
```
