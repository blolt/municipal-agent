# Agentic Bridge: System Architecture & Technology Stack

> **DEPRECATED** (2026-02-07): This is the original system architecture document. It has been superseded by the rewritten `system_architecture.md` in `docs/design/architecture/`. Preserved for historical reference.

---

## 0. Customer Purpose & High-Level Overview

The **Agentic Bridge** system is designed to solve a critical enterprise challenge: bridging the gap between unstructured human intent and structured, deterministic business logic.

### Core Value Propositions
1.  **Operational Efficiency:** Automates complex workflows that previously required human intervention to translate "fuzzy" requests (emails, chats) into precise, domain-specific technical tool execution and database actions.
2.  **System Integration:** Acts as a reliable connective tissue between modern AI capabilities and legacy systems of record, ensuring that AI agents can safely interact with core business data.
3.  **Reliability in AI:** Mitigates the inherent risks of probabilistic LLMs by enforcing strict validation, type safety, and "human-in-the-loop" checkpoints, ensuring that automated actions are always verifiable and safe.

This architecture enables businesses to deploy autonomous agents that are **action-oriented** and **trustworthy**.



## 1. System Requirements

To achieve the value propositions outlined above, the system must adhere to the following functional requirements:

1.  **Probabilistic Ingestion:** The system must be capable of ingesting high-entropy signals (text, audio, images) and probabilistically extracting structured intents.
2.  **Deterministic Execution:** All business logic must be executed in a deterministic, idempotent environment. The system must never allow an LLM to directly mutate state without an intermediate validation layer.
3.  **Strict Interface Contracts:** The boundary between the probabilistic (AI) and deterministic (Code) domains must be guarded by strict schema validation (JSON Schema/Pydantic).
4.  **Asynchronous State Management:** The system must support long-running, multi-turn workflows, maintaining context and state across asynchronous events (e.g., waiting for an email reply).

## 2. Microservices Breakdown

Based on the **Structured Hybrid DAG** architecture, the system is decomposed into six primary microservices. We split the Communication layer into separate Ingress and Egress services to follow the **CQRS (Command Query Responsibility Segregation)** pattern, allowing for independent scaling and failure isolation.

### 1. Ingress Service
*   **Role:** Handles all incoming asynchronous events. It is optimized for high-throughput write operations.
*   **Responsibility:**
    *   **Listen:** Accept Webhooks (Slack, Twilio) and Poll APIs (IMAP).
    *   **Normalize:** Convert raw payloads into `InternalEvent` schema.
    *   **Tag:** Assign a `CorrelationID` to every incoming event.
    *   **Buffer:** Push events to the Ingress Queue (SQS/PubSub).

### 2. Egress Service
*   **Role:** Handles all outgoing asynchronous messages. It is optimized for reliability and rate limiting.
*   **Responsibility:**
    *   **Consume:** Pull formatted messages from the Egress Queue.
    *   **Transmute:** Convert internal message objects into protocol-specific payloads (MIME, JSON).
    *   **Send:** Call external APIs (SMTP, Slack API, Twilio).
    *   **Retry:** Manage exponential backoff for failed deliveries.

### 3. Orchestrator Service
*   **Role:** Manages the agent lifecycle, maintains the DAG state, and performs probabilistic reasoning. It decides *what* needs to be done next (e.g., "call tool X" or "reply to user") but delegates the actual LLM execution to the Model Gateway.
*   **Internal Hierarchy:**
    *   **Level 1: Event Consumer:** Pulls events from the Ingress Queue.
    *   **Level 2: State Manager:** Rehydrates DAG state from Context Service using `CorrelationID`.
    *   **Level 3: Inference Engine:** LLM runtime for decision making, utilizing a **Model Gateway** to abstract provider differences.
    *   **Level 4: Tool Dispatcher:** Invokes Execution Service via MCP.
    *   **Level 5: Response Dispatcher:** Pushes final responses to the Egress Queue.

### 4. Execution Service
*   **Role:** A hierarchy of stateless, secure execution environments for deterministic logic.
*   **Internal Hierarchy:**
    *   **Level 1: Execution Gateway:** Single internal entry point.
    *   **Level 2: Domain Services:** Logical groupings (Math, Data, API).
    *   **Level 3: Atomic Tools:** Individual functions running within domain services.

### 5. Context Service
*   **Role:** Centralized state management.
*   **Internal Hierarchy:**
    *   **Level 1: Query Engine:** Unified interface for state retrieval.
    *   **Level 2: Storage Engines:** Vector, Relational, and Graph stores.

### 6. Gateway Service (Synchronous API)
*   **Role:** The synchronous API entry point for user-facing applications.
*   **Internal Hierarchy:**
    *   **Level 1: API Gateway:** Authentication, Rate Limiting.
    *   **Level 2: Route Handlers:** Maps endpoints to Orchestrator commands.

## 3. Golden Path Workflows

To illustrate how the system components interact, we define three primary "Golden Paths" representing the core usage patterns.

### Path 1: Asynchronous Action
This is the standard flow for background automation triggered by external events.
*   **Trigger:** Webhook (e.g., Slack message, Email received).
*   **Flow:**
    1.  **Ingress:** Receives payload, validates, and pushes to Queue.
    2.  **Orchestrator:** Consumes event, rehydrates state from Context.
    3.  **Inference:** LLM reasons about the event and decides to call a tool.
    4.  **Execution:** Tool executes (e.g., `check_order_status`).
    5.  **Egress:** Orchestrator formats the result and sends a reply via Egress Service.
*   **Key Feature:** Checkpointing after every step ensures resilience against failures.

### Path 2: Synchronous Query
This flow supports user-facing UI interactions where latency matters.
*   **Trigger:** API Request (e.g., User asks "What did the agent do today?").
*   **Flow:**
    1.  **Gateway:** Authenticates request.
    2.  **Orchestrator:** Runs in **Read-Only Mode** (no side-effect tools allowed).
    3.  **Context:** Performs vector search on past actions.
    4.  **Inference:** LLM summarizes the history.
    5.  **Gateway:** Returns JSON response to the UI.
*   **Key Feature:** Low latency and idempotency (no state mutation).

### Path 3: Human-in-the-Loop
This flow handles high-risk actions requiring approval.
*   **Trigger:** Agent decides to take a sensitive action (e.g., "Refund > $500").
*   **Flow:**
    1.  **Orchestrator:** Detects sensitive tool call.
    2.  **State:** Suspends execution and saves state with status `WAITING_APPROVAL`.
    3.  **Egress:** Sends an "Approve/Deny" button to the user (Slack/Email).
    4.  **... Wait ...** (System sleeps, consuming no compute).
    5.  **Ingress:** Receives "Approve" click.
    6.  **Orchestrator:** Resumes state from where it left off and executes the tool.



## 4. Technology Stack Options & Trade-offs

### A. Ingress & Egress Services

| Option | AWS Implementation | GCP Implementation | Trade-offs |
| :--- | :--- | :--- | :--- |
| **Serverless (Split)** | **Lambda** (Ingress) + **Lambda** (Egress). | **Cloud Functions** (Ingress) + **Cloud Functions** (Egress). | **Pros:** Independent scaling (Ingress scales on traffic, Egress on queue depth). **Cons:** Cold starts. |
| **Containerized (Unified)** | **Fargate** (Single Service). | **Cloud Run** (Single Service). | **Pros:** Simpler deployment; shared code. **Cons:** Scaling Ingress might unnecessarily scale Egress logic. |

### B. Orchestrator Service (Core Logic)

| Option | AWS Implementation | GCP Implementation | Trade-offs |
| :--- | :--- | :--- | :--- |
| **Python + LangGraph** | **ECS (Fargate)** or **EC2**. | **Cloud Run** or **GKE**. | **Pros:** Massive ecosystem; native AI integration; **Pydantic** support. **Cons:** Slower execution speed (GIL). |
| **TypeScript + LangChain** | **Lambda** or **Fargate**. | **Cloud Run**. | **Pros:** Shared language with frontend; strong async I/O. **Cons:** Smaller data science ecosystem. |

### C. Execution Service (Runtime)

| Option | AWS Implementation | GCP Implementation | Trade-offs |
| :--- | :--- | :--- | :--- |
| **Python (Sandboxed)** | **Firecracker** on EC2. | **GKE Sandbox** (gVisor). | **Pros:** Flexible (`pandas`, `scipy`). **Cons:** Security risk; slower cold starts. |
| **Rust (WASM)** | **Lambda** or **Fargate**. | **Cloud Run**. | **Pros:** Speed; safety; isolation. **Cons:** Higher dev effort. |

### D. Context Service (Storage)

| Option | AWS Implementation | GCP Implementation | Trade-offs |
| :--- | :--- | :--- | :--- |
| **PostgreSQL + pgvector** | **Aurora PostgreSQL**. | **Cloud SQL**. | **Pros:** Reliable; ACID; simplified infra. **Cons:** Scale limits for massive vector datasets. |
| **Native Graph DB** | **Neptune**. | **Spanner Graph** / Neo4j. | **Pros:** Deep traversal performance. **Cons:** High complexity/cost. |

### E. Gateway Service (API)

| Option | AWS Implementation | GCP Implementation | Trade-offs |
| :--- | :--- | :--- | :--- |
| **FastAPI (Python)** | **Lambda** or **Fargate**. | **Cloud Run**. | **Pros:** Native **Pydantic** integration; auto-generated OpenAPI; high performance. **Cons:** Python runtime overhead. |
| **Express/NestJS (Node)** | **Lambda** or **Fargate**. | **Cloud Run**. | **Pros:** High throughput; shared types with frontend. **Cons:** Manual validation setup (Zod/Joi). |

### F. LLM Runtime & Providers

| Option | AWS Implementation | GCP Implementation | Trade-offs |
| :--- | :--- | :--- | :--- |
| **Managed APIs (Closed)** | **Bedrock** (Claude, Titan). | **Vertex AI** (Gemini). | **Pros:** Zero infra management; SOTA reasoning. **Cons:** Cost at scale; data privacy concerns. |
| **Self-Hosted (Open)** | **SageMaker** / **EC2** (vLLM). | **GKE** / **Vertex** (vLLM). | **Pros:** Full privacy; lower cost at high volume. **Cons:** High operational complexity. |



## 5. Async Error Propagation & Correlation

Splitting Ingress and Egress introduces complexity in tracking the lifecycle of a request. We address this with **Distributed Tracing** and **Dead Letter Queues (DLQ)**.

### The Correlation ID Strategy
1.  **Creation:** The **Ingress Service** generates a unique `CorrelationID` (UUID) for every incoming event.
2.  **Propagation:** This ID is passed to the Orchestrator, logged in the Context Service, and attached to the final message sent to the **Egress Service**.
3.  **Loop Closure:** If the Egress Service sends an email, it attaches the `CorrelationID` as a custom header (`X-Correlation-ID`). If the user replies, the Ingress Service extracts this ID to thread the conversation correctly.

### Error Scenarios
*   **Ingress Failure:** If a webhook fails validation, the Ingress Service rejects it immediately (400 Bad Request). The sender knows instantly.
*   **Orchestration Failure:** If the LLM hallucinates or crashes, the Orchestrator catches the exception, logs it to the Context Service, and pushes a "System Error" message to the Egress Queue to notify the user.
*   **Egress Failure:** If an email bounces or an API is down:
    1.  **Retry:** Egress Service retries with exponential backoff.
    2.  **DLQ:** After max retries, the message moves to a Dead Letter Queue.
    3.  **Callback:** A DLQ Monitor triggers a callback to the Orchestrator: "Message X failed."
    4.  **Recovery:** The Orchestrator decides the next step (e.g., try a different channel: "Email failed, sending SMS").

## 6. Operational Safeguards & Testing Strategy

Deploying autonomous agents requires robust safeguards to prevent hallucinations, infinite loops, and security vulnerabilities.

### A. Observability: The "Flight Recorder"
Standard logging is insufficient for debugging agent reasoning. We employ a **Trace-First** approach using **LangGraph Checkpointers**.
*   **Checkpointing:** The state of the DAG is persisted to Postgres after every node execution.
*   **Time Travel:** This allows developers to "rewind" a failed agent session to the exact step before the error, inspect the state, and replay it with a fix.

### B. Security & Validation (The "Sandwich" Pattern)
We distinguish between runtime guardrails and offline evaluation.

1.  **Input Guardrails (Runtime):** A security layer (e.g., NeMo Guardrails) that sits *before* the Model Gateway. It scans prompts for jailbreak attempts or malicious intent before they reach the LLM.
2.  **Output Guardrails (Runtime):** A validation layer that sits *after* the Model Gateway. It scans generated content for PII leakage or toxic responses before returning them to the user.
3.  **Offline Evaluation (Testing Service):** A separate pipeline that runs the agent against a "Golden Dataset" of known inputs and expected outputs. This calculates metrics (e.g., Pass@k, Accuracy) to validate performance *before* deployment.

### C. Cost & Loop Control
To prevent runaway costs from infinite loops:

1.  **Loop Detection (Middleware):** Implemented within the **Orchestrator** to detect and halt infinite recursion (e.g., max 20 steps per request) with low latency.
2.  **Quota Management (Service):** A shared **Redis-backed** counter that tracks aggregate token usage and cost per tenant, enforcing budget limits over time.



## 7. Roadmap: MVP & Future Design

To manage complexity, we will adopt a phased implementation approach, starting with a "Steel Thread" MVP.

### Phase 0: Design Priority & Next Steps
To ensure a coherent MVP, we will design services in dependency order, starting with the core state and logic.

1.  **Priority 1: Orchestrator & Context (The Core)**
    *   **Dependency:** None.
    *   **Tasks:** Define `AgentState` Pydantic schema; Design LangGraph topology (Nodes/Edges); Setup Postgres checkpointing schema.
2.  **Priority 2: Communication Layer (Ingress/Egress)**
    *   **Dependency:** Orchestrator (needs to know what events to handle).
    *   **Tasks:** Define `InternalEvent` unified schema; Design Webhook handlers for Slack/Email; Design Egress message templates.
3.  **Priority 3: Execution Service (The Tools)**
    *   **Dependency:** Orchestrator (needs to know what tools are available).
    *   **Tasks:** Define MCP Server interface; Implement "Steel Thread" tool (e.g., `check_order_status`).
4.  **Priority 4: Gateway Service (The API)**
    *   **Dependency:** Orchestrator (needs to know what commands to expose).
    *   **Tasks:** Define OpenAPI spec for triggering agent runs; Implement auth middleware.

### Phase 1: The "Steel Thread" MVP
**Goal:** Prove the architecture with a single end-to-end flow, minimizing component complexity.

*   **Ingress:** Webhook only (e.g., Mock Slack).
*   **Orchestrator:** Single Agent (No multi-agent swarm).
*   **Memory:** Postgres only (No Graph DB yet).
*   **Tools:** 1 Read-Only Tool (e.g., "Check Order Status").
*   **Egress:** Webhook reply.

### Phase 2: Hardening & Scale (Future Design Tasks)
Once the Steel Thread is live, we will tackle the following design tasks:

1.  **API Spec:** Define strict OpenAPI contracts for Gateway <-> Orchestrator.
2.  **Graph Schema:** Design the Apache AGE schema for complex RAG.
3.  **Tool Registry:** Implement full MCP server for dynamic tool loading.
4.  **Guardrails:** Integrate NeMo/Llama Guard for production security.

## 8. Appendices

### Appendix A: Deep Dive: LangGraph for Orchestration

**LangGraph** is a library for building stateful, multi-actor applications with LLMs. Unlike simple chains (DAGs), LangGraph supports **cycles**, which are essential for agentic loops (Reason -> Act -> Observe -> Reason).

#### Core Concepts
1.  **State Schema:** A strictly typed object (**Pydantic Model**) that represents the entire state of the agent. Every node receives this state, modifies it, and passes it on.
2.  **Nodes:** Python functions that perform work (Reasoning, Tool Execution, Human Interrupt).
3.  **Edges:** Control flow logic (Conditional, Cyclic).

#### Why LangGraph?
*   **Persistence:** Built-in checkpointers save state after every step, enabling long-running workflows.
*   **Control:** Explicit state machines replace opaque agent loops.
*   **Human-in-the-loop:** Native support for interrupting the graph for user confirmation.

### Appendix B: Deep Dive: The Pydantic Ecosystem

**Pydantic** is the backbone of modern Python data validation and the de-facto standard for interfacing with LLMs. It is not strictly *required* for LangGraph, but it is highly recommended and deeply integrated into the entire "Golden Path" stack.

#### Role in the Stack
1.  **Orchestrator (LangGraph):**
    *   **State Definition:** LangGraph uses Pydantic models to define the `State` schema. This ensures that every node in the graph receives data in a guaranteed format.
    *   **Structured Output:** When the LLM generates a response, Pydantic is used to validate that the JSON output matches the expected schema (e.g., `class ToolCall(BaseModel): ...`). If validation fails, the error is fed back to the LLM for self-correction.
2.  **Gateway Service (FastAPI):**
    *   **API Contracts:** FastAPI (built on Pydantic) automatically generates OpenAPI (Swagger) documentation from Pydantic models. This means the API contract is always in sync with the code.
    *   **Request Validation:** Incoming JSON requests are automatically validated against Pydantic models before they even reach the business logic.
3.  **Execution Service (MCP):**
    *   **Tool Definitions:** The Model Context Protocol (MCP) relies on JSON Schema to define tools. Pydantic models can be instantly exported to JSON Schema (`MyModel.model_json_schema()`), making it the perfect bridge between Python code and MCP.

#### Why Pydantic?
*   **Type Safety:** Enforces strict typing at runtime, catching errors early.
*   **LLM Integration:** Most LLM providers (OpenAI, Anthropic) and frameworks (LangChain, LlamaIndex) treat Pydantic as a first-class citizen for defining structured outputs.
*   **Ecosystem:** It unifies the stack. The same model used to validate an API request in the Gateway can be passed to the Orchestrator, used in the LangGraph state, and sent to the LLM as a prompt constraint.

### Appendix C: Deep Dive: Apache AGE for Agentic Graph RAG

**Apache AGE (Agens Graph Extension)** is a PostgreSQL extension that provides graph database functionality. It enables users to store and query graph data (nodes and edges) alongside standard relational data in the same database instance.

#### Why Apache AGE?
*   **Unified Storage:** Eliminates the need for a separate Graph DB (like Neo4j).
*   **Hybrid Queries:** Allows joining graph data with relational data in a single SQL query.
*   **OpenCypher Support:** Supports the standard Cypher query language.

#### Architecture Integration
1.  **Storage:** Graph data is stored in specific schemas within PostgreSQL.
2.  **Querying:** The Context Service uses the `cypher()` function wrapper within SQL.
3.  **Agentic RAG Workflow:** Orchestrator requests context -> Context Service runs vector search -> Context Service traverses graph edges -> Results returned.

#### Trade-offs vs Native Graph DBs
*   **Pros:** Zero extra infra; ACID compliance; familiar tooling.
*   **Cons:** Performance lag on massive datasets; verbose query syntax.

### Appendix D: Deep Dive: LLM Runtime & Inference Strategy

The system employs a **Hybrid Inference Strategy** to balance reasoning capability, latency, and cost. We do not rely on a single model; instead, we route tasks to the most appropriate model based on complexity.

#### Model Selection Hierarchy
1.  **Reasoning Models (High Intelligence / High Latency):**
    *   **Use Case:** Complex orchestration, planning, fallback handling.
    *   **Examples:** GPT-4o, Claude 3.5 Sonnet, Gemini 1.5 Pro.
    *   **Deployment:** Managed API (via Bedrock/Vertex).
2.  **Task Models (Medium Intelligence / Low Latency):**
    *   **Use Case:** Summarization, extraction, classification.
    *   **Examples:** GPT-4o-mini, Claude 3 Haiku, Gemini 1.5 Flash.
    *   **Deployment:** Managed API.
3.  **Local/Private Models (Specialized / Zero Data Leakage):**
    *   **Use Case:** PII processing, high-volume simple tasks.
    *   **Examples:** Llama 3, Mistral.
    *   **Deployment:** Self-hosted via **vLLM** or **Ollama** on GPU instances.

#### The Model Gateway Pattern
To manage this complexity, the **Orchestrator Service** does not call LLMs directly. It routes requests through a **Model Gateway** (internal module or service).

*   **Unified Interface:** The rest of the system sees a single `generate(prompt, schema)` interface.
*   **Router:** Decides which model to call based on the task type.
*   **Fallback Logic:** If the primary provider (e.g., OpenAI) is down, the gateway automatically retries with a secondary provider (e.g., Anthropic) without the agent knowing.
*   **Cost Tracking:** Centralized logging of token usage and cost per tenant.

#### Orchestrator vs. Model Gateway: Responsibilities
It is critical to distinguish between *reasoning* (Orchestrator) and *routing* (Gateway).

| Feature | Orchestrator Service | Model Gateway |
| :--- | :--- | :--- |
| **Primary Focus** | **Business Logic & State** | **Infrastructure & Reliability** |
| **Decision Scope** | "What should the agent do next?" (e.g., Tool Use vs. Final Answer) | "Which model should process this prompt?" (e.g., GPT-4 vs. Claude 3) |
| **Context Awareness** | High (Knows user history, DAG state, tool outputs). | Low (Stateless; sees only the immediate prompt). |
| **Change Frequency** | High (As business rules evolve). | Low (Only when adding new model providers). |

This decoupling ensures that the agent's logic is not hardcoded to a specific provider. If we need to switch from OpenAI to Anthropic for cost reasons, we update the **Model Gateway** configuration. The **Orchestrator** (and the complex DAG logic within it) remains completely unchanged.
