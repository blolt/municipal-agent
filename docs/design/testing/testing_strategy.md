# Testing Strategy for Agentic Bridge

---

## 0. Overview

This document outlines the testing strategy for the Agentic Bridge system. Given the unique challenges of testing LLM-based agentic systems, this strategy balances deterministic testing (where possible) with probabilistic validation (where necessary).

## 0.1 Testing Philosophy

### Core Principles
1. **Deterministic First**: Test deterministic components (databases, APIs, tool execution) with traditional unit and integration tests
2. **LLM Isolation**: Isolate LLM behavior through mocking and `temperature=0` where possible
3. **Behavioral Validation**: For end-to-end LLM flows, validate behavior patterns rather than exact outputs
4. **Fast Feedback**: Prioritize fast, reliable tests; reserve expensive LLM tests for pre-deployment validation
5. **Observability**: All tests should produce detailed logs for debugging

### Testing Pyramid for Agentic Systems

```
         /\
        /  \
       /E2E \          <- Full agent workflows (LLM-based, slow)     ✅ Implemented
      /------\
     /        \        <- Contract, LLM, Performance                  ❌ Not Yet
    /----------\
   /Integration \      <- Service-to-service (DB, HTTP, MCP)         ✅ Implemented
  /--------------\
 /   Unit Tests   \    <- Pure functions, business logic (fast)       ✅ Implemented
/------------------\
```

## 1. Current Implementation Status

### 1.1 Implemented Test Layers

| Layer | Location | Status | Tools |
|-------|----------|--------|-------|
| **Unit Tests** | `services/*/tests/` | ✅ Implemented | pytest, pytest-asyncio, unittest.mock |
| **Integration Tests** | `tests/integration/` | ✅ Implemented | pytest, docker-compose.test.yml |
| **E2E Tests** | `tests/e2e/` | ✅ Implemented | pytest, E2ETestHarness (httpx), docker-compose |

### 1.2 Not Yet Implemented

| Layer | Document | Status |
|-------|----------|--------|
| **Contract Tests** | [contract_testing.md](contract_testing.md) | Planned (P1) |
| **LLM Tests** | [llm_testing.md](llm_testing.md) | Planned (P1) |
| **Performance Tests** | [performance_testing.md](performance_testing.md) | Planned (P1) |

### 1.3 Pytest Configuration

Defined in `pytest.ini`:

```ini
[tool.pytest.ini_options]
markers =
    e2e: End-to-end tests
    smoke: Smoke tests (fast, basic checks)
    golden_path: Golden path tests (complete workflows)
    slow: Slow tests (may take >10 seconds)

testpaths = tests
```

## 2. Test Directory Structure

### 2.1 Actual Layout

```
tests/
├── __init__.py
├── e2e/
│   ├── __init__.py
│   ├── conftest.py                                # Session-scoped harness fixture
│   ├── harness.py                                 # E2ETestHarness (httpx-based)
│   ├── test_smoke.py                              # 5 smoke tests
│   └── test_golden_path.py                        # 4 golden path tests
└── integration/
    ├── conftest.py
    ├── context_service/
    │   └── test_context_integration.py
    ├── execution_service/
    │   └── test_execution_integration.py
    ├── discord_service/
    │   └── test_discord_orchestrator_flow.py
    └── orchestrator_service/
        ├── test_orchestrator_context_flow.py
        └── test_orchestrator_execution_flow.py

services/
├── context-service/tests/                         # Unit + module tests
│   ├── context_service/
│   │   ├── api/test_events.py, test_query.py, test_state.py
│   │   ├── db/test_connection.py, test_repositories.py
│   │   ├── models/test_schemas.py
│   │   └── test_config.py, test_main.py
│   ├── test_events_api.py
│   ├── test_state_api.py
│   └── test_integration.py
├── execution-service/tests/
│   ├── unit/
│   │   ├── test_runtime.py           # SubprocessRuntime lifecycle
│   │   ├── test_validation.py        # Tool argument validation
│   │   ├── test_path_validation.py   # Sandbox path validation
│   │   ├── test_mcp_client.py        # MCPClient protocol handshake
│   │   ├── test_discord_mcp.py       # Discord MCP server tools (FastMCP)
│   │   └── test_municode_mcp.py      # Municode MCP server tools (FastMCP)
│   └── integration/
│       └── test_mcp_protocol.py      # Real subprocess MCP handshake + tools/list
├── discord-service/tests/
│   ├── test_internal_event.py
│   ├── test_discord_handler.py
│   └── test_orchestrator_client.py
└── orchestrator-service/tests/
    └── test_streaming.py
```

### 2.2 Test Infrastructure

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Full system for E2E tests |
| `docker-compose.test.yml` | Lightweight infra (postgres + execution-service) for integration tests |
| `pytest.ini` | Marker definitions and test discovery config |
| `tests/e2e/harness.py` | E2ETestHarness class for E2E test orchestration |

## 3. Testing Document References

### 3.1 [Unit Testing Standards](unit_testing.md)
- **Scope**: Individual functions, classes, and modules within a single service
- **Focus**: Business logic, data transformations, SSE streaming endpoints, path validation
- **Tools**: pytest, pytest-asyncio, unittest.mock, TestClient (FastAPI)
- **Actual Tests**: `services/*/tests/`

### 3.2 [Integration Testing Standards](integration_testing.md)
- **Scope**: Multi-service interactions, database operations, MCP tool execution
- **Focus**: Service boundaries, data persistence, Orchestrator ↔ Context/Execution flows
- **Tools**: Docker Compose (`docker-compose.test.yml`), pytest, httpx
- **Actual Tests**: `tests/integration/`

### 3.3 [End-to-End Testing Standards](e2e_testing.md)
- **Scope**: Full user workflows across all services
- **Focus**: System reliability, SSE streaming, tool execution through agent, context retention
- **Tools**: Docker Compose, E2ETestHarness (httpx), pytest
- **Actual Tests**: `tests/e2e/`

### 3.4 [Contract Testing Standards](contract_testing.md) — Not Yet Implemented
- **Scope**: API contracts, MCP tool schemas, SSE event schemas
- **Tools**: JSON Schema validation, Pact (planned)

### 3.5 [LLM Testing Standards](llm_testing.md) — Not Yet Implemented
- **Scope**: Agent reasoning, tool selection, response quality
- **Tools**: Custom evaluation harnesses, prompt regression tests (planned)

### 3.6 [Performance Testing Standards](performance_testing.md) — Not Yet Implemented
- **Scope**: Latency, throughput, resource utilization
- **Tools**: Locust, k6 (planned)

## 4. CI/CD Integration Strategy

> **Note:** CI/CD pipelines are not yet implemented. This section describes the planned approach.

### 4.1 Planned Pipeline Stages

```yaml
# Planned pipeline structure
stages:
  - lint:          # Ruff, mypy (< 1 min)
  - unit:          # Service unit tests (< 3 min)
  - integration:   # docker-compose.test.yml tests (< 10 min)
  - e2e-smoke:     # Smoke tests with Ollama (< 5 min)
  - deploy-staging # Deploy to staging
  - e2e-full:      # Full E2E golden path (< 15 min, staging only)
```

### 4.2 Running Tests Locally

```bash
# Unit tests (per service)
cd services/context-service && pytest tests/
cd services/execution-service && pytest tests/unit/
cd services/discord-service && pytest tests/
cd services/orchestrator-service && pytest tests/

# MCP protocol integration tests (no Docker required — spawns real subprocesses)
cd services/execution-service && pytest tests/integration/ -v

# Integration tests (requires docker-compose.test.yml services)
docker compose -f docker-compose.test.yml up -d
pytest tests/integration/ -v

# E2E tests (requires full docker-compose stack)
docker compose up -d
pytest tests/e2e/ -m smoke -v        # Smoke tests only
pytest tests/e2e/ -m golden_path -v  # Golden path workflows
pytest tests/e2e/ -v                 # All E2E tests
```

## 5. LLM-Specific Testing Challenges

### 5.1 Non-Determinism
**Challenge**: LLM outputs vary between runs, making exact assertions impossible.

**Current Approach**:
- **Temperature=0**: Ollama (llama3.2:3b) configured with `temperature=0` for near-deterministic output
- **Behavioral Assertions**: E2E tests validate patterns (e.g., "response contains project name") rather than exact text
- **Thread Isolation**: Each test uses a unique `thread_id` to avoid cross-test state contamination

### 5.2 Cost and Latency
**Challenge**: LLM calls are slow (Ollama first load can take 30+ seconds).

**Current Approach**:
- **Session-scoped Harness**: E2E harness is session-scoped to avoid repeated service startup
- **60s Client Timeout**: httpx client has 60s timeout to accommodate Ollama cold starts
- **Smoke Before Golden Path**: Quick smoke tests run first to catch infrastructure issues

### 5.3 Evaluation Metrics (Planned)
- **Task Success Rate**: Did the agent complete the intended task?
- **Tool Selection Accuracy**: Did the agent choose the right tools?
- **Context Retention**: Did the agent remember prior conversation turns?

## 6. Test Data Management

### 6.1 Fixtures
- **E2E Fixtures**: Session-scoped `harness` fixture in `tests/e2e/conftest.py`
- **Unique Thread IDs**: Function-scoped `unique_thread_id` fixture for test isolation
- **Sandbox Files**: `create_sandbox_file()` / `read_sandbox_file()` helpers in E2ETestHarness

### 6.2 Database State
- **Integration Tests**: Use test-specific PostgreSQL database (`agentic_bridge_test` on port 5434)
- **E2E Tests**: Use full docker-compose stack with main database

### 6.3 Secrets Management
- **No Real Credentials**: Tests use dev-token and local Ollama (no API keys needed)
- **Discord Service**: Excluded from E2E tests (requires real bot token)

## 7. Evolution and Maintenance

### 7.1 Completed
- Unit test structure for all 4 services
- Integration test structure with docker-compose.test.yml
- E2E test harness with SSE streaming support
- Smoke tests (health checks, message sending, tool execution)
- Golden path tests (conversation, file operations, context retention)

### 7.2 Next Steps
1. **Short-term**: Add CI/CD pipeline (GitHub Actions)
2. **Short-term**: Increase unit test coverage across all services
3. **Medium-term**: Add contract testing for API schemas and SSE events
4. **Medium-term**: Add LLM evaluation framework
5. **Long-term**: Add performance testing and benchmarks

---

**Document Status**: Updated
**Last Updated**: 2026-02-10
**Owner**: Engineering Team
