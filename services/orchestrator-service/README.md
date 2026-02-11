# Orchestrator Service

LangGraph-based agent orchestration service for the Municipal Agent platform.

## Overview

The Orchestrator Service is the "brain" of the Municipal Agent. It:
- Executes LangGraph-based agent workflows
- Manages conversation state via PostgreSQL checkpoints
- Integrates with Context Service for event logging and knowledge queries
- Provides a REST API for event processing

## Architecture

```
┌─────────────────────────────────────┐
│     Orchestrator Service            │
│  ┌───────────────────────────────┐ │
│  │  LangGraph Agent Graph        │ │
│  │  - Reasoning Node             │ │
│  │  - Tool Call Node             │ │
│  │  - Response Node              │ │
│  └───────────────────────────────┘ │
│  ┌───────────────────────────────┐ │
│  │  AsyncPostgresSaver           │ │
│  │  (Checkpoint Management)      │ │
│  └───────────────────────────────┘ │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│     Context Service (PostgreSQL)    │
│  - checkpoints (LangGraph-managed)  │
│  - events (our logging)             │
│  - runs (execution tracking)        │
└─────────────────────────────────────┘
```

## Setup

### 1. Install Dependencies

```bash
cd services/orchestrator-service
poetry install
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

Required environment variables:
- `DATABASE_URL`: PostgreSQL connection string (same as Context Service)
- `CONTEXT_SERVICE_URL`: URL of Context Service

**LLM Configuration:**
The service is configured to use **Ollama** for local LLM inference (no API keys needed).

Make sure Ollama is running:
```bash
brew services start ollama
ollama list  # Should show llama3.2:3b
```

If you don't have the model yet:
```bash
ollama pull llama3.2:3b
```

### 3. Start the Service

```bash
poetry run uvicorn orchestrator_service.main:app --host 0.0.0.0 --port 8000 --reload
```

The service will:
1. Initialize AsyncPostgresSaver and create the `checkpoints` table
2. Compile the LangGraph agent
3. Start the FastAPI server on port 8000

## API Endpoints

### Process Event

```bash
POST /process
Content-Type: application/json

{
  "thread_id": "user-123",
  "message": "Hello, I need help with my order",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response:**
```json
{
  "thread_id": "user-123",
  "response": "I'd be happy to help you with your order. Could you please provide your order number?",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Health Check

```bash
GET /health
```

## Agent Graph Flow

1. **Reasoning Node**: LLM analyzes the conversation and decides next action
2. **Tool Call Node**: Executes tools if needed (MVP: placeholder)
3. **Response Node**: Generates final response
4. Loop back to reasoning if tools were called

## Integration with Context Service

The Orchestrator automatically:
- Logs `agent.process_start` events when processing begins
- Logs `agent.process_complete` events on success
- Logs `agent.process_error` events on failure

## Development

### Run Tests

```bash
poetry run pytest tests/ -v
```

### Interactive Documentation

Visit `http://localhost:8000/docs` for Swagger UI.

## Next Steps

- [ ] Add tool integration via MCP
- [ ] Add streaming responses
- [ ] Add multi-agent support
- [ ] Add event queue processing
