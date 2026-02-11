# Context Service Design

---

## 0. Customer Purpose & High-Level Overview

The **Context Service** provides immutable event logging and knowledge retrieval for the Municipal Agent system. It records every agent invocation as a structured event and exposes a query interface for knowledge graph traversal via Apache AGE.

The service is the system's audit trail and long-term memory layer, separate from the Orchestrator's short-term checkpoint state.

### 0.1 Glossary

*   **Context Service:** Event logging and knowledge retrieval service. Port 8001.
*   **InternalEvent:** The canonical event schema stored by the service. Contains correlation_id, event_type, source, timestamp, and payload.
*   **EventRepository:** Data access class for the `events` table using asyncpg.
*   **GraphRepository:** Data access class for Apache AGE Cypher queries.
*   **StateRepository:** (Deprecated) Previously managed checkpoint state. Now handled by `AsyncPostgresSaver` in the Orchestrator.
*   **Apache AGE:** PostgreSQL extension for graph database queries using Cypher.
*   **asyncpg:** Async PostgreSQL driver used for all database operations.

### 0.2 Core Value Propositions

1.  **Audit Trail:** Every agent action is recorded as an immutable event, enabling debugging, compliance, and observability.
2.  **Knowledge Retrieval:** Graph-based queries allow agents to retrieve structured business knowledge (entities, relationships).
3.  **Separation of Concerns:** Long-term event storage is decoupled from short-term agent checkpoint state.

### 0.3 High-Level Strategy

*   **MVP (P0 - Steel Thread):** Event logging with asyncpg, hardcoded graph queries for Apache AGE.
*   **Production (P1 - Extension):** Dynamic Cypher query generation, pgvector integration for semantic search.

---

## 1. System Requirements

1.  **Immutable Event Logging:** Accept and persist events via `POST /events` with no modification or deletion.
2.  **Knowledge Queries:** Execute Cypher queries against Apache AGE via `POST /query`.
3.  **Connection Pooling:** Manage asyncpg pool (2-10 connections) for concurrent access.
4.  **Health Reporting:** Expose `/health` endpoint for container orchestration.

---

## 2. Architecture & Internal Design

### 2.1 API Layer (FastAPI)

*   **`POST /events`** — Accept and store an InternalEvent. Returns `{ event_id, created_at }`.
*   **`POST /query`** — Execute a knowledge graph query. Accepts `KnowledgeQuery` with query string and strategies.
*   **`GET /health`** — Health check.

### 2.2 Repository Layer

Three repository classes follow the Repository pattern:

*   **`EventRepository`** — Inserts events into the `events` table. Uses parameterized asyncpg queries.
*   **`GraphRepository`** — Executes Cypher queries against Apache AGE. MVP: hardcoded query templates. Manages `ag_catalog` search path.
*   **`StateRepository`** — (Deprecated) Previously managed checkpoint state in `runs` and `checkpoints` tables. Checkpoint management is now handled by `AsyncPostgresSaver` in the Orchestrator Service.

### 2.3 Database Layer

*   **Connection Pool:** asyncpg pool initialized on startup (min=2, max=10 configurable).
*   **Search Path:** Sets `ag_catalog` in search path for Apache AGE compatibility.
*   **Lifespan:** Pool created on FastAPI startup, closed on shutdown.

### 2.4 Data Model

**Events Table:**
| Column | Type | Description |
|--------|------|-------------|
| `event_id` | UUID | Primary key, auto-generated |
| `correlation_id` | UUID | Links related events across services |
| `event_type` | VARCHAR | Event category (e.g., "agent.invocation") |
| `source` | VARCHAR | Origin service (e.g., "orchestrator") |
| `timestamp` | TIMESTAMPTZ | Event time |
| `payload` | JSONB | Event-specific data |
| `created_at` | TIMESTAMPTZ | Insertion time |

---

## 3. Interfaces & Interactions

### 3.1 Inbound: Orchestrator → Context Service

*   **Trigger:** Agent invocation start, completion, or error.
*   **Action:** `POST /events`
*   **Data:**
    *   Input: `{ correlation_id, event_type, source, timestamp, payload, source_event_id, source_channel_id, source_user_id, routing, content }`
    *   Output: `{ event_id: str, created_at: str }`

### 3.2 Knowledge Query Interface

*   **Trigger:** Agent needs structured knowledge (P1 feature).
*   **Action:** `POST /query`
*   **Data:**
    *   Input: `{ query: str, strategies: list }`
    *   Output: Query results (MVP: hardcoded response)

### 3.3 Event Schema

```python
class InternalEvent(BaseModel):
    event_id: str | None          # Auto-generated if not provided
    correlation_id: str           # UUID for distributed tracing
    event_type: str               # Event category
    timestamp: str                # ISO 8601
    payload: dict                 # Event data
    source: str                   # Origin service
    source_event_id: str          # Original event ID
    source_channel_id: str        # Source channel
    source_user_id: str           # Source user
    routing: dict                 # Reply routing
    content: str                  # Message content
```

---

## 4. Technology Stack & Trade-offs

### 4.1 asyncpg

*   **Why:** High-performance async PostgreSQL driver. Connection pooling built-in. Direct protocol access (no ORM overhead).
*   **Trade-off:** Raw SQL queries require manual management. Acceptable for the service's simple query patterns.

### 4.2 Apache AGE

*   **Why:** Adds graph database capability (Cypher queries) to PostgreSQL without a separate database.
*   **Trade-off:** Extension adds Docker image complexity. MVP uses hardcoded queries; dynamic generation planned for P1.

### 4.3 Repository Pattern

*   **Why:** Clean separation between API layer and data access. Testable in isolation.
*   **Trade-off:** Additional abstraction layer for simple operations.

---

## 5. External Dependencies

### 5.1 Infrastructure

*   **PostgreSQL 16 (port 5433):** Primary data store with Apache AGE extension.

### 5.2 Internal Services

*   **Orchestrator Service:** Primary client that posts events.

---

## 6. Operational Considerations

### 6.1 Error Handling

*   **Database Errors:** Caught and returned as 500 status with error detail.
*   **Validation Errors:** Pydantic validation returns 422 with field-level errors.
*   **Connection Pool Exhaustion:** Requests queue until a connection is available (pool max = 10).

### 6.2 Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5433/municipal_agent` | PostgreSQL connection |
| `DATABASE_POOL_MIN_SIZE` | `2` | Minimum connection pool size |
| `DATABASE_POOL_MAX_SIZE` | `10` | Maximum connection pool size |
| `LOG_LEVEL` | `INFO` | Logging level |
| `DEBUG` | `false` | Debug mode |

---

## 7. Future Roadmap

### 7.1 Dynamic Graph Queries (P1)

*   Generate Cypher queries dynamically from natural language or structured query objects.
*   Support multi-hop graph traversal for complex business knowledge retrieval.

### 7.2 Semantic Search (P1)

*   pgvector integration for embedding-based retrieval.
*   Hybrid retrieval: combine graph traversal with vector similarity.

### 7.3 Event Query API (P1)

*   `GET /events` endpoint for querying stored events by correlation_id, time range, event_type.
*   Support for event aggregation and analytics.
