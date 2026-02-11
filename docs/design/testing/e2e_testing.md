# End-to-End Testing Standards

---

## 0. Overview

This document defines standards and best practices for end-to-end (E2E) testing in the Agentic Bridge system. E2E tests verify complete user workflows across all services, from message input through agent processing to response delivery. These tests provide the highest confidence that the system delivers value to users.

## 0.1 Glossary

- **End-to-End Test**: A test that exercises a complete user workflow from start to finish
- **Golden Path**: The expected, successful execution flow through the system
- **Smoke Test**: A minimal E2E test that verifies basic system functionality
- **Test Harness**: `E2ETestHarness` class that manages service communication for tests
- **SSE (Server-Sent Events)**: The streaming protocol consumed by `send_message_stream()`
- **Thread ID**: Unique identifier for conversation context (checkpoint key in LangGraph)

## 1. Scope and Objectives

### 1.1 What E2E Tests Cover

1. **Complete User Workflows**
   - User sends message → Agent processes → User receives response
   - Multi-turn conversations with context retention
   - Tool execution and result delivery via agent
   - SSE streaming responses

2. **Cross-Service Integration**
   - Orchestrator → Context Service (event logging)
   - Orchestrator → Execution Service → MCP tool execution
   - Full service health verification

3. **System Reliability**
   - Service health checks
   - File sandbox operations
   - Conversation state persistence (LangGraph checkpoints)

### 1.2 What E2E Tests Do NOT Cover

- **Unit-level logic**: Use unit tests (`services/*/tests/`)
- **Service-specific APIs**: Use integration tests (`tests/integration/`)
- **Discord platform integration**: Requires real bot token (tested manually)
- **Performance under load**: Use performance tests (planned)

## 2. Test Infrastructure

### 2.1 E2ETestHarness

The harness (`tests/e2e/harness.py`) provides the test interface. It uses `httpx.Client` with a 60-second timeout to accommodate Ollama cold starts.

**Key Methods**:

| Method | Purpose |
|--------|---------|
| `wait_for_services(timeout)` | Poll health endpoints until all services are ready |
| `send_message(message, thread_id)` | Send message via `POST /process` (synchronous) |
| `send_message_stream(message, thread_id)` | Send message via `POST /v1/agent/run` (SSE streaming) |
| `get_available_tools()` | List MCP tools via `GET /tools` on Execution Service |
| `create_sandbox_file(filename, content)` | Write file to sandbox via `POST /execute` |
| `read_sandbox_file(filename)` | Read file from sandbox via `POST /execute` |
| `health_check_all()` | Check health of all 3 testable services |
| `get_events(correlation_id)` | Query events from Context Service |

**Service URLs** (defaults to localhost):
- Orchestrator: `http://localhost:8000`
- Context: `http://localhost:8001`
- Execution: `http://localhost:8002`

### 2.2 Fixtures (conftest.py)

```python
@pytest.fixture(scope="session")
def harness():
    """Session-scoped test harness. Waits for services, shared across all tests."""
    h = E2ETestHarness()
    if not h.wait_for_services(timeout=60):
        pytest.fail("Services did not become healthy in time")
    yield h
    h.close()

@pytest.fixture(scope="function")
def unique_thread_id():
    """Unique thread ID per test to ensure conversation isolation."""
    return f"test_thread_{int(time.time() * 1000)}"
```

### 2.3 Running E2E Tests

**Prerequisites**: Full `docker-compose.yml` stack must be running.

```bash
# Start all services
docker compose up -d

# Wait for services to be healthy (especially Ollama model loading)
docker compose ps

# Run smoke tests only (fast)
pytest tests/e2e/ -m smoke -v

# Run golden path tests
pytest tests/e2e/ -m golden_path -v

# Run all E2E tests
pytest tests/e2e/ -v

# Run excluding slow tests
pytest tests/e2e/ -m "not slow" -v

# Stop services
docker compose down
```

## 3. Implemented Tests

### 3.1 Smoke Tests (`test_smoke.py`)

| Test | What It Verifies |
|------|-----------------|
| `test_all_services_healthy` | All 3 services return 200 on `/health` |
| `test_can_send_simple_message` | `POST /process` returns a non-empty response |
| `test_can_send_streaming_message` | `POST /v1/agent/run` returns SSE chunks |
| `test_execution_service_has_tools` | `GET /tools` returns `read_file` and `write_file` |
| `test_can_create_and_read_file` | Sandbox file write + read round-trip works |

### 3.2 Golden Path Tests (`test_golden_path.py`)

| Test | What It Verifies | Markers |
|------|-----------------|---------|
| `test_simple_conversation` | Two-turn conversation, thread context maintained | `golden_path` |
| `test_file_operation_workflow` | Agent reads a file via natural language request | `golden_path` |
| `test_multi_turn_context_retention` | Agent remembers "Agentic Bridge" across turns | `golden_path`, `slow` |
| `test_tool_discovery_and_execution` | Tools are discovered + file write/read works | `golden_path` |

### 3.3 Test Markers

Defined in `pytest.ini`:

| Marker | Purpose | Usage |
|--------|---------|-------|
| `e2e` | All E2E tests | `pytest -m e2e` |
| `smoke` | Fast basic checks | `pytest -m smoke` |
| `golden_path` | Complete workflows | `pytest -m golden_path` |
| `slow` | Tests > 10 seconds | `pytest -m "not slow"` to skip |

## 4. Testing Standards

### 4.1 Test Isolation

- **Unique Thread IDs**: Each test gets a `unique_thread_id` fixture to prevent conversation contamination
- **Unique Filenames**: Sandbox files use thread ID in the filename
- **Session Harness**: Shared harness avoids repeated service startup but tests remain independent

### 4.2 Assertions for LLM Output

Since LLM responses are non-deterministic, use behavioral assertions:

```python
# Good: Pattern matching
assert "agentic" in response2.text.lower() or "bridge" in response2.text.lower()

# Good: Existence check
assert response.status is not None
assert len(response.text) > 0

# Bad: Exact text matching
assert response.text == "The Agentic Bridge project..."  # Will break
```

### 4.3 Timeouts

- **httpx client timeout**: 60 seconds (accommodates Ollama cold starts)
- **Service wait timeout**: 60 seconds in `wait_for_services()`
- **Test-level timeout**: Use `@pytest.mark.timeout(60)` for long tests

### 4.4 Streaming vs Synchronous

The harness supports two communication modes:

| Method | Endpoint | Use Case |
|--------|----------|----------|
| `send_message()` | `POST /process` | Simple assertions on complete response |
| `send_message_stream()` | `POST /v1/agent/run` | Verify SSE streaming works |

## 5. LLM Considerations

### 5.1 Ollama (Current LLM)

- **Model**: `llama3.2:3b` with `temperature=0`
- **Cold Start**: First request after model load can take 30+ seconds
- **Determinism**: `temperature=0` provides near-deterministic output but not guaranteed identical

### 5.2 Testing Without Discord

E2E tests bypass the Discord Service and communicate directly with the Orchestrator. This is because:
1. Discord Service requires a real bot token
2. The Discord → Orchestrator flow is tested in integration tests
3. Direct Orchestrator communication tests the same agent logic

### 5.3 Behavioral Validation Strategy

For golden path tests that involve agent reasoning:
- Assert on **presence** of expected entities (e.g., "agentic" or "bridge" in response)
- Assert on **response shape** (non-empty, correct thread_id)
- Assert on **tool execution** (tools were discovered, file operations succeeded)
- Do NOT assert on exact phrasing

## 6. Debugging Failed E2E Tests

### 6.1 Common Issues

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `Services did not become healthy in time` | Ollama model not pulled | `docker exec agentic-bridge-ollama ollama pull llama3.2:3b` |
| `httpx.ReadTimeout` | Ollama first response slow | Increase client timeout or pre-warm |
| `assert len(response.text) > 0` fails | Agent returned empty response | Check orchestrator logs: `docker compose logs orchestrator-service` |
| File operations fail | Sandbox volume not mounted | Verify `workspace` volume in `docker compose ps` |

### 6.2 Checking Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f orchestrator-service

# Recent orchestrator logs
docker compose logs --tail=50 orchestrator-service
```

## 7. Evolution

### 7.1 Current State
- 5 smoke tests + 4 golden path tests
- httpx-based test harness with SSE support
- Session-scoped fixture for efficiency

### 7.2 Planned Additions
- Discord Service integration tests (with mock Discord gateway)
- Mocked LLM mode for faster, deterministic E2E tests
- CI/CD integration (GitHub Actions)
- Response latency tracking

---

**Document Status**: Updated
**Last Updated**: 2026-02-07
**Owner**: Engineering Team
