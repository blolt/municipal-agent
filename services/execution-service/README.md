# Execution Service

The Execution Service provides sandboxed tool execution via the Model Context Protocol (MCP). It enables the Orchestrator to discover and invoke external tools from MCP servers.

## Features

- **MCP Protocol Support**: Full implementation of Model Context Protocol (JSON-RPC 2.0)
- **Tool Discovery**: Automatic discovery of tools from configured MCP servers
- **Sandboxed Execution**: Isolated subprocess execution for security
- **Filesystem Sandboxing**: All file operations restricted to designated sandbox directory
- **Connection Pooling**: Efficient connection management for multiple MCP servers
- **Timeout Control**: Configurable timeouts to prevent runaway processes
- **Structured Errors**: Comprehensive error handling and reporting

## Security

### Filesystem Sandboxing

All filesystem operations are automatically restricted to a designated sandbox directory. This prevents:
- **Directory Traversal**: Attempts to access parent directories (`../`) are blocked
- **Absolute Path Escapes**: Absolute paths outside the sandbox are rejected
- **Symlink Escapes**: Symlinks pointing outside the sandbox are detected and blocked

**Configuration**:
```bash
SANDBOX_DIRECTORY=/tmp/execution-sandbox
```

**Example**:
```bash
# ✅ Allowed: File within sandbox
curl -X POST http://localhost:8002/execute \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "read_text_file", "arguments": {"path": "test.txt"}}'

# ❌ Blocked: File outside sandbox
curl -X POST http://localhost:8002/execute \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "read_text_file", "arguments": {"path": "/etc/passwd"}}'
# Returns: "Path validation failed: Path '/etc/passwd' is outside sandbox directory"
```

## Architecture

```
┌─────────────────┐
│  Orchestrator   │
└────────┬────────┘
         │ REST API
         ▼
┌─────────────────┐
│  API Layer      │
│  (FastAPI)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Connection     │
│  Manager        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  MCP Client     │
│  (stdio)        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Subprocess     │
│  Runtime        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  MCP Servers    │
│  (filesystem,   │
│   fetch, etc.)  │
└─────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for MCP servers)
- Poetry

### Installation

```bash
# Install dependencies
poetry install

# Copy environment template
cp .env.example .env

# Edit .env with your configuration
```

### Running Locally

```bash
# Development mode with auto-reload
poetry run uvicorn src.main:app --reload --port 8002

# Production mode
poetry run uvicorn src.main:app --host 0.0.0.0 --port 8002
```

### Running with Docker

```bash
# Build image
docker build -t execution-service .

# Run container
docker run -p 8002:8002 execution-service
```

## API Endpoints

### Health Check
```http
GET /health
```

### List Available Tools
```http
GET /tools
```

Response:
```json
{
  "tools": [
    {
      "name": "read_file",
      "description": "Read contents of a file",
      "inputSchema": {
        "type": "object",
        "properties": {
          "path": {"type": "string"}
        },
        "required": ["path"]
      }
    }
  ]
}
```

### Execute Tool
```http
POST /execute
Content-Type: application/json

{
  "tool_name": "read_file",
  "arguments": {
    "path": "/tmp/test.txt"
  }
}
```

Response:
```json
{
  "status": "success",
  "output": {
    "content": "File contents here"
  },
  "execution_time_ms": 45
}
```

## Configuration

### MCP Servers

Configure MCP servers in `config/mcp_servers.json`:

```json
{
  "servers": [
    {
      "name": "filesystem",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
      "env": {},
      "timeout": 30
    },
    {
      "name": "fetch",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-fetch"],
      "env": {},
      "timeout": 60
    }
  ]
}
```

### Environment Variables

```bash
# Server configuration
PORT=8002
LOG_LEVEL=INFO

# MCP configuration
MCP_CONFIG_PATH=config/mcp_servers.json
DEFAULT_TIMEOUT=30

# Resource limits
MAX_CONCURRENT_EXECUTIONS=10
```

## Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=src --cov-report=html

# Run only unit tests
poetry run pytest tests/unit/

# Run only integration tests
poetry run pytest tests/integration/
```

## Development

### Code Style

```bash
# Format code
poetry run black src/ tests/

# Lint code
poetry run ruff check src/ tests/

# Type checking
poetry run mypy src/
```

### Adding a New MCP Server

1. Add server configuration to `config/mcp_servers.json`
2. Restart the service
3. Verify tools appear in `GET /tools`

## Troubleshooting

### MCP Server Not Starting

- Check that Node.js is installed and in PATH
- Verify MCP server package is available: `npx -y @modelcontextprotocol/server-filesystem --help`
- Check logs for subprocess errors

### Tool Execution Timeout

- Increase timeout in `config/mcp_servers.json`
- Check if MCP server is hanging (test manually)

### Connection Pool Exhausted

- Increase `MAX_CONCURRENT_EXECUTIONS` in environment
- Check for connection leaks in logs

## Architecture Details

See [Execution Service Design](../../docs/design/architecture/execution_service_design.md) for detailed architecture documentation.

## License

MIT
