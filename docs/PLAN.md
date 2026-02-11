# Design Docs Rewrite Plan

## Guiding Principle

**The codebase is the source of truth.** The 4 implemented services (Orchestrator, Context, Execution, Discord) are the architecture. Documentation that describes services or patterns that don't exist in code will be deprecated or removed.

## Key Discrepancies Found

| # | Area | Doc Says | Code Does |
|---|------|----------|-----------|
| 1 | **Gateway Service** | System architecture describes a separate Gateway Service | Does not exist. Orchestrator exposes SSE directly at `/v1/agent/run` |
| 2 | **Egress Service** | System architecture describes Egress Service | Does not exist. Discord Service handles its own responses |
| 3 | **Agent Registry Service** | Full design doc written | Does not exist. No service, no code, no tests |
| 4 | **Redis** | DOCKER_COMPOSE.md lists Redis as a dependency | Not in `docker-compose.yml` |
| 5 | **Ollama** | Not mentioned in DOCKER_COMPOSE.md | Running in `docker-compose.yml` on port 11434 |
| 6 | **Discord Service** | Not mentioned in DOCKER_COMPOSE.md | Running in `docker-compose.yml` on port 8003 |
| 7 | **Discord health.py** | Title says "Ingress Service" | Should say "Discord Service" |
| 8 | **Discord events/__init__.py** | Docstring says "Ingress Service" | Should say "Discord Service" |
| 9 | **ADR-001** | Status: "Decision Pending" | Decision made and shipped: streaming-first via Orchestrator |
| 10 | **Queue-based architecture** | Docs reference Ingress/Egress queues (Redis) | Replaced by direct SSE streaming |
| 11 | **Testing docs** | 7 docs describe theoretical strategies | Actual tests use harness-based E2E, docker-compose integration, mock-based unit tests |
| 12 | **DOCKER_COMPOSE.md dependency tree** | context-service depends on Redis | Actual: depends only on postgres |
| 13 | **MVP implementation plan** | Phases 0-3 complete, Phase 4 at 20% | Significantly further along; Discord Service implemented, E2E tests written |

---

## Sub-Tasks

### Phase 1: System Architecture (Foundation)

#### Task 1.1 — Rewrite `system_architecture.md`
- Define the architecture as the 4 implemented services + infrastructure (Postgres, Ollama)
- Remove Gateway Service, Egress Service, Agent Registry from architecture
- Update architecture diagram: `Discord ↔ Discord Service → Orchestrator (SSE) → Context/Execution`
- Update service table with actual ports (8000, 8001, 8002, 8003)
- Document the streaming-first pattern as implemented

#### Task 1.2 — Update ADR-001 to "Accepted"
- Change status from "Decision Pending" to "Accepted"
- Add implementation notes referencing actual code paths
- Note that Option A (streaming in Orchestrator) was the chosen path
- Keep analysis intact as historical context

#### Task 1.3 — Deprecate stale design docs
- Move `agent_registry_service_design.md` to `architecture/deprecated/`
- Move `unified_platform_service_design.md` to `architecture/deprecated/` (pattern is now just how Discord Service works)
- Delete `gateway_service_design.md` if it exists (it doesn't appear to)
- Verify existing deprecated folder docs are properly marked

### Phase 2: Service Design Docs

#### Task 2.1 — Rewrite `orchestrator_service_design.md`
- Document actual 3-node LangGraph: reasoning → tool_call → respond
- Document actual SSE event types: thinking, tool_start, tool_result, done
- Document actual endpoints: `/v1/agent/run` (SSE), `/process` (sync), `/health`
- Document integration clients: ContextServiceClient, ExecutionServiceClient
- Document state schema: TypedDict with messages, thread_id, correlation_id, next_action
- Document AsyncPostgresSaver checkpointing
- Remove all references to Ingress/Egress queues, Gateway Service

#### Task 2.2 — Rewrite `discord_service_design.md`
- Document actual implementation: DiscordGatewayHandler + OrchestratorClient
- Document actual flow: discord.py WebSocket → InternalEvent → SSE stream to Orchestrator → edit Discord message
- Document debounce pattern (1s interval for message editing)
- Document retry logic with exponential backoff (3 attempts)
- Document concurrent architecture: bot + health server on separate tasks
- Remove all references to Gateway Service

#### Task 2.3 — Write context service design doc (currently missing from active docs)
- Document actual endpoints: POST /events, POST /query, GET /health
- Document asyncpg connection pooling and repository pattern
- Document Apache AGE integration status (hardcoded MVP queries)
- Document deprecated state endpoints and migration to AsyncPostgresSaver

#### Task 2.4 — Write execution service design doc (currently missing from active docs)
- Document MCP server management: SubprocessRuntime, MCPClient, ConnectionManager
- Document tool discovery (GET /tools) and execution (POST /execute)
- Document sandbox path validation and security model
- Document JSON-RPC 2.0 over stdio protocol

### Phase 3: Infrastructure & Deployment Docs

#### Task 3.1 — Rewrite `DOCKER_COMPOSE.md`
- Remove Redis references
- Add Ollama service (port 11434, model management)
- Add Discord Service (env vars: DISCORD_BOT_TOKEN, APPLICATION_ID, GATEWAY_SERVICE_URL)
- Fix dependency tree to match actual compose
- Update environment variable tables for all services
- Update troubleshooting section

#### Task 3.2 — Update `sidecar_deployment.md`
- Verify alignment with actual docker-compose volume sharing (workspace volume)
- Update service list to actual 4 services + Ollama
- Update cost estimates if needed

#### Task 3.3 — Review `gcp_deployment.md`
- Add "Reference Only — Not Yet Deployed" header
- Update service list to actual 4-service architecture

### Phase 4: Testing Documentation

#### Task 4.1 — Rewrite `testing_strategy.md`
- Align with actual test structure: `services/*/tests/` (unit) + `tests/integration/` + `tests/e2e/`
- Document actual markers: `e2e`, `smoke`, `golden_path`, `slow`
- Document docker-compose.test.yml for integration env
- Reference pytest.ini configuration

#### Task 4.2 — Rewrite `unit_testing.md`
- Document actual unit test patterns per service:
  - Context Service: test_events_api, test_state_api, test_config, test_main, db/test_connection, db/test_repositories, models/test_schemas, api/test_events, api/test_query, api/test_state
  - Execution Service: test_runtime, test_validation, test_path_validation
  - Orchestrator Service: test_streaming (mock-based SSE verification)
  - Discord Service: test_discord_handler, test_orchestrator_client, test_internal_event

#### Task 4.3 — Rewrite `integration_testing.md`
- Document actual infrastructure: docker-compose.test.yml (postgres + redis + execution-service)
- Document conftest.py patterns: session-scoped docker_compose_env, service clients
- Document actual tests: context event logging, execution tool listing/execution, orchestrator-context flow, discord-orchestrator streaming

#### Task 4.4 — Rewrite `e2e_testing.md`
- Document E2ETestHarness class and capabilities
- Document smoke tests: health, simple message, streaming, tools, file CRUD
- Document golden_path tests: conversation, file workflow, context retention, tool discovery
- Document how to run: full docker-compose up + pytest -m e2e

#### Task 4.5 — Review `llm_testing.md`, `performance_testing.md`, `contract_testing.md`
- These describe theoretical/future strategies with no implementation
- Add "Not Yet Implemented" headers
- Keep content as reference for future work

### Phase 5: Supporting Docs

#### Task 5.1 — Update `logging_best_practices.md`
- Verify against actual structlog usage in `libs/agentic-common`
- Check if documented patterns match what services actually import/use

#### Task 5.2 — Update `mvp_implementation_plan.md`
- Mark completed phases (all 4 services built, Docker Compose working, tests written)
- Update Phase 4 progress (E2E tests exist, Discord integration done)
- Note remaining work accurately

#### Task 5.3 — Update `CLAUDE.md`
- Ensure service table matches actual 4 services
- Update "Current Status" section
- Verify common commands still work

#### Task 5.4 — Update testing `README.md`
- Align with actual directory structure and test commands

### Phase 6: Cleanup

#### Task 6.1 — Final pass on deprecated docs folder
- Ensure all deprecated docs are properly marked with reason and date
- Remove broken cross-references from active docs to deprecated content

#### Task 6.2 — Fix Discord Service "Ingress Service" naming in code
- health.py title/description → "Discord Service"
- events/__init__.py docstring → "Discord Service"
- (Small code fix bundled with doc cleanup)

---

## Execution Notes

- Each task is independently reviewable
- Phase 1 goes first — all other docs reference system architecture
- Tasks within a phase can be parallelized
- Task 6.2 is a small code fix included because it's a naming issue found during doc audit
- Total: 6 phases, 20 sub-tasks
