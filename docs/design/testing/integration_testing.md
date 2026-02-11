# Integration Testing Standards

---

## 0. Overview

This document defines standards and best practices for integration testing in the Municipal Agent system. Integration tests verify that multiple components work correctly together, focusing on service boundaries, database interactions, and HTTP communication between services.

## 1. Scope and Objectives

### 1.1 What Integration Tests Cover

Integration tests in Municipal Agent verify:

1. **Service-to-Service Communication**
   - Orchestrator Service ↔ Context Service (HTTP API calls)
   - Orchestrator Service ↔ Execution Service (HTTP tool execution)
   - Discord Service → Orchestrator Service (SSE streaming)

2. **Database Operations**
   - Event logging with asyncpg (Context Service)
   - Schema migrations (PostgreSQL with AGE + pgvector)
   - Connection pool behavior

3. **Tool Execution Pipeline**
   - MCP server discovery and invocation
   - Sandbox path validation with real filesystem
   - Tool schema validation

### 1.2 What Integration Tests Do NOT Cover

- **LLM Reasoning**: Use E2E tests (see [e2e_testing.md](e2e_testing.md))
- **Pure Business Logic**: Use unit tests (see [unit_testing.md](unit_testing.md))
- **Performance Under Load**: Use performance tests (see [performance_testing.md](performance_testing.md))

## 2. Testing Architecture

### 2.1 Test Infrastructure: docker-compose.test.yml

Integration tests run against services defined in `docker-compose.test.yml`:

```yaml
# docker-compose.test.yml (actual)
services:
  postgres:
    build:
      context: ./services/context-service
      dockerfile: Dockerfile                    # PostgreSQL 16 + AGE + pgvector
    container_name: municipal-agent-postgres-test
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: municipal_agent_test
    ports:
      - "5434:5432"                             # Port 5434 to avoid conflict with dev
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 5

  execution-service:
    build:
      context: ./services/execution-service
      dockerfile: Dockerfile
    container_name: municipal-agent-execution-service-test
    environment:
      PORT: 8002
      LOG_LEVEL: DEBUG
      MCP_CONFIG_PATH: config/mcp_servers.json
      DEFAULT_TIMEOUT: 30
      SANDBOX_DIRECTORY: /app/sandbox
      MAX_CONCURRENT_EXECUTIONS: 10
    ports:
      - "8003:8002"                             # Port 8003 to avoid conflict
    volumes:
      - /tmp/execution-sandbox-test:/app/sandbox
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8002/health')"]
      interval: 10s
      timeout: 5s
      start_period: 15s
      retries: 3
```

### 2.2 Directory Structure

There are two integration test locations:

**Root-level** (`tests/integration/`) — Docker Compose-based, tests service-to-service HTTP:
```
tests/
└── integration/
    ├── conftest.py                                   # Shared pytest fixtures
    ├── context_service/
    │   └── test_context_integration.py               # Event logging, DB queries
    ├── execution_service/
    │   └── test_execution_integration.py             # MCP tool discovery + execution
    ├── discord_service/
    │   └── test_discord_orchestrator_flow.py          # Discord → Orchestrator SSE flow
    └── orchestrator_service/
        ├── test_orchestrator_context_flow.py          # Orchestrator → Context event logging
        └── test_orchestrator_execution_flow.py        # Orchestrator → Execution tool calls
```

**Service-level** (`services/execution-service/tests/integration/`) — subprocess-based, no Docker required:
```
services/execution-service/tests/
└── integration/
    └── test_mcp_protocol.py                          # Real MCP handshake + tools/list via subprocess
```

The MCP protocol tests spawn real FastMCP server subprocesses and verify the full MCP lifecycle
(`initialize` → `notifications/initialized` → `tools/list`) through `MCPClient`. They test
both custom servers (discord, municode) and validate that multiple concurrent server connections work.

### 2.3 Running Integration Tests

```bash
# Docker Compose-based tests (requires test infrastructure)
docker compose -f docker-compose.test.yml up -d
docker compose -f docker-compose.test.yml ps
pytest tests/integration/ -v
pytest tests/integration/context_service/ -v
pytest tests/integration/execution_service/ -v
docker compose -f docker-compose.test.yml down -v

# MCP protocol tests (no Docker required — spawns subprocesses locally)
cd services/execution-service && pytest tests/integration/ -v
```

## 3. Testing Standards

### 3.1 Test Isolation

**Requirement**: Each test must be isolated from other tests.

**Approaches used**:
- **Unique IDs**: Each test uses unique correlation IDs, thread IDs, and filenames
- **Database cleanup**: Truncate tables between test runs or use transaction rollback
- **Sandbox cleanup**: Clear sandbox directory files between execution tests

### 3.2 Assertions

**Requirement**: Use specific, meaningful assertions.

```python
def test_context_service_stores_event(context_client):
    # Arrange
    event = {
        "correlation_id": str(uuid.uuid4()),
        "event_type": "agent.invocation",
        "source": "test",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {"message": "test event"},
        "source_event_id": "test-001",
        "source_channel_id": "test-channel",
        "source_user_id": "test-user",
        "routing": {},
        "content": "test content"
    }

    # Act
    response = context_client.post("/events", json=event)

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "event_id" in data
    assert "created_at" in data
```

### 3.3 Timeouts

**Requirement**: All integration tests must have explicit timeouts.

```python
import pytest

@pytest.mark.timeout(30)
def test_execution_service_tool_discovery(execution_client):
    response = execution_client.get("/tools")
    assert response.status_code == 200
    tools = response.json().get("tools", [])
    assert len(tools) > 0
```

## 4. Service-Specific Integration Tests

### 4.1 Context Service

**Critical Flows**:
1. Event logging via `POST /events`
2. Event retrieval (when endpoint is added)
3. Knowledge graph queries via `POST /query` (Apache AGE)
4. Connection pool behavior under concurrent requests

### 4.2 Execution Service

**Critical Flows**:
1. MCP tool discovery via `GET /tools`
2. Tool execution via `POST /execute` with valid arguments
3. Path validation rejection for sandbox escapes
4. Timeout handling for long-running tools
5. File read/write through sandbox
6. MCP protocol handshake (`initialize` → `notifications/initialized`) with both custom FastMCP servers (discord, municode) and third-party MCP servers (filesystem, fetch)

### 4.3 Orchestrator → Context Flow

**Critical Flows**:
1. Orchestrator logs invocation events to Context Service
2. Event correlation via `correlation_id`
3. Error handling when Context Service is unavailable

### 4.4 Orchestrator → Execution Flow

**Critical Flows**:
1. Tool discovery at startup
2. Tool execution during agent reasoning
3. Error propagation from Execution Service to agent
4. Timeout handling for tool calls

### 4.5 Discord → Orchestrator Flow

**Critical Flows**:
1. SSE stream consumption from `POST /v1/agent/run`
2. Non-streaming fallback via `POST /process`
3. Retry behavior on Orchestrator errors

## 5. Best Practices

### 5.1 Test Naming Convention

**Format**: `test_<component>_<action>_<expected_result>`

**Examples**:
- `test_context_service_stores_event_successfully`
- `test_execution_service_rejects_path_traversal`
- `test_orchestrator_logs_event_to_context_service`

### 5.2 Flaky Test Prevention

**Common causes**:
1. **Race conditions**: Wait for health checks before testing
2. **Port conflicts**: Use non-default ports (5434, 8003) in test compose
3. **Ollama cold starts**: Not applicable to integration tests (Ollama not in test compose)
4. **Shared state**: Use unique IDs per test

### 5.3 Debugging Failures

```bash
# Check service logs
docker compose -f docker-compose.test.yml logs execution-service

# Check database state
docker exec municipal-agent-postgres-test psql -U postgres -d municipal_agent_test -c "SELECT * FROM events LIMIT 10"

# Check sandbox files
docker exec municipal-agent-execution-service-test ls -la /app/sandbox
```

## 6. Metrics

### 6.1 Coverage Targets
- Service API endpoints: 100% coverage
- Database operations: 90%+ coverage
- Error handling paths: 80%+ coverage

### 6.2 Duration Targets
- Individual test: < 5 seconds
- Full integration suite: < 10 minutes

---

**Document Status**: Updated
**Last Updated**: 2026-02-10
**Owner**: Engineering Team
