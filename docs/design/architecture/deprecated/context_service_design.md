# Context Service Design

> **DEPRECATED** (2026-02-07): This is the original Context Service design. It has been superseded by the rewritten `context_service_design.md` in `docs/design/`. Preserved for historical reference.

---

## 0. Customer Purpose & High-Level Overview

The **Context Service** is a centralized data persistence layer that provides the Orchestrator Service with access to structured business data, event logs, and knowledge graphs. It manages interactions with relational databases (PostgreSQL), graph databases (Apache AGE), and vector databases (pgvector) to enable exact retrieval, semantic search, and relationship traversal.

**Primary Functions:**
1.  **Event Logging:** Stores immutable records of all system events (ingress, egress, tool executions) for auditability and debugging.
2.  **Knowledge Storage:** Maintains a graph database of business entities (Customers, Orders, Tickets) and their relationships for context-aware reasoning.
3.  **Semantic Search:** Provides vector-based similarity search over embeddings to retrieve relevant information based on natural language queries.


### 0.1 Glossary

*   **Context Service:** A centralized data persistence layer that manages interactions with relational, graph, and vector databases to provide structured business data and event logs.
*   **Vector Database:** A specialized database optimized for storing and querying high-dimensional vectors (embeddings), enabling semantic search capabilities.
*   **Orchestrator Service:** The service responsible for managing agent execution, state transitions, and tool invocation.
*   **Agent State:** The transient, checkpointed state of a specific agent execution thread (e.g., conversation history, current variables). Managed by `AsyncPostgresSaver` in the Orchestrator Service.
*   **Knowledge Graph:** A structured representation of entities and their relationships, stored in a graph database to enable complex reasoning and traversal.
*   **Apache AGE:** A PostgreSQL extension that provides graph database functionality (OpenCypher support) within the relational database.
*   **pgvector:** A PostgreSQL extension for vector similarity search, used for semantic retrieval.
*   **Relational Database:** A database based on the relational model (PostgreSQL), used for storing structured data like events and run logs.




### Core Value Propositions
1.  **Continuity:** Enables long-running, multi-turn workflows that can span days (e.g., waiting for an email reply) without losing context.
2.  **Grounding:** Provides agents with access to structured business data (Orders, Tickets) and unstructured relationships (Knowledge Graph), reducing hallucinations.
3.  **Auditability:** Maintains an immutable log of all state changes and decisions, ensuring every agent action is traceable.

### High-Level Strategy
To ensure the system solves real user problems while maintaining flexibility, we adopt a "Steel Thread" approach for the MVP (P0), while designing for extensibility (P1).
*   **MVP (Steel Thread):** Focuses on a **Customer Support Agent** scenario, requiring identity resolution and transactional lookups.
*   **P1 (Extensibility):** Supports multi-tenancy and custom schemas via a dynamic registry, allowing customers to define their own domain entities.

## 1. System Requirements

To achieve the value propositions above, the Context Service must adhere to the following functional requirements:

1.  **Unified Storage:** Must store relational data (events, runs), graph data (entities, relationships), and vector embeddings in a single, consistent system to minimize infrastructure complexity.
2.  **Time-Travel Debugging:** Must support checkpointing of the DAG state after every node execution, allowing developers to "rewind" and replay failed sessions.
3.  **Hybrid Retrieval:** Must support queries that combine semantic search (vector), structural traversal (graph), and precise filtering (SQL) in a single request.
4.  **Dynamic Extensibility:** Must allow the definition of new graph labels and properties at runtime without requiring database schema migrations (for P1).
5.  **Strict Isolation:** Must enforce data isolation between tenants at the row level.

## 2. Schema Design

### 2.1 Relational Schema (PostgreSQL)
These tables handle the immutable log of events and the operational state of agents.

#### `events`
Immutable log of all ingress and egress signals.
```sql
CREATE TABLE events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id UUID NOT NULL, -- Links related events in a thread
    event_type VARCHAR(50) NOT NULL, -- e.g., 'webhook.slack', 'email.received', 'tool.output'
    source VARCHAR(100) NOT NULL, -- e.g., 'slack', 'gmail', 'orchestrator'
    payload JSONB NOT NULL, -- The raw data
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed boolean DEFAULT FALSE
);
CREATE INDEX idx_events_correlation_id ON events(correlation_id);
```

#### `runs`
Tracks agent execution sessions.
```sql
CREATE TABLE runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id UUID NOT NULL REFERENCES events(correlation_id), -- Trigger event
    status VARCHAR(20) NOT NULL, -- 'running', 'completed', 'failed', 'waiting'
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    metadata JSONB -- Config used for this run
);
```

#### `checkpoints`
**Managed Externally:** This table is managed directly by LangGraph's `AsyncPostgresSaver` library in the Orchestrator Service. It is not part of the Context Service's public schema or API.


### 2.2 Graph Schema (Apache AGE)
Stores entities and relationships extracted from unstructured data.

**Note:** The labels below represent the **Steel Thread** configuration. In a production P1 scenario, these would be configurable per tenant.

**Graph Name:** `knowledge_graph`

#### Vertex Labels
*   `Entity`: Base label.
*   `Person`: `{name, email, role}`
*   `Order`: `{order_id, status, amount}`
*   `Product`: `{sku, name, description}`
*   `Ticket`: `{ticket_id, priority, summary}`

#### Edge Labels
*   `CREATED`: `Person -> Ticket`
*   `ORDERED`: `Person -> Order`
*   `CONTAINS`: `Order -> Product`
*   `MENTIONS`: `Ticket -> Product`

**Example Query (OpenCypher):**
```sql
SELECT * FROM cypher('knowledge_graph', $$
    MATCH (p:Person)-[:ORDERED]->(o:Order)
    WHERE p.email = 'user@example.com'
    RETURN o
$$) as (o agtype);
```

## 3. API Interface (Query Engine)

The Context Service exposes a REST API for the Orchestrator.

### 3.1 Ingestion
*   `POST /events`: Store a new event.
    *   Input: `InternalEvent` schema.
    *   Output: `event_id`.

### 3.2 State Management
**Deprecated:** State persistence is now handled directly by the Orchestrator Service using LangGraph's `AsyncPostgresSaver`. The Context Service no longer exposes state management endpoints.


### 3.3 Knowledge Retrieval
*   `POST /query`: Unified search endpoint.
    *   Input:
        ```json
        {
            "query": "What orders did user@example.com place?",
            "strategies": ["graph", "vector"],
            "filters": {"time_range": "7d"}
        }
        ```
    *   Output: List of relevant context chunks.

## 4. Orchestrator Integration

1.  **Startup:** Orchestrator initializes `AsyncPostgresSaver` to connect to the database.
2.  **Execution:**
    *   Orchestrator receives an event -> calls `POST /events`.
    *   Orchestrator needs context -> calls `POST /query`.
3.  **Checkpointing:** Orchestrator writes directly to the `checkpoints` table via `AsyncPostgresSaver`.


## 5. External Dependencies

To ensure reliability and scalability, the Context Service relies on the following external systems:

### 5.1 Infrastructure
*   **PostgreSQL:** Core database engine (v16+) for relational data.
*   **Apache AGE:** Extension for graph database functionality (OpenCypher support).
*   **pgvector:** Extension for vector similarity search.

## 6. Limitations & Trade-offs (Apache AGE)
*   **Deep Traversal:** Performance may degrade for >3 hop queries compared to Neo4j. We mitigate this by keeping graph queries scoped to specific entities (e.g., "Customer's recent orders").
*   **Tooling:** Less mature visualization tools than Neo4j Bloom. We will rely on simple SQL-based inspection for MVP.

## 7. Future Migration Paths & Alternatives

If the system outgrows Apache AGE (e.g., due to graph size > 100M nodes or deep traversal latency), the following alternatives offer viable migration paths while preserving the Cypher-based logic.

### 6.1 Memgraph (Performance Upgrade)
*   **Why:** High-performance, in-memory graph database written in C++.
*   **Fit:** Fully compatible with openCypher and the Bolt protocol. Strong Python ecosystem (`GQLAlchemy`).
*   **Trade-off:** Requires managing a separate database instance (unlike AGE which lives in Postgres).

### 6.2 Amazon Neptune (Managed Scale)
*   **Why:** Fully managed AWS service with high availability and auto-scaling.
*   **Fit:** Native support for openCypher. Good if the rest of the stack moves to deep AWS integration.
*   **Trade-off:** Vendor lock-in; higher cost; eventual consistency model can be tricky for some agentic state.

### 6.3 Neo4j (Enterprise Features)
*   **Why:** The industry standard with the richest ecosystem (Bloom, Graph Data Science library).
*   **Fit:** Best if we need advanced enterprise features like sharding (Fabric) or complex RBAC.
*   **Trade-off:** Java-based (heavier resource footprint); expensive enterprise licensing; "Community Edition" has limitations.

## 8. Implementation Roadmap

### 8.1 Phase 1: MVP (P0) - The "Steel Thread"
**Goal:** Deploy a functional Context Service supporting the single "Customer Support" use case.

1.  **Infrastructure Setup:**
    *   Provision PostgreSQL 16 instance.
    *   Install `age` and `pgvector` extensions.
2.  **Schema Migration (v1):**
    *   Apply Relational Schema (`events`, `runs`, `checkpoints`).
    *   Apply Graph Schema (Hardcoded labels: `Person`, `Order`, `Ticket`).
3.  **API Implementation:**
    *   Implement `POST /events` (Ingestion).
    *   (State Management is handled by library).
    *   Implement `POST /query` with basic SQL-based graph traversal (no dynamic query generation yet).
4.  **Integration Testing:**
    *   Verify end-to-end flow with a mock Orchestrator.

### 8.2 Extension to Production (P1)
**Goal:** Transform the hardcoded MVP into a multi-tenant platform.

1.  **Dynamic Schema Engine:**
    *   *From MVP:* Hardcoded `CREATE_VLABEL` commands.
    *   *To P1:* Implement `POST /config/schema` to dynamically execute AGE label creation commands based on customer config.
2.  **Multi-Tenancy Layer:**
    *   *From MVP:* Single tenant (implicit).
    *   *To P1:* Add `tenant_id` column to all tables; enable RLS policies; update API to require `X-Tenant-ID` header.
3.  **Advanced Query Planner:**
    *   *From MVP:* Fixed SQL templates for graph queries.
    *   *To P1:* Implement a query builder that translates abstract JSON filters into dynamic Cypher/SQL queries based on the registry.
