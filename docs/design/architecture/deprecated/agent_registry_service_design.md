# Agent Registry Service Design

> **DEPRECATED** (2026-02-07): This service was never implemented. The design is preserved for future reference. See `system_architecture.md` section 7.2 for current roadmap.

---

## 0. Customer Purpose & High-Level Overview

The **Agent Registry Service** (formerly Management Service) is the source of truth for all persistent configuration in the Municipal Agent system. It manages the lifecycle of Agents, Customers, API Keys, and Billing state.

By separating this "slow-changing" configuration data from the "fast-changing" runtime state (Orchestrator), we achieve:
1.  **Separation of Concerns:** The Orchestrator focuses purely on execution logic.
2.  **Security:** Sensitive customer data (billing, PII) is isolated from the runtime environment.
3.  **Scalability:** The Management Service is Read-Heavy (Config) while the Orchestrator is Compute-Heavy.

### 0.1 Glossary

*   **Agent Registry Service:** The microservice responsible for CRUD operations on Agents and Customers.
*   **Agent Config:** The definition of an agent (Name, System Prompt, Tools, Model).
*   **Control Plane:** The set of services that manage configuration (Agent Registry Service).
*   **Data Plane:** The set of services that process traffic (Gateway, Orchestrator).

### Core Value Propositions

1.  **Centralized Configuration:** A single place to manage all agent definitions.
2.  **Versioning:** Supports versioning of agent configurations (e.g., "v1" vs "v2" prompts).
3.  **Multi-Tenancy:** Enforces strict isolation between different customers' configurations.

---

## 1. System Requirements

The Agent Registry Service must:

1.  **Store Agent Definitions:** Persist System Prompts, Tool definitions, and Model parameters.
2.  **Serve Configs Low-Latency:** Provide agent configurations to the Orchestrator (or Gateway) with <10ms latency.
3.  **Manage Identity:** Store User/Customer profiles and link them to Agents.
4.  **Audit Changes:** Log who changed what configuration and when.

---

## 2. Architecture & Internal Design

### 2.1 Database Schema (PostgreSQL)

The service owns its own logical database (or schema).

```sql
-- Customers / Tenants
CREATE TABLE customers (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    api_key_hash TEXT,
    created_at TIMESTAMP
);

-- Agent Definitions
CREATE TABLE agents (
    id UUID PRIMARY KEY,
    customer_id UUID REFERENCES customers(id),
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP
);

-- Agent Versions (Immutable)
CREATE TABLE agent_versions (
    id UUID PRIMARY KEY,
    agent_id UUID REFERENCES agents(id),
    version_number INT NOT NULL,
    system_prompt TEXT NOT NULL,
    model_name TEXT NOT NULL, -- e.g. "gpt-4-turbo"
    tools JSONB NOT NULL,     -- List of enabled tools
    created_at TIMESTAMP
);
```

### 2.2 API Layer (FastAPI)

*   **Framework:** FastAPI
*   **Auth:** Validates JWTs (User) or Service Tokens (Internal).

---

## 3. Interfaces & Interactions

### 3.1 Public API (via Gateway)

| Method | Path | Description |
| :--- | :--- | :--- |
| `POST` | `/v1/agents` | Create a new Agent |
| `GET` | `/v1/agents` | List Agents |
| `GET` | `/v1/agents/{id}` | Get Agent details |
| `POST` | `/v1/agents/{id}/versions` | Publish new version |

### 3.2 Internal API (for Orchestrator)

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/internal/agents/{id}/active` | Get the active configuration for an agent |

### 3.3 Interaction Flow

**Runtime Flow (Chat):**
1.  **Gateway** receives `WS /v1/chat?agent_id=123`.
2.  **Gateway** calls **Agent Registry Service** `GET /internal/agents/123/active` to fetch the config (System Prompt, Tools).
3.  **Gateway** calls **Orchestrator** `POST /v1/agent/run` passing the *full config* in the payload.
    *   *Benefit:* Orchestrator remains stateless and doesn't need to talk to the DB.

---

## 4. Technology Stack

*   **Language:** Python (FastAPI)
*   **Database:** PostgreSQL (via SQLAlchemy/AsyncPG)
*   **Migrations:** Alembic

---

## 5. Implementation Roadmap

### 5.1 Phase 1: MVP
1.  Scaffold `management-service`.
2.  Implement `agents` and `agent_versions` tables.
3.  Implement CRUD API.
4.  Update Gateway to fetch config before calling Orchestrator.
