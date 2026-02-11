# LangGraph Architecture Alignment Analysis

## Date: January 21, 2026

## Question

Are we duplicating LangGraph's built-in functionality with our Context Service and microservices architecture?

## TL;DR - Answer

**✅ We are NOT duplicating LangGraph's core functionality.**  
**✅ We are following standard LangGraph production deployment patterns.**

Our architecture appropriately **extends** LangGraph rather than reinventing it. Here's why:

---

## What LangGraph Provides (Built-in)

### 1. Checkpoint Interface
LangGraph provides **checkpoint savers** as an abstraction:
- `PostgresSaver` / `AsyncPostgresSaver` from `langgraph-checkpoint-postgres`
- Automatically creates `checkpoints` table
- Stores: `thread_id`, `checkpoint_id`, `parent_checkpoint_id`, serialized state, metadata

**What they handle:**
- Graph state snapshots after each node execution
- Time-travel debugging
- Resume from interruptions

### 2. Graph Execution Engine
- Node execution
- Edge traversal (conditional, cyclic)
- State updates
- Built-in Human-in-the-Loop (HITL)

### 3. Memory Abstraction
- `PostgresStore` for structured user data (separate from checkpoints)
- Stores in `store` table

---

## What Our Architecture Adds (Appropriate Extensions)

### 1. Context Service - Beyond Checkpointing

**NOT Duplication - We're adding:**

| Feature | LangGraph Built-in | Our Context Service | Why We Need It |
|---------|-------------------|---------------------|----------------|
| Checkpoints | ✅ `checkpoints` table | ✅ `checkpoints` table | **Same** - We use LangGraph's schema |
| Event Log | ❌ Not included | ✅ `events` table | **New** - Immutable audit trail of all ingress/egress |
| Run Tracking | ❌ Basic only | ✅ `runs` table | **New** - Execution metadata, status tracking |
| Graph Queries | ❌ Not included | ✅ Apache AGE (future) | **New** - Knowledge graph for RAG |
| Custom API | ❌ Direct DB access | ✅ REST API | **New** - Orchestration layer abstraction |

**Key Insight:** LangGraph's `PostgresSaver` is **used by** the Orchestrator internally. Our Context Service **wraps** this with additional business logic (event logging, run management, RAG).

### 2. Orchestrator Service - Correct Usage

**✅ This is standard LangGraph deployment:**

```python
# Standard pattern (what we're doing):
from langgraph.checkpoint.postgres import AsyncPostgresSaver

# Orchestrator Service code
checkpointer = AsyncPostgresSaver(db_connection)
graph = StateGraph(AgentState)
# ... define nodes ...
app = graph.compile(checkpointer=checkpointer)
```

**Our Orchestrator Service:**
- Uses LangGraph's `PostgresSaver` internally ✅
- Adds **event queue integration** (Ingress/Egress) ✅
- Adds **Model Gateway abstraction** ✅
- Adds **Tool Dispatcher** (MCP integration) ✅

These are **microservices orchestration concerns**, not LangGraph's job.

### 3. Communication Layer (Ingress/Egress)

**✅ Not duplication:**
- LangGraph doesn't handle Slack webhooks, email polling, etc.
- Our Ingress/Egress services provide this
- Standard microservices pattern

### 4. Execution Service

**✅ Not duplication:**
- LangGraph calls tools, but doesn't manage tool infrastructure
- Our Execution Service provides MCP server management, sandboxing, secret injection
- LangGraph sees this as "external tool" - correct separation

---

## Standard LangGraph Production Architecture

Based on research, **our architecture matches industry best practices:**

### Recommended Pattern (from LangGraph docs)
1. ✅ FastAPI wrapper around LangGraph
2. ✅ PostgreSQL with `langgraph-checkpoint-postgres`
3. ✅ Containerized deployment
4. ✅ Separate stateless API layer from stateful checkpointer
5. ✅ External tool execution with validation

### Where We're Aligned

| LangGraph Best Practice | Our Implementation |
|------------------------|-------------------|
| Use `PostgresSaver` for checkpoints | ✅ Context Service will use it in Orchestrator |
| Expose as API (FastAPI) | ✅ Orchestrator + Gateway Service |
| Keep business logic in graph nodes | ✅ Nodes live in Orchestrator |
| Externalize tools | ✅ Execution Service via MCP |
| Add observability | ✅ Event logging, structured state |
| Use queues for async | ✅ Ingress/Egress via Redis/SQS |

---

## Potential Concern: Are We Over-Engineering?

### The "Monolith vs Microservices" Question

**If LangGraph + PostgreSQL checkpointer is simple, why split into services?**

**Answer: Enterprise requirements**

| Requirement | Monolith Approach | Our Microservices Approach |
|-------------|------------------|---------------------------|
| Multiple channels (Slack, Email, SMS) | All in one app | Ingress/Egress services |
| Tool isolation (security) | Trust all tools | Execution Service (sandboxed) |
| Multi-tenant | Complex in monolith | Service-level isolation |
| Independent scaling | Scale entire app | Scale Orchestrator vs Ingress separately |
| Team ownership | One team | Different teams per service |

### For MVP: Could we simplify?

**Yes, but with trade-offs:**

**Minimal MVP (Single Service):**
```
FastAPI app
  ├── LangGraph with PostgresSaver ← checkpoint handling
  ├── Webhook endpoints ← instead of Discord Service
  ├── Tool functions ← instead of Execution Service
  └── Send via SMTP/Slack SDK ← instead of Egress Service
```

**Why we chose microservices anyway:**
1. Design explicitly calls for asynchronous event handling
2. Tool execution needs sandboxing for security
3. We're building for production scale, not just MVP demo
4. Different failure domains (LLM crash shouldn't break webhooks)

---

## Recommended Adjustments

### 1. Context Service Implementation Detail

**Current Plan:**  
Context Service has its own `checkpoints` table

**Better Approach:**  
Context Service should **delegate** checkpointing to LangGraph's `PostgresSaver` when called by Orchestrator:

```python
# In Orchestrator Service (not Context Service):
from langgraph.checkpoint.postgres import AsyncPostgresSaver

checkpointer = AsyncPostgresSaver(
    conn_string="postgresql://..."  # Points to Context Service DB
)

# Context Service provides:
# - events table
# - runs table  
# - RAG/graph queries
# - API wrapper for observability

# LangGraph provides (via checkpointer):
# - checkpoints table (managed by LangGraph)
```

**Why:** Let LangGraph manage its own schema. We add value on top.

### 2. Schema Alignment

**Update Context Service migrations:**
- Keep `001_create_relational_schema.sql` for `events` and `runs`
- **Remove** custom `checkpoints` table
- Let LangGraph's `PostgresSaver.setup()` create `checkpoints` table
- Add `002_setup_age_extension.sql` for our custom graph schema

### 3. Clear Boundaries

**LangGraph's Job (in Orchestrator):**
- Execute graph nodes
- Manage state transitions
- Persist checkpoints via `PostgresSaver`

**Context Service's Job:**
- Provide database infrastructure
- Event audit log
- Run lifecycle tracking
- RAG knowledge queries
- Metrics/observability API

---

## Conclusion

### ✅ We are NOT duplicating LangGraph

**We are building the appropriate infrastructure AROUND LangGraph:**

```
┌─────────────────────────────────────┐
│      Ingress/Egress Services        │  ← Not LangGraph's job
│   (Webhooks, Queues, Protocols)     │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│    Orchestrator Service             │
│  ┌─────────────────────────────┐   │
│  │   LangGraph Engine          │   │  ← LangGraph's core job
│  │   - Nodes, Edges, State     │   │
│  │   - Uses PostgresSaver      │   │
│  └─────────────────────────────┘   │
│  + Event Queue Integration          │  ← Our orchestration
│  + Model Gateway                    │  ← Our abstraction
│  + Tool Dispatcher                  │  ← Our integration
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│     Context Service (PostgreSQL)    │
│  - LangGraph's checkpoints table    │  ← LangGraph manages
│  - Our events table                 │  ← We manage
│  - Our runs table                   │  ← We manage
│  - Our graph schema (AGE)           │  ← We manage
└─────────────────────────────────────┘
```

### Recommendation

**Keep the microservices architecture** but ensure:
1. Use `langgraph-checkpoint-postgres` in Orchestrator (not custom logic)
2. Context Service provides DB + observability, not checkpoint logic
3. Clear documentation of LangGraph vs our additions

This is **standard LangGraph production architecture**, not duplication.
