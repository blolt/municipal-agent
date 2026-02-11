# Logging Best Practices & Strategy

> **Implementation**: The shared logging library at `libs/agentic-common/src/agentic_common/logging.py` implements these practices using `structlog`. All services import via `from agentic_common import setup_logging, get_logger, bind_context`.

## 1. Core Philosophy: "Logs as Event Streams"

In a microservices architecture, logs should be treated as a continuous stream of time-ordered events. They are the primary interface for observability during development and the source of truth for debugging in production.

### The "Two Streams" Concept
To address the "verbosity" issue, we distinguish between two distinct types of logs:

1.  **Application Logs (The "What")**:
    *   **Audience**: Developers, Product Owners.
    *   **Content**: Business logic events (e.g., "Message received", "Agent decided X", "Tool Y executed").
    *   **Format**: Structured (JSON) or clean, human-readable text.
    *   **Volume**: Low to Medium. High signal-to-noise ratio.

2.  **Service/Platform Logs (The "How")**:
    *   **Audience**: DevOps, SREs.
    *   **Content**: HTTP access logs, database connection pool events, raw exception tracebacks from framework internals, health checks.
    *   **Format**: Often standard formats (Common Log Format) or raw text.
    *   **Volume**: High. Often "noise" during normal operation.

## 2. Best Practices for Python Microservices

### 2.1 Structured Logging (JSON)
For machine parsing and filtering, **Structured Logging** is the industry standard. Instead of:
`"User 123 failed to login: Password incorrect"`
We log:
`{"event": "login_failed", "user_id": 123, "reason": "password_incorrect", "timestamp": "..."}`

**Recommendation**: Use **`structlog`**.
*   It binds context variables (like `correlation_id`) once and they appear in all subsequent logs.
*   It supports different "renderers": JSON for production, colored text for local development.

### 2.2 Context Propagation
Every log line must be traceable to a specific request or workflow.
*   **Correlation ID**: A unique ID generated at the Platform Adapter (e.g., Discord Service) and passed to *every* downstream service via HTTP headers or request payloads.
*   **Worker/Service ID**: Which instance processed this?

### 2.3 Log Levels
Strict discipline on log levels reduces noise:
*   **ERROR**: Actionable failures requiring human intervention (e.g., "Database connection lost", "Payment gateway 500").
*   **WARNING**: Unexpected but handled states (e.g., "Rate limit hit, retrying", "Config missing, using default").
*   **INFO**: Key lifecycle events (e.g., "Service started", "Job completed"). **Do not log every step of a loop here.**
*   **DEBUG**: Granular details for development (e.g., "Payload content", "Variable state"). **Disabled by default in production.**

## 3. Implementation Strategy for Municipal Agent

To solve the "too verbose" issue and separate concerns:

### 3.1 Configuration Changes
We will configure our services to physically separate the log streams.

**Local Development Strategy:**
*   **Application Logs**: Written to a **dedicated file** (e.g., `logs/app.log`).
    *   This allows you to `tail -f logs/app.log` and see *only* business logic.
*   **System/Access Logs**: Continue to `stdout` (Docker Console).
    *   This keeps the "noise" (health checks, HTTP requests) in the Docker window, separate from your clean application stream.

### 3.2 Code Changes (Python)

**1. Centralized Logging Config (`src/core/logging.py`)**
We will update the config to support a `log_file` parameter.

```python
import structlog
import logging
import sys

def setup_logging(log_level="INFO", log_file=None):
    # 1. Configure Standard Library Logging (Uvicorn/System) -> stdout
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level.upper(),
    )
    
    # 2. Configure Structlog (Application)
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer() # Always use JSON for consistency
    ]
    
    # If a file is specified, write to it. Otherwise stdout.
    if log_file:
        # Create a file handler
        handler = logging.FileHandler(log_file)
        logger_factory = structlog.stdlib.LoggerFactory()
        # ... (bind handler to logger)
    else:
        logger_factory = structlog.stdlib.LoggerFactory()

    structlog.configure(
        processors=processors,
        logger_factory=logger_factory,
        # ...
    )
```

**2. Docker Volumes**
We will mount a `./logs` directory into each container so the log files are accessible from your host machine.

```yaml
volumes:
  - ./logs/orchestrator:/app/logs
```

### 3.3 Workflow

1.  **Run System**: `docker-compose up` (Shows system health, errors, access logs).
2.  **Watch Logic**: `tail -f logs/orchestrator/app.log` (Shows *only* "Processing event", "Agent decided X").

### 3.4 GCP & Production Strategy

**"Everything to Stdout/Stderr"**
We will adhere to the 12-Factor App methodology: treat logs as event streams.
*   **Application Logs (Business Logic)** -> `stdout`
*   **System/Error Logs (Health checks, Tracebacks)** -> `stderr`

**How GCP Segregates Logs (vs. CloudWatch):**
Unlike AWS CloudWatch which uses "Log Groups", GCP Cloud Logging uses a unified stream with powerful filtering dimensions:

1.  **Resource Type**: Logs are automatically tagged by the resource (e.g., `resource.type="cloud_run_revision"`).
2.  **Service Name**: You filter by the service name (e.g., `resource.labels.service_name="orchestrator-service"`).
3.  **Log Name**: GCP separates the streams into `projects/[ID]/logs/stdout` and `projects/[ID]/logs/stderr`.
4.  **Structured JSON**: By logging JSON to stdout, we can add our own "grouping" fields.
    *   We will add `service`, `version`, and `correlation_id` to every JSON payload.
    *   In GCP Log Explorer, you can simply query: `jsonPayload.service = "orchestrator-service"`.

### 3.5 Revised Local Workflow

To achieve the "clean console" locally without writing to files, we use standard shell redirection.

**Command:**
```bash
# Pipe stderr (System/Noise) to a file (or /dev/null), keep stdout (App Logic) on console
docker-compose up 2> system.log
```

*   **Result**: Your terminal shows *only* the clean, colored application logs (`stdout`).
*   **Background**: The noisy health checks and uvicorn access logs (`stderr`) are captured in `system.log` for debugging if needed.

## 4. Summary of Recommendations

1.  **Strict Stream Separation**: Configure Python to send App logs to `stdout` and System logs to `stderr`.
2.  **JSON Structure**: Include `service` and `correlation_id` in all payloads for GCP filtering.
3.  **Local Filtering**: Use `2> system.log` to hide noise during development.
4.  **Silence Health Checks**: Still recommended to reduce volume in `stderr`.
