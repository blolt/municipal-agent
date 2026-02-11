"""Main entry point for Discord Service.

Runs the Discord Gateway bot and health check API concurrently.
"""

import asyncio
import signal
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn

from src.api.health import app as health_app
from src.core.config import get_settings
from src.core.logging import get_logger, setup_logging
from src.core.gateway_client import GatewayClient
from src.handlers.discord import run_discord_bot

# Setup logging first (settings needed for service name)
_settings = get_settings()
setup_logging(
    service_name=_settings.service_name,
    service_version=_settings.service_version,
    log_level=_settings.log_level,
    log_format=_settings.log_format,
)
logger = get_logger(__name__)


async def run_health_server(port: int) -> None:
    """Run the health check server.

    Args:
        port: Port to listen on
    """
    config = uvicorn.Config(
        health_app,
        host="0.0.0.0",
        port=port,
        log_level="warning",  # Reduce uvicorn noise
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main() -> None:
    """Main entry point - runs Discord bot and health server concurrently."""
    settings = get_settings()

    logger.info(
        "Starting Discord Service",
        service=settings.service_name,
        version=settings.service_version,
        gateway_url=settings.gateway_service_url,
    )

    # Validate required settings
    if not settings.discord_bot_token:
        logger.error("DISCORD_BOT_TOKEN is required")
        sys.exit(1)
    
    if not settings.service_auth_secret:
        logger.error("SERVICE_AUTH_SECRET is required")
        sys.exit(1)

    # Create Gateway client
    gateway_client = GatewayClient(
        base_url=settings.gateway_service_url,
        service_auth_secret=settings.service_auth_secret,
    )

    logger.info("Gateway client created", base_url=settings.gateway_service_url)

    # Create tasks for concurrent execution
    tasks = [
        asyncio.create_task(
            run_discord_bot(
                bot_token=settings.discord_bot_token,
                gateway_client=gateway_client,
            ),
            name="discord_bot",
        ),
        asyncio.create_task(
            run_health_server(settings.health_port),
            name="health_server",
        ),
    ]

    # Handle shutdown gracefully
    loop = asyncio.get_event_loop()

    def shutdown_handler(sig: signal.Signals) -> None:
        logger.info(f"Received signal {sig.name}, shutting down...")
        for task in tasks:
            task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_handler, sig)

    # Wait for tasks and handle completion/errors
    try:
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_EXCEPTION
        )
        
        for task in done:
            if task.exception():
                logger.error(
                    f"Task {task.get_name()} failed with exception",
                    error=str(task.exception()),
                    exc_info=task.exception()
                )
            else:
                logger.info(f"Task {task.get_name()} completed")

        # Cancel remaining tasks
        for task in pending:
            task.cancel()
            
    except Exception as e:
        logger.error("Unexpected error in main loop", error=str(e), exc_info=True)
    finally:
        logger.info("Discord Service stopped")


if __name__ == "__main__":
    asyncio.run(main())
