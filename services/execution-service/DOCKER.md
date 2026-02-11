# Docker Deployment Guide

## Running with Docker Compose

### Development Environment

Start the execution service:

```bash
docker-compose up -d execution-service
```

Check status:

```bash
docker-compose ps execution-service
docker-compose logs -f execution-service
```

### Integration Testing Environment

Use the test-specific compose file:

```bash
docker-compose -f docker-compose.test.yml up -d execution-service
```

This uses:
- Different ports (8003 instead of 8002)
- Test database
- Debug logging
- Isolated sandbox directory

### Configuration

The service is configured via environment variables in `docker-compose.yml`:

```yaml
environment:
  PORT: 8002
  LOG_LEVEL: INFO
  MCP_CONFIG_PATH: config/mcp_servers.json
  DEFAULT_TIMEOUT: 30
  SANDBOX_DIRECTORY: /app/sandbox
  MAX_CONCURRENT_EXECUTIONS: 10
```

### Sandbox Volume

The sandbox directory is mounted as a Docker volume:

```yaml
volumes:
  - execution_sandbox:/app/sandbox
```

This ensures:
- Data persistence across container restarts
- Isolation from host filesystem
- Proper permissions

### Health Checks

The service includes a health check:

```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8002/health')"]
  interval: 30s
  timeout: 10s
  start_period: 10s
  retries: 3
```

Check health status:

```bash
docker inspect municipal-agent-execution-service --format='{{.State.Health.Status}}'
```

## Testing Containerized Service

### 1. Create a test file

```bash
docker exec municipal-agent-execution-service sh -c 'echo "test" > /app/sandbox/test.txt'
```

### 2. Read via API

```bash
curl -X POST http://localhost:8002/execute \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "read_text_file", "arguments": {"path": "test.txt"}}' | jq .
```

### 3. Write via API

```bash
curl -X POST http://localhost:8002/execute \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "write_file", "arguments": {"path": "new.txt", "content": "Hello"}}' | jq .
```

### 4. Verify file was created

```bash
docker exec municipal-agent-execution-service cat /app/sandbox/new.txt
```

## Building the Image

Build manually:

```bash
cd services/execution-service
docker build -t execution-service .
```

Or via docker-compose:

```bash
docker-compose build execution-service
```

## Troubleshooting

### Container won't start

Check logs:

```bash
docker-compose logs execution-service
```

### MCP servers not starting

The container includes Node.js for MCP servers. Verify:

```bash
docker exec municipal-agent-execution-service node --version
docker exec municipal-agent-execution-service npx --version
```

### Sandbox permissions

If you encounter permission errors:

```bash
docker exec municipal-agent-execution-service ls -la /app/sandbox
docker exec municipal-agent-execution-service chmod 777 /app/sandbox
```

### Reset sandbox

Remove and recreate the volume:

```bash
docker-compose down -v
docker-compose up -d execution-service
```

## Production Considerations

1. **Use specific image tags** instead of `latest`
2. **Set resource limits**:
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '1.0'
         memory: 1G
   ```
3. **Use secrets** for sensitive configuration
4. **Enable log rotation**
5. **Monitor container health** and restart on failure
