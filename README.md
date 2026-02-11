# Municipal Agent

An AI-powered municipal zoning assistant that helps residents, developers, and city staff navigate local zoning codes and land use regulations. Ask questions in plain English — the agent fetches municipal ordinances, builds a knowledge graph, and answers with citations to specific code sections.

Built on a streaming microservices architecture: a LangGraph agent orchestrates tool calls via MCP (Model Context Protocol), stores structured zoning data in an Apache AGE property graph, and delivers real-time responses over SSE.

## What It Does

- **Look up zoning rules**: "What uses are permitted in the R1 district?"
- **Check dimensional standards**: "What's the minimum lot size for a duplex in Detroit?"
- **Search across codes**: "What does the code say about accessory dwelling units?"
- **Navigate code structure**: Browse articles, divisions, and sections of any municipality's ordinances
- **Understand definitions**: "How does the zoning code define 'mixed-use development'?"

The agent automatically fetches code from the [Municode](https://municode.com/) API, ingests it into a knowledge graph, builds recursive summaries, and queries the graph to answer questions — all transparently via tool calls streamed to the user.

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
| **context-service** | 8001 | Event logging, state persistence, knowledge graph (PostgreSQL + AGE) |
| **execution-service** | 8002 | Sandboxed MCP tool execution (JSON-RPC 2.0 over stdio) |
| **discord-service** | 8003 | Discord bot integration — SSE client of the Orchestrator |

### Infrastructure

| Service | Port | Purpose |
|---------|------|---------|
| **PostgreSQL 16** | 5433 | Database with Apache AGE (graph) + pgvector (embeddings) |
| **Ollama** | 11434 | Local LLM inference (llama3.2:3b for MVP) |

## MCP Tool Servers

The Execution Service manages MCP servers that give the agent its capabilities:

| MCP Server | Tools | Purpose |
|------------|-------|---------|
| **municode** | 7 tools | Fetch municipal codes from the Municode REST API — states, municipalities, code structure, section text, search |
| **knowledge_graph** | 13 tools | Build and query the zoning knowledge graph — ingest sections, build recursive summaries, query permissions/standards/definitions, search by topic |
| **filesystem** | standard | Read/write files in the shared workspace |
| **fetch** | standard | HTTP fetch for external resources |
| **discord** | 3 tools | Send/edit Discord messages, manage reactions |

### Agent Workflow

```
User: "What's the minimum lot size in Detroit's R1 district?"
                    │
                    ▼
Municode MCP ──► fetch code structure ──► fetch relevant sections
                    │
                    ▼
    KG MCP ──► ingest sections ──► build summaries
                    │
                    ▼
    KG MCP ──► kg_query_standards(district="R1") ──► answer with citation
```

The Knowledge Graph uses a **RAPTOR-like recursive summary tree** — instead of vector search, it builds summaries bottom-up (section → division → article) and uses the LLM to score relevance at each level, drilling down from broad topics to specific code sections.

## Tech Stack

- **Language:** Python 3.12
- **Framework:** FastAPI (all services)
- **Agent Framework:** LangGraph + LangChain
- **LLM:** Ollama (llama3.2:3b for MVP)
- **Database:** PostgreSQL 16 with Apache AGE (property graph) + pgvector (embeddings)
- **Knowledge Graph:** Apache AGE with municipal zoning ontology (7 vertex labels, 9 edge labels)
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
  -d '{"message": "What zoning districts exist in Detroit, MI?", "thread_id": "test-1"}'
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
municipal-agent/
├── services/
│   ├── orchestrator-service/   # LangGraph agent — reasoning, tool calls, streaming
│   ├── context-service/        # Event logging, state, knowledge graph (AGE)
│   ├── execution-service/      # MCP tool servers (municode, knowledge_graph, etc.)
│   └── discord-service/        # Discord bot — platform adapter
├── libs/
│   └── agentic-common/         # Shared library (structlog logging, auth)
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

- MCP tool servers (municode, knowledge_graph) may be spun off to separate public repositories as standalone MCP servers
- Support for additional municipal data sources beyond Municode
- GCP Cloud Run deployment (reference architecture in `docs/design/architecture/gcp_deployment.md`)
- Sidecar deployment pattern for tighter service coupling (design in `docs/design/architecture/sidecar_deployment.md`)
