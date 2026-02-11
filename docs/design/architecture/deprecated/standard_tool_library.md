# Standard Tool Library Design

> **DEPRECATED** (2026-02-07): The Standard Tool Library was never implemented as described. The Execution Service uses MCP filesystem tools directly. Preserved for future reference.

---

## 0. Overview

The **Standard Tool Library** is a collection of "batteries-included" capabilities available to every agent in the Municipal Agent system. Just as a standard library in a programming language provides essential functions (I/O, Math, Networking), this library provides the fundamental actions an agent needs to operate autonomously, plan its work, and interact with its environment.

These tools are implemented as **MCP Servers** and are loaded by default into the Execution Service.

## 1. Core Categories

We categorize the standard tools into four pillars of agentic capability:

1.  **Metacognition (Planning):** Tools for managing the agent's own state and progress (e.g., `tasks.md`).
2.  **Perception (Reading):** Tools for understanding the environment (Files, Search).
3.  **Action (Writing):** Tools for affecting the environment (Write File, API Call).
4.  **Interaction (Human):** Tools for communicating with the user.

## 2. Metacognition: The Task Manager

Inspired by the "Task Boundary" concept, this toolset allows the agent to maintain a persistent plan. This is critical for preventing "agent amnesia" during long-running workflows.

### Tool: `manage_task_list`
*   **Description:** Creates, updates, or completes items in a structured task list.
*   **Arguments:**
    *   `action`: `create` | `update` | `complete`
    *   `task_id`: (Optional) ID of the task to modify.
    *   `description`: Text description of the task.
    *   `status`: `pending` | `in_progress` | `done`
*   **Behavior:** Maintains a `tasks.md` file in the agent's workspace.
*   **Why it's useful:**
    *   Allows the agent to break down complex goals (e.g., "Refactor Codebase") into small steps.
    *   Provides a "save point" if the agent crashes or pauses.

### Tool: `reflect`
*   **Description:** Records a "thought" or "observation" to the persistent log without taking external action.
*   **Arguments:**
    *   `content`: The thought content.
    *   `category`: `plan` | `critique` | `observation`
*   **Why it's useful:** Encourages "Chain of Thought" reasoning to be explicit and debuggable.

## 3. Perception: The File System & Knowledge

Agents need to orient themselves in their environment.

### Tool: `list_directory`
*   **Description:** Lists files and folders in a specific path.
*   **Arguments:** `path` (absolute).
*   **Why it's useful:** The agent needs to know what files exist before it can read them.

### Tool: `read_file`
*   **Description:** Reads the contents of a file.
*   **Arguments:** `path` (absolute).
*   **Why it's useful:** Essential for coding, data analysis, and reading config files.

### Tool: `search_knowledge` (RAG)
*   **Description:** Semantically searches the Context Service (Vector DB) for relevant information.
*   **Arguments:** `query` (natural language).
*   **Why it's useful:** Allows the agent to recall business rules ("What is the refund policy?") or past decisions.

## 4. Action: Safe Execution

### Tool: `write_file`
*   **Description:** Creates or overwrites a file.
*   **Arguments:**
    *   `path`: Absolute path.
    *   `content`: The string content.
*   **Safety:** Restricted to specific "workspace" directories to prevent system damage.

### Tool: `fetch_url`
*   **Description:** Performs an HTTP GET request to retrieve web content or API data.
*   **Arguments:** `url`.
*   **Why it's useful:** Accessing external documentation, checking status pages, or reading public APIs.

## 5. Interaction: Human-in-the-Loop

### Tool: `ask_user`
*   **Description:** Pauses execution and requests input from the human operator.
*   **Arguments:**
    *   `question`: The specific question to ask.
    *   `options`: (Optional) A list of valid choices (e.g., ["Yes", "No"]).
*   **Why it's useful:**
    *   **Ambiguity Resolution:** "Did you mean 'Project A' or 'Project B'?"
    *   **Approval:** "I am about to delete 50 files. Proceed?"

## 6. Implementation Strategy (MCP)

All standard tools will be bundled into a single **Core MCP Server** (`mcp-server-core`).

*   **Language:** Python (FastAPI) or Go.
*   **Deployment:** Runs as a sidecar to the Execution Service.
*   **Configuration:** Enabled/Disabled via the `agent_profile` (e.g., a "Read-Only Agent" would not have access to `write_file`).
