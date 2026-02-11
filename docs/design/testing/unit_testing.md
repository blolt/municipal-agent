# Unit Testing Standards

---

## 0. Overview

This document defines standards and best practices for unit testing in the Municipal Agent system. Unit tests verify individual functions, classes, and modules in isolation, focusing on business logic, data transformations, and utility functions.

**Language**: All services are Python 3.12. There are no TypeScript/JavaScript services.

## 1. Scope and Objectives

### 1.1 What Unit Tests Cover

Unit tests in Municipal Agent verify:

1. **Business Logic** — Data validation rules, state transitions, decision logic
2. **Pure Functions** — Input/output transformations, data parsing, utility functions
3. **Class Behavior** — Constructor initialization, method behavior, internal state
4. **Edge Cases** — Boundary conditions, empty inputs, invalid inputs, error conditions
5. **API Endpoints** — FastAPI route handlers via `TestClient` (without external services)
6. **SSE Streaming** — Streaming response formatting and event emission

### 1.2 What Unit Tests Do NOT Cover

- **External Dependencies**: Database, MCP servers, Ollama (use integration tests)
- **Multi-Service Interactions**: Service-to-service HTTP (use integration tests)
- **LLM Behavior**: Agent reasoning, tool selection (use E2E tests)

## 2. Testing Framework and Tools

**Framework**: pytest

**Key Libraries**:
```python
pytest              # Test framework
pytest-cov          # Coverage reporting
pytest-mock         # Mocking utilities (mocker fixture)
pytest-asyncio      # Async test support
```

**FastAPI Testing**:
```python
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
```

## 3. Actual Test Locations

### 3.1 Per-Service Test Directories

```
services/
├── context-service/tests/
│   ├── context_service/
│   │   ├── api/
│   │   │   ├── test_events.py       # Event API endpoint tests
│   │   │   ├── test_query.py        # Knowledge query endpoint tests
│   │   │   └── test_state.py        # State endpoint tests
│   │   ├── db/
│   │   │   ├── test_connection.py   # Database connection pool tests
│   │   │   └── test_repositories.py # Repository pattern tests
│   │   ├── models/
│   │   │   └── test_schemas.py      # Pydantic model validation
│   │   ├── test_config.py           # Configuration loading
│   │   └── test_main.py             # App lifespan, health endpoint
│   ├── test_events_api.py           # Event API integration
│   ├── test_state_api.py            # State API integration
│   └── test_integration.py          # DB integration (requires postgres)
│
├── execution-service/tests/
│   ├── unit/
│   │   ├── test_runtime.py          # SubprocessRuntime lifecycle
│   │   ├── test_validation.py       # Tool argument validation
│   │   ├── test_path_validation.py  # Sandbox path validation
│   │   ├── test_mcp_client.py       # MCPClient protocol handshake
│   │   ├── test_discord_mcp.py      # Discord MCP server tools (FastMCP)
│   │   └── test_municode_mcp.py     # Municode MCP server tools (FastMCP)
│   └── integration/
│       └── test_mcp_protocol.py     # Real subprocess MCP handshake + tools/list
│
├── discord-service/tests/
│   ├── test_internal_event.py       # InternalEvent schema
│   ├── test_discord_handler.py      # DiscordGatewayHandler (mocked discord.py)
│   └── test_orchestrator_client.py  # OrchestratorClient HTTP calls
│
└── orchestrator-service/tests/
    └── test_streaming.py            # SSE streaming endpoint
```

### 3.2 Running Tests

```bash
# Run all unit tests for a service
cd services/context-service && pytest tests/

# Run execution-service unit tests
cd services/execution-service && pytest tests/unit/ -v

# Run execution-service integration tests (real subprocess, no Docker)
cd services/execution-service && pytest tests/integration/ -v

# Run specific test file
cd services/execution-service && pytest tests/unit/test_path_validation.py -v

# Run with coverage
cd services/discord-service && pytest tests/ --cov=. --cov-report=term
```

## 4. Testing Standards

### 4.1 Test Structure: Arrange-Act-Assert (AAA)

**Requirement**: All tests must follow the AAA pattern with clear separation.

```python
def test_path_validation_rejects_traversal():
    # Arrange
    validator = PathValidator(sandbox_dir="/workspace")
    malicious_path = "/workspace/../etc/passwd"

    # Act & Assert
    with pytest.raises(PathValidationError):
        validator.validate(malicious_path)
```

### 4.2 Test Naming Convention

**Format**: `test_<method>_<scenario>_<expected_result>`

**Examples**:
- `test_validate_path_with_traversal_raises_error`
- `test_normalize_message_extracts_channel_id`
- `test_stream_event_emits_thinking_tokens`

### 4.3 Mocking External Dependencies

**Requirement**: Unit tests must mock all external dependencies (databases, HTTP clients, subprocesses).

**Example — Mocking asyncpg (Context Service)**:
```python
@pytest.mark.asyncio
async def test_event_repository_inserts_event(mocker):
    # Arrange
    mock_pool = mocker.AsyncMock()
    mock_pool.fetchrow.return_value = {"event_id": "abc-123", "created_at": "2026-01-01"}
    repo = EventRepository(pool=mock_pool)
    event = InternalEvent(correlation_id="corr-1", event_type="test", ...)

    # Act
    result = await repo.insert(event)

    # Assert
    assert result["event_id"] == "abc-123"
    mock_pool.fetchrow.assert_called_once()
```

**Example — Mocking discord.py (Discord Service)**:
```python
def test_normalize_message_extracts_metadata():
    # Arrange
    mock_message = MagicMock()
    mock_message.id = 12345
    mock_message.content = "Hello agent"
    mock_message.author.id = 67890
    mock_message.author.display_name = "TestUser"
    mock_message.channel.id = 11111

    handler = DiscordGatewayHandler()

    # Act
    event = handler._normalize_message(mock_message)

    # Assert
    assert event.source_event_id == "12345"
    assert event.content == "Hello agent"
    assert event.source_user_id == "67890"
```

**Example — Mocking httpx (Orchestrator Client)**:
```python
@pytest.mark.asyncio
async def test_orchestrator_client_retries_on_failure(mocker):
    # Arrange
    mock_response = mocker.AsyncMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError("500", ...)
    client = OrchestratorClient(base_url="http://test:8000")

    # Act & Assert
    with pytest.raises(OrchestratorError):
        await client.send_event(event)
```

**Example — Testing FastMCP Tool Functions (Execution Service)**:

MCP servers use the `FastMCP` SDK with `@mcp.tool()` decorators. Each tool is an async function
that can be imported and tested directly — no JSON-RPC transport needed. Mock the underlying
HTTP helper (e.g. `_discord_request`) with `AsyncMock`:

```python
from unittest.mock import patch, AsyncMock
from mcp_servers.discord_server import discord_send_message

@patch("mcp_servers.discord_server._discord_request", new_callable=AsyncMock)
async def test_send_message_returns_id(mock_request):
    # Arrange
    mock_request.return_value = {"id": "msg-999", "content": "Hello"}

    # Act
    result = await discord_send_message(channel_id="ch-123", content="Hello")

    # Assert
    mock_request.assert_called_once_with(
        "POST", "/channels/ch-123/messages", {"content": "Hello"},
    )
    assert "msg-999" in result
```

**Example — Testing MCPClient Protocol Handshake (Execution Service)**:

The `MCPClient.connect()` performs the standard MCP handshake (`initialize` → response →
`notifications/initialized`). Test by mocking `SubprocessRuntime` to provide fake stdio streams:

```python
from unittest.mock import AsyncMock, MagicMock
from src.mcp.client import MCPClient

async def test_connect_sends_initialize_then_notification(server_config, mock_runtime):
    init_response = {
        "jsonrpc": "2.0", "id": 1,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "test", "version": "1.0.0"},
        },
    }
    reader = asyncio.StreamReader()
    reader.feed_data((json.dumps(init_response) + "\n").encode())
    writer = MagicMock()
    writer.drain = AsyncMock()
    mock_runtime.start_server.return_value = (reader, writer)

    client = MCPClient(server_config, mock_runtime)
    await client.connect()

    # First write: initialize request (has "id")
    first_msg = json.loads(writer.write.call_args_list[0][0][0].decode())
    assert first_msg["method"] == "initialize"
    # Second write: notification (no "id")
    second_msg = json.loads(writer.write.call_args_list[1][0][0].decode())
    assert second_msg["method"] == "notifications/initialized"
    assert "id" not in second_msg
```

### 4.4 Testing Async Code

```python
import pytest

@pytest.mark.asyncio
async def test_connection_pool_initializes():
    # Arrange
    pool = await create_pool(DATABASE_URL, min_size=1, max_size=2)

    # Act
    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT 1")

    # Assert
    assert result == 1

    await pool.close()
```

### 4.5 Testing FastAPI Endpoints

```python
from fastapi.testclient import TestClient

def test_health_endpoint_returns_200(mock_app):
    client = TestClient(mock_app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
```

### 4.6 Parametrized Tests

```python
@pytest.mark.parametrize("path,should_pass", [
    ("/workspace/file.txt", True),
    ("/workspace/subdir/file.txt", True),
    ("/workspace/../etc/passwd", False),
    ("/etc/passwd", False),
    ("../../outside", False),
])
def test_path_validation(path, should_pass):
    validator = PathValidator(sandbox_dir="/workspace")
    if should_pass:
        validator.validate(path)  # Should not raise
    else:
        with pytest.raises(PathValidationError):
            validator.validate(path)
```

## 5. Code Coverage Standards

### 5.1 Coverage Targets

| Code Type | Target | Rationale |
|-----------|--------|-----------|
| Path Validation | 90%+ | Security-critical |
| API Endpoints | 80%+ | User-facing |
| Pydantic Models | 80%+ | Data integrity |
| Business Logic | 80%+ | Correctness |
| Configuration | 60%+ | Simple, low risk |

### 5.2 Coverage Measurement

```bash
# Run with coverage
pytest tests/ --cov=. --cov-report=html --cov-report=term

# View HTML report
open htmlcov/index.html
```

## 6. Common Patterns

### 6.1 Conftest Fixtures

```python
# services/discord-service/tests/conftest.py
import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_discord_client():
    """Provide a mocked discord.Client."""
    client = MagicMock()
    client.user = MagicMock()
    client.user.bot = True
    return client

@pytest.fixture
def mock_orchestrator_response():
    """Provide a mocked Orchestrator response."""
    return {"status": "success", "response": "Hello!"}
```

### 6.2 Anti-Patterns to Avoid

- **Testing implementation details**: Don't assert on internal method calls; test observable behavior
- **Shared mutable state**: Each test should create its own fixtures
- **Overly broad mocking**: Mock at the boundary, not deep internals
- **No assertions**: Every test must have at least one assertion

## 7. Metrics

### 7.1 Test Execution Time
- Individual test: < 100ms
- Test file: < 1 second
- Full unit suite per service: < 30 seconds

### 7.2 Flakiness
- Target: 0% flakiness for unit tests
- If a unit test is flaky, it's likely testing external dependencies (move to integration)

---

**Document Status**: Updated
**Last Updated**: 2026-02-10
**Owner**: Engineering Team
