# Contract Testing Standards

> **Not Yet Implemented** (2026-02-07): No contract testing framework is in place. This document describes the planned approach for API contract validation. See `testing_strategy.md` for the current test implementation status.

## 0. Overview

This document defines standards and best practices for contract testing in the Agentic Bridge system. Contract tests verify that services honor their API contracts, ensuring that changes to one service don't break consumers. This is especially critical in a microservices architecture where services evolve independently.

## 0.1 Glossary

- **Contract**: A formal specification of an API's inputs, outputs, and behavior
- **Provider**: The service that implements an API (e.g., Context Service provides `/query` endpoint)
- **Consumer**: The service that calls an API (e.g., Orchestrator consumes Context Service)
- **JSON Schema**: A vocabulary for annotating and validating JSON documents
- **OpenAPI**: A specification for describing REST APIs
- **MCP (Model Context Protocol)**: A standardized protocol for tool discovery and invocation
- **Schema Validation**: Verifying that data conforms to a defined schema
- **Breaking Change**: A change to an API that breaks existing consumers
- **Backward Compatibility**: The ability for new versions to work with old consumers
- **Contract-First Development**: Defining the contract before implementing the service

## 1. Scope and Objectives

### 1.1 What Contract Tests Cover

Contract tests in Agentic Bridge verify:

1. **REST API Contracts**
   - Request/response schemas
   - HTTP status codes
   - Headers and content types
   - Error response formats

2. **MCP Tool Schemas**
   - Tool input schemas (JSON Schema)
   - Tool output formats
   - Error responses
   - Tool discovery protocol

3. **Event Schemas**
   - StreamEvent schema (Server-Sent Events)
   - Internal event structure
   - Database event log structure

4. **Database Schemas**
   - Table structures
   - Column types and constraints
   - Migration compatibility

### 1.2 What Contract Tests Do NOT Cover

- **Business Logic**: Use unit tests
- **Performance**: Use performance tests
- **Multi-Service Workflows**: Use integration tests
- **LLM Behavior**: Use LLM-specific tests

## 2. Contract Testing Approaches

### 2.1 Schema-Based Validation

**Approach**: Define schemas using JSON Schema or OpenAPI, validate all requests/responses.

**When to Use**: 
- REST APIs
- MCP tool definitions
- Event messages

**Example (JSON Schema)**:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Event",
  "type": "object",
  "required": ["event_id", "event_type", "timestamp"],
  "properties": {
    "event_id": {
      "type": "string",
      "pattern": "^evt_[a-zA-Z0-9]+$"
    },
    "event_type": {
      "type": "string",
      "enum": ["user.message", "system.notification", "tool.execution"]
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "payload": {
      "type": "object"
    }
  }
}
```

### 2.2 Consumer-Driven Contract Testing (CDCT)

**Approach**: Consumers define their expectations, providers verify they meet them.

**When to Use**:
- Multiple consumers of the same API
- Frequent API changes
- Need to prevent breaking changes

**Tools**: Pact (future consideration)

### 2.3 Provider-Side Validation

**Approach**: Provider validates all incoming requests and outgoing responses against schemas.

**When to Use**:
- Single provider, multiple consumers
- Strong schema enforcement needed
- Real-time validation in production

## 3. Testing Standards

### 3.1 REST API Contract Testing

#### 3.1.1 OpenAPI Specification

**Requirement**: All REST APIs must have an OpenAPI 3.0+ specification.

**Example (Context Service)**:
```yaml
# services/context-service/openapi.yaml
openapi: 3.0.0
info:
  title: Context Service API
  version: 1.0.0
paths:
  /query:
    post:
      summary: Semantic search over knowledge base
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [query]
              properties:
                query:
                  type: string
                  minLength: 1
                  maxLength: 1000
                limit:
                  type: integer
                  minimum: 1
                  maximum: 100
                  default: 10
      responses:
        '200':
          description: Successful query
          content:
            application/json:
              schema:
                type: object
                required: [results]
                properties:
                  results:
                    type: array
                    items:
                      type: object
                      required: [text, similarity_score]
                      properties:
                        text:
                          type: string
                        similarity_score:
                          type: number
                          minimum: 0
                          maximum: 1
        '400':
          description: Invalid request
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'
components:
  schemas:
    Error:
      type: object
      required: [error, message]
      properties:
        error:
          type: string
        message:
          type: string
        details:
          type: object
```

#### 3.1.2 Request Validation Test

**Python Example**:
```python
import pytest
from jsonschema import validate, ValidationError
from context_service.schemas import QUERY_REQUEST_SCHEMA

def test_query_request_validates_against_schema():
    """Verify that valid query requests pass schema validation."""
    # Arrange
    valid_request = {
        "query": "What is the capital of France?",
        "limit": 5
    }
    
    # Act & Assert
    validate(instance=valid_request, schema=QUERY_REQUEST_SCHEMA)

def test_query_request_rejects_missing_query():
    """Verify that requests without 'query' field are rejected."""
    # Arrange
    invalid_request = {
        "limit": 5
    }
    
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        validate(instance=invalid_request, schema=QUERY_REQUEST_SCHEMA)
    
    assert "'query' is a required property" in str(exc_info.value)

@pytest.mark.parametrize("invalid_query", [
    "",           # Empty string
    "a" * 1001,   # Too long
    123,          # Wrong type
    None,         # Null
])
def test_query_request_rejects_invalid_query_values(invalid_query):
    """Verify that invalid query values are rejected."""
    invalid_request = {"query": invalid_query}
    
    with pytest.raises(ValidationError):
        validate(instance=invalid_request, schema=QUERY_REQUEST_SCHEMA)
```

#### 3.1.3 Response Validation Test

**Python Example**:
```python
def test_query_response_conforms_to_schema(context_service_client):
    """Verify that API responses conform to the defined schema."""
    # Arrange
    request = {"query": "test query", "limit": 5}
    
    # Act
    response = context_service_client.post("/query", json=request)
    
    # Assert
    assert response.status_code == 200
    validate(instance=response.json(), schema=QUERY_RESPONSE_SCHEMA)

def test_error_response_conforms_to_schema(context_service_client):
    """Verify that error responses conform to the error schema."""
    # Arrange
    invalid_request = {}  # Missing required 'query' field
    
    # Act
    response = context_service_client.post("/query", json=invalid_request)
    
    # Assert
    assert response.status_code == 400
    validate(instance=response.json(), schema=ERROR_SCHEMA)
    assert "error" in response.json()
    assert "message" in response.json()
```

### 3.2 MCP Tool Contract Testing

#### 3.2.1 Tool Schema Definition

**Requirement**: All MCP tools must define their input schema using JSON Schema.

**Example (Check Order Status Tool)**:
```json
{
  "name": "check_order_status",
  "description": "Retrieve the current status of an order",
  "inputSchema": {
    "type": "object",
    "required": ["order_id"],
    "properties": {
      "order_id": {
        "type": "string",
        "pattern": "^ORD-[0-9]{6}$",
        "description": "Order ID in format ORD-XXXXXX"
      }
    }
  }
}
```

#### 3.2.2 Tool Discovery Contract Test

**Python Example**:
```python
def test_mcp_server_returns_valid_tool_list(mcp_client):
    """Verify that MCP server returns tools conforming to MCP protocol."""
    # Act
    tools = mcp_client.list_tools()
    
    # Assert
    assert isinstance(tools, list)
    assert len(tools) > 0
    
    for tool in tools:
        # Validate tool structure
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool
        
        # Validate input schema is valid JSON Schema
        assert tool["inputSchema"]["type"] == "object"
        assert "properties" in tool["inputSchema"]

def test_tool_input_schema_is_valid_json_schema():
    """Verify that tool input schemas are valid JSON Schema documents."""
    from jsonschema import Draft7Validator
    
    # Arrange
    tool_schema = {
        "type": "object",
        "required": ["order_id"],
        "properties": {
            "order_id": {"type": "string"}
        }
    }
    
    # Act & Assert
    Draft7Validator.check_schema(tool_schema)  # Raises if invalid
```

#### 3.2.3 Tool Invocation Contract Test

**TypeScript Example**:
```typescript
import { MCPClient } from '../../src/mcpClient';
import { validateToolInput } from '../../src/validation';

describe('MCP Tool Contracts', () => {
  describe('check_order_status', () => {
    it('should accept valid order ID format', () => {
      const validInput = { order_id: 'ORD-123456' };
      
      expect(() => validateToolInput('check_order_status', validInput))
        .not.toThrow();
    });
    
    it('should reject invalid order ID format', () => {
      const invalidInputs = [
        { order_id: 'invalid' },
        { order_id: '123456' },
        { order_id: 'ORD-ABC' },
        {},  // Missing order_id
      ];
      
      invalidInputs.forEach(input => {
        expect(() => validateToolInput('check_order_status', input))
          .toThrow(/validation error/i);
      });
    });
    
    it('should return response conforming to output schema', async () => {
      const client = new MCPClient();
      const validInput = { order_id: 'ORD-123456' };
      
      const result = await client.callTool('check_order_status', validInput);
      
      expect(result).toHaveProperty('status');
      expect(result).toHaveProperty('order_id');
      expect(result.order_id).toBe('ORD-123456');
    });
  });
});
```

### 3.3 Event Schema Contract Testing

#### 3.3.1 Event Schema Definition

**Requirement**: All event types must have a defined schema.

**Example (Internal Event)**:
```python
# services/shared/schemas/events.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict, Any, Literal

class InternalEvent(BaseModel):
    """Schema for internal events flowing through the system."""
    event_id: str = Field(..., pattern=r"^evt_[a-zA-Z0-9]+$")
    correlation_id: str = Field(..., pattern=r"^[a-f0-9-]{36}$")  # UUID
    event_type: Literal["user.message", "system.notification", "tool.execution"]
    timestamp: datetime
    payload: Dict[str, Any]
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "evt_abc123",
                "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
                "event_type": "user.message",
                "timestamp": "2026-01-22T20:00:00Z",
                "payload": {"message": "Hello"}
            }
        }
```

#### 3.3.2 Event Validation Test

**Python Example**:
```python
import pytest
from pydantic import ValidationError
from shared.schemas.events import InternalEvent

def test_internal_event_validates_with_valid_data():
    """Verify that valid events pass validation."""
    # Arrange
    event_data = {
        "event_id": "evt_test123",
        "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
        "event_type": "user.message",
        "timestamp": "2026-01-22T20:00:00Z",
        "payload": {"message": "Hello"}
    }
    
    # Act
    event = InternalEvent(**event_data)
    
    # Assert
    assert event.event_id == "evt_test123"
    assert event.event_type == "user.message"

@pytest.mark.parametrize("invalid_field,invalid_value", [
    ("event_id", "invalid_format"),  # Doesn't match pattern
    ("correlation_id", "not-a-uuid"),  # Invalid UUID
    ("event_type", "unknown.type"),  # Not in allowed values
    ("timestamp", "invalid-date"),  # Invalid datetime
])
def test_internal_event_rejects_invalid_data(invalid_field, invalid_value):
    """Verify that invalid events are rejected."""
    # Arrange
    event_data = {
        "event_id": "evt_test123",
        "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
        "event_type": "user.message",
        "timestamp": "2026-01-22T20:00:00Z",
        "payload": {}
    }
    event_data[invalid_field] = invalid_value
    
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        InternalEvent(**event_data)
    
    assert invalid_field in str(exc_info.value)
```

#### 3.3.3 Streaming Event Contract Test

**Python Example**:
```python
def test_streaming_events_conform_to_schema(orchestrator_client):
    """Verify that events streamed from the API conform to StreamEvent schema."""
    # Arrange
    request = {"input": "Hello", "thread_id": "test_1", "correlation_id": "corr_1"}
    
    # Act: Request streaming
    response = orchestrator_client.post("/v1/agent/run", json=request, stream=True)
    
    # Assert: Each event parses against schema
    for line in response.iter_lines():
        if not line: continue
        
        decoded = line.decode('utf-8')
        if not decoded.startswith("data: "): continue
        
        event_data = json.loads(decoded[6:])
        
        # Validate minimal StreamEvent fields
        assert "type" in event_data
        assert event_data["type"] in ["thinking", "tool_start", "tool_result", "message", "done", "error"]
        
        if event_data["type"] == "thinking":
            assert "content" in event_data
```

### 3.4 Database Schema Contract Testing

#### 3.4.1 Migration Validation

**Requirement**: All database migrations must be tested for backward compatibility.

**Python Example**:
```python
def test_migration_preserves_existing_columns(db_connection):
    """Verify that new migration doesn't drop existing columns."""
    # Arrange: Get columns before migration
    before_columns = get_table_columns(db_connection, "events")
    
    # Act: Run migration
    run_migration(db_connection, "002_add_metadata_column.sql")
    
    # Assert: All previous columns still exist
    after_columns = get_table_columns(db_connection, "events")
    for column in before_columns:
        assert column in after_columns, f"Column {column} was removed"

def test_migration_adds_expected_columns(db_connection):
    """Verify that migration adds the expected new columns."""
    # Act
    run_migration(db_connection, "002_add_metadata_column.sql")
    
    # Assert
    columns = get_table_columns(db_connection, "events")
    assert "metadata" in columns
    
    # Verify column type
    column_info = get_column_info(db_connection, "events", "metadata")
    assert column_info["type"] == "jsonb"
    assert column_info["nullable"] == True
```

## 4. Contract Versioning

### 4.1 Semantic Versioning for APIs

**Requirement**: Use semantic versioning (MAJOR.MINOR.PATCH) for API contracts.

**Version Bump Rules**:
- **MAJOR**: Breaking changes (remove field, change type, remove endpoint)
- **MINOR**: Backward-compatible additions (new optional field, new endpoint)
- **PATCH**: Bug fixes, documentation updates

**Example**:
```yaml
# openapi.yaml
openapi: 3.0.0
info:
  title: Context Service API
  version: 2.1.0  # MAJOR.MINOR.PATCH
```

### 4.2 Deprecation Policy

**Requirement**: Deprecated fields/endpoints must be supported for at least 2 minor versions.

**Example**:
```yaml
paths:
  /search:  # Deprecated
    post:
      deprecated: true
      summary: "[DEPRECATED] Use /query instead. Will be removed in v3.0.0"
      # ... rest of definition
  /query:  # New endpoint
    post:
      summary: "Semantic search over knowledge base"
      # ... rest of definition
```

### 4.3 Breaking Change Detection

**Requirement**: CI/CD must detect breaking changes and fail the build.

**Tool**: `openapi-diff` or similar

**GitHub Actions Example**:
```yaml
- name: Check for breaking changes
  run: |
    npx openapi-diff \
      origin/main:services/context-service/openapi.yaml \
      HEAD:services/context-service/openapi.yaml \
      --fail-on-incompatible
```

## 5. Contract-First Development

### 5.1 Workflow

1. **Define Contract**: Write OpenAPI spec or JSON Schema
2. **Review Contract**: Team reviews and approves
3. **Generate Code**: Use code generators (optional)
4. **Implement Service**: Build to match contract
5. **Validate**: Run contract tests

### 5.2 Code Generation (Optional)

**Python (FastAPI)**:
```bash
# Generate Pydantic models from OpenAPI spec
datamodel-codegen \
  --input openapi.yaml \
  --output models.py \
  --input-file-type openapi
```

**TypeScript**:
```bash
# Generate TypeScript types from OpenAPI spec
npx openapi-typescript openapi.yaml --output types.ts
```

## 6. CI/CD Integration

### 6.1 GitHub Actions Workflow

```yaml
name: Contract Tests

on:
  pull_request:
  push:
    branches: [main]

jobs:
  contract-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Need history for openapi-diff
      
      - name: Validate OpenAPI specs
        run: |
          npx @apidevtools/swagger-cli validate services/*/openapi.yaml
      
      - name: Check for breaking changes
        if: github.event_name == 'pull_request'
        run: |
          for spec in services/*/openapi.yaml; do
            npx openapi-diff \
              origin/main:$spec \
              HEAD:$spec \
              --fail-on-incompatible
          done
      
      - name: Run schema validation tests
        run: pytest tests/contract/ -v --tb=short
      
      - name: Validate MCP tool schemas
        run: |
          python scripts/validate_mcp_schemas.py
```

### 6.2 Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: validate-openapi
        name: Validate OpenAPI specs
        entry: npx @apidevtools/swagger-cli validate
        language: system
        files: 'openapi\.yaml$'
      
      - id: validate-json-schemas
        name: Validate JSON Schemas
        entry: python scripts/validate_json_schemas.py
        language: system
        files: '\.schema\.json$'
```

## 7. Best Practices

### 7.1 Schema Design Principles

**Be Explicit**:
```json
// Good: Explicit constraints
{
  "type": "string",
  "minLength": 1,
  "maxLength": 255,
  "pattern": "^[a-zA-Z0-9_-]+$"
}

// Bad: Too permissive
{
  "type": "string"
}
```

**Use Enums for Fixed Values**:
```json
{
  "event_type": {
    "type": "string",
    "enum": ["user.message", "system.notification", "tool.execution"]
  }
}
```

**Provide Examples**:
```yaml
components:
  schemas:
    Event:
      type: object
      properties:
        event_id:
          type: string
      example:
        event_id: "evt_abc123"
```

### 7.2 Error Response Standardization

**Requirement**: All services must use a consistent error response format.

**Standard Error Schema**:
```json
{
  "type": "object",
  "required": ["error", "message"],
  "properties": {
    "error": {
      "type": "string",
      "description": "Error code (e.g., 'validation_error', 'not_found')"
    },
    "message": {
      "type": "string",
      "description": "Human-readable error message"
    },
    "details": {
      "type": "object",
      "description": "Additional error context (e.g., field-level validation errors)"
    },
    "request_id": {
      "type": "string",
      "description": "Unique request ID for debugging"
    }
  }
}
```

### 7.3 Backward Compatibility Guidelines

**Safe Changes** (non-breaking):
- Add new optional field
- Add new endpoint
- Add new enum value (if consumers handle unknown values)
- Relax validation (e.g., increase max length)

**Unsafe Changes** (breaking):
- Remove field
- Rename field
- Change field type
- Make optional field required
- Remove endpoint
- Change HTTP method
- Tighten validation (e.g., decrease max length)

## 8. Metrics and Monitoring

### 8.1 Contract Compliance Metrics

**Track**:
- % of APIs with OpenAPI specs
- % of tools with JSON Schema
- Number of breaking changes detected
- Contract test coverage

### 8.2 Runtime Validation

**Recommendation**: Enable schema validation in production (with monitoring).

**Python Example**:
```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.middleware("http")
async def validate_responses(request: Request, call_next):
    response = await call_next(request)
    
    # Validate response against schema
    try:
        validate_response_schema(request.url.path, response)
    except ValidationError as e:
        # Log schema violation
        logger.error(f"Response schema violation: {e}")
        # Optionally: emit metric
        metrics.increment("schema_violation", tags={"path": request.url.path})
    
    return response
```

## 9. Evolution

This document will evolve as the system matures:
- Add Pact for consumer-driven contract testing (P1)
- Implement automated contract documentation generation
- Add GraphQL schema validation (if adopted)
- Expand to gRPC contracts (if adopted)

---

**Document Status**: Initial Draft  
**Last Updated**: 2026-01-22  
**Owner**: Engineering Team
