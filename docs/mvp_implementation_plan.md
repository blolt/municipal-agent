# Agentic Bridge MVP Implementation Plan

## 0. Overview

This document tracks the implementation progress of the Agentic Bridge system. The plan is organized into phases that build upon each other, enabling incremental delivery of value.

**Steel Thread Use Case:** Conversational AI agent that can reason, execute filesystem tools via MCP, and maintain conversation context across turns.

**Last Updated:** 2026-02-07

---

## 1. Current Status Summary

| Phase | Status | Completion | Notes |
|-------|--------|------------|-------|
| Phase 0: Foundation | ✅ Complete | 100% | PostgreSQL with AGE + pgvector |
| Phase 1: Context Service | ✅ Complete | 100% | Event logging, asyncpg |
| Phase 2: Orchestrator Service | ✅ Complete | 100% | LangGraph agent, SSE streaming |
| Phase 3: Execution Service | ✅ Complete | 100% | MCP tool execution with sandboxing |
| Phase 4: E2E Integration | ✅ Complete | 100% | Docker Compose, E2E tests passing |
| Phase 5: Discord Service | 🟡 In Progress | 80% | Scaffolding complete, integration pending |

---

## 2. Completed Phases

### 2.1 Phase 0: Foundation ✅

**Goal:** Establish core infrastructure and database layer.

- ✅ PostgreSQL 16 via Docker (port 5433)
- ✅ Apache AGE extension for graph queries
- ✅ pgvector extension for embeddings
- ✅ Relational schema (`events` table)

---

### 2.2 Phase 1: Context Service ✅

**Goal:** Deploy Context Service with event ingestion.

- ✅ `POST /events` — Immutable event logging with asyncpg
- ✅ `POST /query` — Knowledge graph queries (Apache AGE, hardcoded MVP)
- ✅ `GET /health` — Health check
- ✅ Connection pooling (asyncpg, 2-10 connections)
- ✅ Docker Compose configuration

**Port:** 8001

---

### 2.3 Phase 2: Orchestrator Service ✅

**Goal:** Deploy Orchestrator with LangGraph-based agent workflow and SSE streaming.

- ✅ LangGraph 3-node agent graph (reasoning → tool_call → respond)
- ✅ AsyncPostgresSaver for checkpoint persistence
- ✅ ChatOllama (llama3.2:3b, temperature=0)
- ✅ `POST /v1/agent/run` — SSE streaming endpoint
- ✅ `POST /process` — Synchronous endpoint
- ✅ Integration with Context Service (event logging)
- ✅ Integration with Execution Service (tool calls)

**Port:** 8000

---

### 2.4 Phase 3: Execution Service ✅

**Goal:** Enable tool execution via MCP with filesystem sandboxing.

- ✅ SubprocessRuntime for MCP server lifecycle
- ✅ MCPClient with JSON-RPC 2.0 over stdin/stdout
- ✅ ConnectionManager for multi-server tool registry
- ✅ Path validation (sandbox enforcement, traversal prevention)
- ✅ `GET /tools` — 14 filesystem tools discovered
- ✅ `POST /execute` — Tool execution with timeout handling
- ✅ Unit tests (18/18 passing)

**Port:** 8002

---

### 2.5 Phase 4: E2E Integration ✅

**Goal:** Verify complete steel thread from message input to response.

- ✅ Port conflicts resolved (Orchestrator: 8000, Execution: 8002)
- ✅ Unified `docker-compose.yml` with all 6 services (4 app + 2 infra)
- ✅ Service dependency health checks
- ✅ Shared workspace volume for Orchestrator + Execution
- ✅ E2ETestHarness implemented (httpx, SSE support)
- ✅ 5 smoke tests (health, messaging, streaming, tools, file ops)
- ✅ 4 golden path tests (conversation, file workflow, context retention, tool discovery)
- ✅ `docker-compose.test.yml` for integration tests

---

## 3. Current Phase: Discord Service 🟡

### Phase 5: Discord Integration (80%)

**Goal:** Connect Discord bot to Orchestrator via SSE.

**Completed:**
- ✅ Discord Service scaffolding (discord.py + FastAPI health server)
- ✅ InternalEvent normalization from Discord messages
- ✅ OrchestratorClient with SSE streaming + exponential backoff
- ✅ Debounced message editing (1s intervals)
- ✅ Health endpoint on port 8003
- ✅ Docker Compose configuration

**Remaining:**
| Task | Priority | Status |
|------|----------|--------|
| Verify Discord → Orchestrator SSE flow with real bot token | P0 | ⏳ Not Started |
| Test debounced editing with live Discord API | P0 | ⏳ Not Started |
| Error handling for Discord rate limits | P1 | ⏳ Not Started |

---

## 4. Service Ports (Final)

| Service | Port | Status |
|---------|------|--------|
| Orchestrator Service | 8000 | ✅ Active |
| Context Service | 8001 | ✅ Active |
| Execution Service | 8002 | ✅ Active |
| Discord Service | 8003 | ✅ Active |
| PostgreSQL | 5433 | ✅ Active |
| Ollama | 11434 | ✅ Active |

---

## 5. Success Metrics

### MVP (P0) Success Criteria

- [x] All 4 services running via single `docker compose up -d`
- [x] Agent handles conversational queries
- [x] Tool execution (read_file, write_file) sandboxed
- [x] State persistence survives restarts (AsyncPostgresSaver)
- [x] SSE streaming working end-to-end
- [x] E2E tests passing (smoke + golden path)
- [ ] Discord bot delivers responses in real-time

---

**Document Version:** 3.0
**Last Updated:** 2026-02-07
