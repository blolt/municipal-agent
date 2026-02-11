# Municipal Agent - Docker Compose Guide

This guide explains how to run the complete Municipal Agent system using Docker Compose.

## Services

The system consists of 4 application services and 2 infrastructure services:

| Service | Port | Description |
|---------|------|-------------|
| **postgres** | 5433 | PostgreSQL 16 with AGE + pgvector extensions |
| **ollama** | 11434 | Local LLM runtime (llama3.2:3b) |
| **context-service** | 8001 | Event logging and knowledge retrieval |
| **execution-service** | 8002 | MCP tool execution with sandboxing |
| **orchestrator-service** | 8000 | LangGraph agent orchestration (SSE streaming) |
| **discord-service** | 8003 | Discord bot integration |

## Quick Start

### 1. Start All Services

```bash
docker-compose up -d
```

This will:
1. Build Docker images for all services
2. Start PostgreSQL and Ollama
3. Wait for infrastructure to be healthy
4. Start Context Service and Execution Service
5. Start Orchestrator Service (depends on all above)
6. Start Discord Service

### 2. Check Status

```bash
docker-compose ps
```

All services should show as "healthy" after ~30 seconds (Ollama may take longer on first start).

### 3. View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f orchestrator-service
```

### 4. Test the System

```bash
# Check all health endpoints
curl http://localhost:8001/health  # Context Service
curl http://localhost:8002/health  # Execution Service
curl http://localhost:8000/health  # Orchestrator Service
curl http://localhost:8003/health  # Discord Service
```

## Service Dependencies

```
orchestrator-service
├── depends on: postgres (healthy)
├── depends on: ollama (healthy)
├── depends on: context-service (healthy)
└── depends on: execution-service (healthy)

context-service
└── depends on: postgres (healthy)

execution-service
└── (no dependencies)

discord-service
└── connects to: orchestrator-service (via GATEWAY_SERVICE_URL)
```

## Environment Variables

### PostgreSQL
- `POSTGRES_USER`: Database user (default: `postgres`)
- `POSTGRES_PASSWORD`: Database password (default: `postgres`)
- `POSTGRES_DB`: Database name (default: `municipal_agent`)

### Context Service
- `DATABASE_URL`: PostgreSQL connection string
- `DATABASE_POOL_MIN_SIZE`: Minimum connection pool size (default: 2)
- `DATABASE_POOL_MAX_SIZE`: Maximum connection pool size (default: 10)
- `LOG_LEVEL`: Logging level (default: INFO)

### Execution Service
- `PORT`: Service port (default: 8002)
- `LOG_LEVEL`: Logging level (default: INFO)
- `MCP_CONFIG_PATH`: Path to MCP servers config (default: `config/mcp_servers.json`)
- `DEFAULT_TIMEOUT`: Tool execution timeout in seconds (default: 30)
- `SANDBOX_DIRECTORY`: Sandbox directory for file operations (default: `/workspace`)
- `MAX_CONCURRENT_EXECUTIONS`: Max concurrent tool executions (default: 10)

### Orchestrator Service
- `DATABASE_URL`: PostgreSQL connection string
- `CONTEXT_SERVICE_URL`: Context Service URL (default: `http://context-service:8001`)
- `EXECUTION_SERVICE_URL`: Execution Service URL (default: `http://execution-service:8002`)
- `OLLAMA_BASE_URL`: Ollama API URL (default: `http://ollama:11434`)
- `PORT`: Service port (default: 8000)
- `LOG_LEVEL`: Logging level (default: INFO)

### Discord Service
- `DISCORD_BOT_TOKEN`: Discord bot authentication token (required)
- `DISCORD_APPLICATION_ID`: Discord application ID (required)
- `GATEWAY_SERVICE_URL`: Orchestrator Service URL (default: `http://orchestrator-service:8000`)
- `SERVICE_TOKEN`: Internal service token (default: `dev-token`)
- `HEALTH_PORT`: Health server port (default: 8003)
- `LOG_LEVEL`: Logging level (default: INFO)
- `LOG_FORMAT`: Log format (default: `json`)

## Common Commands

### Start Services
```bash
docker-compose up -d
```

### Stop Services
```bash
docker-compose down
```

### Stop and Remove Volumes (Clean Slate)
```bash
docker-compose down -v
```

### Rebuild Services
```bash
docker-compose build
docker-compose up -d
```

### Rebuild Specific Service
```bash
docker-compose build orchestrator-service
docker-compose up -d orchestrator-service
```

### View Service Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f orchestrator-service

# Last 100 lines
docker-compose logs --tail=100 orchestrator-service
```

### Execute Commands in Container
```bash
# PostgreSQL
docker exec -it municipal-agent-postgres psql -U postgres -d municipal_agent

# Check sandbox files
docker exec -it municipal-agent-execution-service ls -la /workspace
```

## Ollama Model Management

Ollama requires pulling a model on first use:

```bash
# Pull the default model
docker exec -it municipal-agent-ollama ollama pull llama3.2:3b

# List available models
docker exec -it municipal-agent-ollama ollama list

# Test model directly
docker exec -it municipal-agent-ollama ollama run llama3.2:3b "Hello"
```

The Ollama data volume (`ollama_data`) persists models across container restarts.

## Health Checks

All services include health checks:

- **postgres**: `pg_isready -U postgres`
- **ollama**: `ollama list`
- **context-service**: HTTP GET `/health`
- **execution-service**: HTTP GET `/health`
- **orchestrator-service**: HTTP GET `/health`
- **discord-service**: HTTP GET `/health`

Check health status:
```bash
docker inspect municipal-agent-orchestrator-service --format='{{.State.Health.Status}}'
```

## Volumes

| Volume | Purpose |
|--------|---------|
| `postgres_data` | PostgreSQL data persistence |
| `ollama_data` | Ollama model storage |
| `workspace` | Shared workspace for Orchestrator and Execution Service sandbox |

## Troubleshooting

### Services Won't Start

1. Check logs:
   ```bash
   docker-compose logs
   ```

2. Verify no port conflicts:
   ```bash
   lsof -i :8000  # Orchestrator
   lsof -i :8001  # Context
   lsof -i :8002  # Execution
   lsof -i :8003  # Discord
   lsof -i :5433  # PostgreSQL
   lsof -i :11434 # Ollama
   ```

3. Clean restart:
   ```bash
   docker-compose down -v
   docker-compose up -d
   ```

### Service Unhealthy

Check specific service logs:
```bash
docker-compose logs orchestrator-service
```

### Database Connection Issues

1. Verify PostgreSQL is healthy:
   ```bash
   docker exec municipal-agent-postgres pg_isready -U postgres
   ```

2. Check database exists:
   ```bash
   docker exec municipal-agent-postgres psql -U postgres -c "\l"
   ```

3. Apply migrations if needed:
   ```bash
   docker exec -i municipal-agent-postgres psql -U postgres -d municipal_agent < services/context-service/migrations/001_create_relational_schema.sql
   ```

### Ollama Issues

1. Check Ollama is running:
   ```bash
   docker exec municipal-agent-ollama ollama list
   ```

2. Verify model is pulled:
   ```bash
   docker exec municipal-agent-ollama ollama pull llama3.2:3b
   ```

3. Ollama first startup can be slow (downloading model). Check logs:
   ```bash
   docker-compose logs ollama
   ```

### Discord Service Issues

1. Verify bot token is set:
   ```bash
   echo $DISCORD_BOT_TOKEN
   ```

2. Check connection to Orchestrator:
   ```bash
   docker exec municipal-agent-discord-service curl -f http://orchestrator-service:8000/health
   ```

### Execution Service Sandbox Issues

Check sandbox directory:
```bash
docker exec municipal-agent-execution-service ls -la /workspace
```

## Development Workflow

### Local Development with Docker Services

Run infrastructure (PostgreSQL, Ollama) in Docker, services locally:

```bash
# Start only infrastructure
docker-compose up -d postgres ollama

# Run services locally
cd services/context-service && uvicorn src.main:app --port 8001
cd services/execution-service && uvicorn src.main:app --port 8002
cd services/orchestrator-service && uvicorn src.main:app --port 8000 --env-file .env

### Running Tests
The project uses a separate Docker Compose file for integration testing to ensure isolation.

```bash
# Run Integration Tests
docker compose -f tests/integration/docker-compose.test.yml up -d
pytest tests/integration/
docker compose -f tests/integration/docker-compose.test.yml down
```
```

### Full Docker Development

Run everything in Docker:

```bash
docker-compose up -d
```

## Next Steps

- See `docs/design/architecture/system_architecture.md` for architecture overview
- See `docs/design/testing/e2e_testing.md` for E2E testing guide
- See individual service design docs in `docs/design/` for detailed documentation
