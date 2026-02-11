# Discord Service

Handles incoming events from Discord and streams responses from the Orchestrator Service back to Discord channels.

## Architecture

```
Discord Gateway → Discord Service → SSE Stream → Orchestrator
   (Events)        (Normalize)     (/v1/agent/run)   (Process)
```

## Development

```bash
# Install dependencies
poetry install

# Run locally
poetry run python -m src.main

# Run tests
poetry run pytest

# Format code
poetry run black src/ tests/
poetry run ruff src/ tests/ --fix
```

## Configuration

Environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DISCORD_BOT_TOKEN` | Discord bot token | Required |
| `SERVICE_TOKEN` | Service token for internal auth | Required |
| `GATEWAY_SERVICE_URL` | Orchestrator Service URL | `http://gateway-service:8000` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `HEALTH_PORT` | Port for health checks | `8003` |

## Discord Setup

1. Create application at https://discord.com/developers
2. Create bot and copy token
3. Enable intents: MESSAGE_CONTENT, GUILD_MESSAGES, DIRECT_MESSAGES
4. Invite bot to server with appropriate permissions
