# Context Service

The **Context Service** is the state management and knowledge retrieval layer for the Municipal Agent system. It provides persistent storage for agent execution state, event logging, and graph-based knowledge queries.

## Features

- **Event Ingestion**: Immutable log of all ingress/egress events
- **State Management**: LangGraph checkpoint persistence for time-travel debugging
- **Knowledge Retrieval**: Graph-based queries using Apache AGE (MVP: basic queries)
- **Async API**: Built with FastAPI and asyncpg for high-performance async operations
- **Environment-based Configuration**: Flexible configuration via environment variables

## Architecture

```
context-service/
├── src/context_service/
│   ├── api/              # FastAPI routers
│   │   ├── events.py     # POST /events
│   │   ├── state.py      # GET/POST /state/{thread_id}
│   │   └── query.py      # POST /query
│   ├── models/
│   │   └── schemas.py    # Pydantic models
│   ├── db/
│   │   ├── connection.py # Connection pool management
│   │   └── repositories.py # Data access layer
│   ├── config.py         # Settings management
│   └── main.py           # FastAPI application
├── migrations/           # SQL migrations
├── tests/                # Unit and integration tests
└── .env.example          # Environment variable template
```

## Quick Start

### Prerequisites

- Python 3.11+
- Poetry
- Docker & Docker Compose (for PostgreSQL + Redis)
- PostgreSQL client tools (optional, for direct DB access)

### Setup

1. **Start Infrastructure** (from repo root):
   ```bash
   docker-compose up -d
   ```

2. **Apply Database Migrations**:
   ```bash
   cd services/context-service
   
   # Using Docker exec (recommended - no psql client needed)
   docker exec -i municipal-agent-postgres psql -U postgres -d municipal_agent < migrations/001_create_relational_schema.sql
   docker exec -i municipal-agent-postgres psql -U postgres -d municipal_agent < migrations/002_setup_age_extension.sql
   docker exec -i municipal-agent-postgres psql -U postgres -d municipal_agent < migrations/003_setup_pgvector.sql
   
   # Verify migrations
   docker exec municipal-agent-postgres psql -U postgres -d municipal_agent -c "\dt"
   ```

3. **Configure Environment**:
   ```bash
   cp .env.example .env
   # The .env file is used by the FastAPI application (not by psql)
   # Default values work with the Docker setup, edit if needed
   ```

4. **Install Dependencies**:
   ```bash
   poetry install
   ```

5. **Run the Service**:
   ```bash
   poetry run uvicorn context_service.main:app --reload --port 8001
   ```

The service is now running at `http://localhost:8001`

## API Endpoints

### Health Check
```bash
GET /health
```

Returns service health status.

### Events

**Create Event**
```bash
POST /events
Content-Type: application/json

{
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "webhook.slack",
  "source": "slack",
  "payload": {"message": "Hello"}
}
```

### Knowledge Query

**Query Knowledge Graph**
```bash
POST /query
Content-Type: application/json

{
  "query": "test query",
  "strategies": ["graph"]
}
```

> **Note:** State management (checkpoints) is now handled by LangGraph's `AsyncPostgresSaver` in the Orchestrator Service. The `/state` endpoints have been removed from this service.

### Interactive Documentation

Visit `http://localhost:8001/docs` for interactive Swagger UI documentation.

## Testing

### Verify Database Setup

```bash
# Check tables exist
docker exec municipal-agent-postgres psql -U postgres -d municipal_agent -c "\dt"

# Expected output:
#             List of relations
#  Schema |    Name     | Type  |  Owner   
# --------+-------------+-------+----------
#  public | checkpoints | table | postgres
#  public | events      | table | postgres
#  public | runs        | table | postgres
```

### Manual API Testing

1. **Health Check**:
   ```bash
   curl http://localhost:8001/health
   # Expected: {"status":"healthy","service":"context-service"}
   ```

2. **Create an Event**:
   ```bash
   curl -X POST http://localhost:8001/events \
     -H "Content-Type: application/json" \
     -d '{
       "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
       "event_type": "webhook.test",
       "source": "curl_test",
       "payload": {"message": "Test event"}
     }'
   
   # Expected: {"event_id":"...","created_at":"2026-01-21T..."}
   ```

3. **Save a Checkpoint**:
   ```bash
   curl -X POST http://localhost:8001/state/test-thread-123 \
     -H "Content-Type: application/json" \
     -d '{
       "checkpoint_id_str": "checkpoint-1",
       "state_dump": {
         "messages": [{"role": "user", "content": "Hello!"}],
         "metadata": {"test": true}
       }
     }'
   ```

4. **Retrieve the Checkpoint**:
   ```bash
   curl http://localhost:8001/state/test-thread-123
   
   # Should return the checkpoint you just saved
   ```

5. **Verify in Database**:
   ```bash
   docker exec municipal-agent-postgres psql -U postgres -d municipal_agent \
     -c "SELECT event_id, event_type, source, created_at FROM events ORDER BY created_at DESC LIMIT 5;"
   ```

### Automated Testing

Run the test suite:

```bash
# Run all tests
poetry run pytest tests/ -v

# Run with coverage
poetry run pytest tests/ --cov=context_service --cov-report=term-missing

# Run specific test file
poetry run pytest tests/test_events_api.py -v

# Run integration tests only
poetry run pytest tests/test_integration.py -v
```

### Test Structure

- `tests/test_events_api.py` - Unit tests for event ingestion
- `tests/test_state_api.py` - Unit tests for state management
- `tests/test_integration.py` - End-to-end integration tests

## Configuration

The service uses environment variables for configuration. Copy `.env.example` to `.env` and customize as needed.

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres:postgres@localhost:5432/municipal_agent` |
| `DATABASE_POOL_MIN_SIZE` | Minimum connection pool size | `2` |
| `DATABASE_POOL_MAX_SIZE` | Maximum connection pool size | `10` |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `DEBUG` | Enable debug mode | `false` |

### Example Configuration

```bash
# .env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/municipal_agent
DATABASE_POOL_MIN_SIZE=2
DATABASE_POOL_MAX_SIZE=10
LOG_LEVEL=INFO
DEBUG=false
```

**Note:** The `.env` file is read by the FastAPI application via Pydantic Settings. The `psql` command-line tool does not read `.env` files - it uses its own environment variables (`PGHOST`, `PGUSER`, `PGDATABASE`, `PGPASSWORD`) or command-line flags. For database administration tasks, we recommend using `docker exec` commands as shown in the setup instructions.

## Development

### Running Locally

```bash
# Activate virtual environment
source ../../.venv/bin/activate

# Run with auto-reload
poetry run uvicorn context_service.main:app --reload --port 8001

# Run with specific log level
LOG_LEVEL=DEBUG poetry run uvicorn context_service.main:app --port 8001
```

### Code Quality

```bash
# Format code
poetry run ruff format src/

# Lint code
poetry run ruff check src/

# Type checking
poetry run mypy src/
```

### Database Migrations

Migrations are plain SQL files in the `migrations/` directory:

- `001_create_relational_schema.sql` - Core tables (events, runs, checkpoints)
- `002_setup_age_extension.sql` - Apache AGE graph database setup
- `003_setup_pgvector.sql` - pgvector extension for future semantic search

To apply migrations:
```bash
docker exec -i municipal-agent-postgres psql -U postgres -d municipal_agent < migrations/00X_migration_name.sql
```

## Troubleshooting

### Service won't start - "database does not exist"

Ensure the database is created:
```bash
docker exec municipal-agent-postgres psql -U postgres -c "SELECT datname FROM pg_database WHERE datname='municipal_agent';"
```

If not found, the migrations will create it automatically.

### Connection refused

1. Verify Docker containers are running:
   ```bash
   docker-compose ps
   ```

2. Check if PostgreSQL is healthy:
   ```bash
   docker exec municipal-agent-postgres pg_isready -U postgres
   ```

3. Verify port 5432 is accessible:
   ```bash
   nc -zv localhost 5432
   ```

### Test failures

1. Ensure database is running and migrations are applied
2. Check that DATABASE_URL in `.env` is correct
3. Verify no other service is using port 8001

### Viewing logs

```bash
# Docker container logs
docker logs municipal-agent-postgres

# Service logs (if running via nohup)
tail -f /tmp/context-service.log

# Or run with verbose logging
LOG_LEVEL=DEBUG poetry run uvicorn context_service.main:app --port 8001
```

## Production Considerations

### Security

- [ ] Add authentication middleware
- [ ] Enable CORS restrictions (currently allows all origins)
- [ ] Use secrets management for DATABASE_URL
- [ ] Enable SSL for PostgreSQL connection
- [ ] Add rate limiting

### Performance

- [ ] Adjust connection pool sizes based on load
- [ ] Enable query result caching
- [ ] Add database read replicas for scaling
- [ ] Monitor slow queries

### Monitoring

- [ ] Add OpenTelemetry instrumentation
- [ ] Set up Prometheus metrics
- [ ] Configure structured logging
- [ ] Add health check endpoints for dependencies

## License

Part of the Municipal Agent project.
