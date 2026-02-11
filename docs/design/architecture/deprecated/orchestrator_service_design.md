# Orchestrator Service Design

> **DEPRECATED** (2026-02-07): This is the original Orchestrator Service design. It has been superseded by the rewritten `orchestrator_service_design.md` in `docs/design/`. Preserved for historical reference.

---

## 0. Customer Purpose & High-Level Overview

The **Orchestrator Service** is the central decision-making component of the Municipal Agent. It is responsible for the "Execution Cycle"—the continuous cycle of observing events, deciding on actions, calling models via the model gateway, retrieving knowledge from the context service, executing tools through the execution service, and reflecting on outcomes. In short, it is responsible for orchestration.

### 0.1 Glossary

*   **Context Service:** The service responsible for interacting with relational and vector databases to provide the model with long-term, exact memory and structured business data.
*   **Vector Database:** A specialized database optimized for storing and querying high-dimensional vectors (embeddings), enabling semantic search capabilities.
*   **Agent State:** The transient, checkpointed state of a specific agent execution thread (e.g., conversation history, current variables). Managed by `AsyncPostgresSaver`.
*   **LangGraph:** A library for building stateful, multi-actor applications with LLMs, used to define the agent's execution graph. An evolution of LangChain that allows for cycles.
*   **Model Gateway:** A library-based abstraction layer using LangChain's `ChatModel` interface to interact with LLM providers (e.g., OpenAI, Anthropic, Ollama). Implemented directly within the Orchestrator Service, not as a separate microservice.
*   **Ingress/Egress Queue:** Message queues (backed by Redis) used for asynchronous communication between the Orchestrator and external systems.


### Core Value Propositions
1.  **Cognitive Control:** Centralizes the decision-making logic, allowing for consistent application of business rules and policies across all agent interactions.
2.  **Stateful Continuity:** Manages the lifecycle of long-running processes, ensuring that multi-turn conversations and asynchronous workflows (e.g., waiting for approval) are handled seamlessly.
3.  **Resilience:** Decouples reasoning from execution and communication, ensuring that failures in external tools or APIs do not crash the core logic.

### High-Level Strategy
*   **MVP (P0 - Steel Thread):** A single-agent architecture using a simple ReAct (Reason+Act) loop, persisted to PostgreSQL. Focus on handling one linear workflow reliably.
*   **Production (P1 - Multi-Agent):** A hierarchical swarm architecture where a "Router Agent" delegates tasks to specialized sub-agents (e.g., "Triage", "Fulfillment").

## 1. System Requirements

To achieve the value propositions, the Orchestrator must:

1.  **Probabilistic Reasoning:** Utilize LLMs to interpret unstructured inputs and select appropriate tools from a dynamic registry.
2.  **Deterministic State Machine:** Enforce a strict Directed Acyclic Graph (DAG) or Cyclic Graph structure (via LangGraph) to manage the flow of execution.
3.  **Loop Detection & Safety:** Automatically detect infinite loops (e.g., agent repeatedly calling the same tool) and halt execution to prevent runaway costs.
4.  **Human-in-the-Loop:** Support "breakpoints" where execution suspends until a human provides input (e.g., approval), then resumes with full context.
5.  **Provider Agnostic:** Interface with LLMs via a **Model Gateway** to switch between providers (OpenAI, Anthropic, Local) without code changes.

## 2. Architecture & Internal Hierarchy

The Orchestrator is composed of five distinct layers that process an event from ingestion to response, aligning with the System Architecture.

### Level 1: Event Consumer
*   **Role:** The entry point. Pulls normalized `InternalEvent` objects from the Ingress Queue.
*   **Responsibility:**
    *   **Ingestion:** Acknowledges receipt to the queue to prevent data loss.
    *   **Correlation:** Extracts the `CorrelationID` to identify the active session/thread.
    *   **Deduplication:** Ensures the same event is not processed twice (idempotency).

### Level 2: State Manager (LangGraph)
*   **Role:** The state manager is responsible for stepping through the LangGraph nodes and managing the state of the agent.
*   **Responsibility:**
    *   **Rehydration:** Fetches the existing `AgentState` directly from PostgreSQL using `AsyncPostgresSaver`.
    *   **Graph Execution:** Steps through the defined LangGraph nodes (Reason -> Tool -> Response).
    *   **Checkpointing:** Persists the modified state to PostgreSQL using `AsyncPostgresSaver` after *every* node transition.
    *   **Time Travel:** Allows rewinding to a previous checkpoint for debugging.

    > [!NOTE]
    > **State vs. Context:**
    > *   **Agent State (Checkpoints):** Short-term "Working Memory". Contains the current conversation history, variables, and execution stack. Managed by `AsyncPostgresSaver`.
    > *   **Context (Context Service):** Long-term "Semantic Memory". Contains business data (Orders, Tickets) and knowledge graph. Managed by the Context Service.
    > The Orchestrator *queries* Context to populate State, but they are stored separately.



### Level 3: Inference Engine (Reasoning)
*   **Role:** Core Reasoning Logic.
*   **Responsibility:**
    *   **Context Assembly:** Constructs the prompt with System Instructions (Persona), Conversation History (from State), and RAG Context.
    *   **Model Invocation:** Calls the LLM using LangChain's `ChatModel` interface (e.g., `ChatOpenAI`, `ChatAnthropic`, `ChatOllama`).
    *   **Decision:** Determines if the agent should call a tool, ask for human help, or provide a final answer based on the LLM response.

### Level 4: Tool Dispatcher
*   **Role:** Tool Execution Manager.
*   **Responsibility:**
    *   **Validation:** If the Inference Engine requests a tool call, this layer validates the arguments against the tool's JSON Schema.
    *   **Dispatch:** Invokes the **Execution Service** (via MCP or direct RPC).
    *   **Feedback:** Receives the tool output (or error) and feeds it back into the State Manager as an observation.

### Level 5: Response Dispatcher
*   **Role:** Response Formatter & Delivery.
*   **Responsibility:**
    *   **Formatting:** When the agent reaches a "Final Answer", this layer formats the response into the appropriate protocol (e.g., Slack JSON, Email MIME).
    *   **Delivery:** Pushes the result to the **Egress Service** queue.

## 3. Component Interactions

### 3.0 Interaction with Ingress Service (via Queue)
*   **Consume:**
    *   **Trigger:** New message in Ingress Queue.
    *   **Action:** `PULL` from Queue.
    *   **Data:** Receives `InternalEvent` with `CorrelationID`.

### 3.1 Interaction with Context Service
*   **Search (RAG):**
    *   **Trigger:** During the "Reasoning" phase.
    *   **Action:** `POST /query`
    *   **Data:** Sends a natural language query; receives relevant text chunks or graph entities.
    *   **Note:** This retrieves *knowledge* to be added to the conversation history. It does not load the agent's execution state.



### 3.2 Model Provider Integration (LangChain)
*   **Implementation:** Direct library integration using LangChain's `ChatModel` classes.
*   **Provider Examples:**
    *   **OpenAI:** `ChatOpenAI(model="gpt-4o", temperature=0)`
    *   **Anthropic:** `ChatAnthropic(model="claude-3-5-sonnet-20241022")`
    *   **Local (Ollama):** `ChatOllama(model="llama3.2:3b")`
*   **Configuration:** Model selection and parameters are configured via environment variables or application config, not a separate service.
*   **Switching Providers:** Changing providers requires updating the Orchestrator's configuration and redeploying the service.

### 3.3 Interaction with Execution Service
*   **Discovery:**
    *   **Trigger:** Startup or Periodic Refresh.
    *   **Action:** Query MCP server for capabilities.
*   **Invocation:**
    *   **Trigger:** Tool Dispatcher receives a valid tool call.
    *   **Action:** `call_tool(name, arguments)`
    *   **Data:** Sends specific parameters; receives structured JSON output.

### 3.4 Interaction with Egress Service (via Queue)
*   **Publish:**
    *   **Trigger:** Response Dispatcher receives formatted payload.
    *   **Action:** `PUSH` to Egress Queue.
    *   **Data:** Sends protocol-specific payload (e.g., Slack JSON) with `CorrelationID`.

## 4. Technology Stack & Trade-offs

### Core Framework: LangGraph (Python)
*   **Why:** Native support for cyclic graphs, persistence, and human-in-the-loop flows.
*   **Trade-off:** Python GIL limitations (mitigated by async I/O and horizontal scaling of containers).

### LangChain (Model Abstraction)
*   **Why:** Provides unified `ChatModel` interface for multiple LLM providers, enabling easy provider switching.
*   **Trade-off:** Adds dependency layer, but essential for provider abstraction and tool integration.

### Runtime: Containerized (Docker/K8s)
*   **Why:** Long-running processes (agents) are better suited for containers than stateless functions (Lambda), especially when maintaining WebSocket connections or complex in-memory state during a run.



## 5. External Dependencies

To ensure reliability and scalability, the Orchestrator relies on the following external systems:

### 5.1 AI Providers (via LangChain ChatModel)
*   **OpenAI:** Primary provider for high-reasoning tasks (e.g., GPT-4o). Accessed via `ChatOpenAI`.
*   **Anthropic:** Secondary/Fallback provider (e.g., Claude 3.5 Sonnet). Accessed via `ChatAnthropic`.
*   **Local Models:** Optional support for self-hosted models (e.g., Llama 3 via Ollama). Accessed via `ChatOllama`.

### 5.2 Infrastructure
*   **PostgreSQL:** Primary persistent store for agent state (checkpoints) and application data.
*   **Redis:** High-throughput message broker for Ingress/Egress queues and shared state (e.g., quota counters).

### 5.3 Security & Compliance
*   **NeMo Guardrails:** Programmable guardrails for LLM input/output filtering.

## 6. Operational Safeguards & Error Handling

### 6.1 Error Propagation
*   **Internal Failures:** If the LLM or a tool fails, the Orchestrator catches the exception, logs it to the Context Service, and pushes a "System Error" message to the Egress Queue.
*   **Egress Failures:** The Orchestrator listens for DLQ callbacks (e.g., "Email Failed") and triggers recovery logic (e.g., retry via SMS).

### 6.2 Safety Guardrails
*   **Input Guardrails:** Scans prompts for jailbreak attempts or malicious intent *before* they reach the Model Gateway.
*   **Output Guardrails:** Scans generated content for PII leakage or toxic responses *after* the Model Gateway returns.

### 6.3 Loop & Cost Control
*   **Loop Detection:** Enforces a maximum number of steps per run (e.g., 20) to prevent infinite recursion.
*   **Quota Management:** Checks Redis-backed counters before execution to enforce tenant budget limits.

## 7. API Specifications (Internal)

The Orchestrator is primarily a consumer of queues, but it exposes a management API.

### `POST /control/stop`
*   **Purpose:** Emergency halt for a runaway agent.
*   **Params:** `thread_id`.

### `POST /control/resume`
*   **Purpose:** Resume a suspended thread (e.g., after human approval).
*   **Params:** `thread_id`, `input` (the approval decision).

### `GET /health`
*   **Purpose:** Liveness check.

## 8. Implementation Roadmap

### 8.1 Phase 1: MVP (P0) - The "Steel Thread"
**Goal:** Deploy a functional Orchestrator Service handling a single linear workflow ("Check Order Status").

1.  **Infrastructure Setup:**
    *   Provision PostgreSQL instance for state persistence.
    *   Deploy Orchestrator container (Python/LangGraph).
2.  **State Definition (v1):**
    *   Define `AgentState` Pydantic model (e.g., `{ messages: List[BaseMessage] }`).
    *   Initialize `AsyncPostgresSaver` for persistence.

3.  **Graph Implementation:**
    *   Implement `Reason` node (LLM call via Model Gateway).
    *   Implement `Tool` node (Hardcoded `check_order_status` function).
    *   Define linear edge logic (`Reason -> Tool -> Reason -> End`).
4.  **Integration Testing:**
    *   Verify end-to-end flow: Webhook Ingress -> Orchestrator -> Tool Execution -> Webhook Reply.

### 8.2 Extension to Production (P1)
**Goal:** Transform the simple linear agent into a robust, multi-agent swarm.

1.  **Hierarchical Graph:**
    *   *From MVP:* Single linear graph.
    *   *To P1:* Implement a "Supervisor" node that routes tasks to specialized sub-graphs (e.g., "Refund Specialist", "Inventory Specialist").
2.  **Dynamic Tool Registry:**
    *   *From MVP:* Hardcoded tool list in the code.
    *   *To P1:* Integrate with Execution Service to dynamically load tools via MCP based on the user's intent.
3.  **Guardrails & Safety:**
    *   *From MVP:* Basic loop detection (max steps).
    *   *To P1:* Integrate NeMo Guardrails to filter inputs (jailbreak attempts) and outputs (PII leakage) before/after the LLM call.

