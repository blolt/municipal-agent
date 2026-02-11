"""Orchestrator client for Discord Service.

Handles HTTP communication with the Orchestrator Service to forward normalized events.
Uses JWT service tokens for authentication.

Response delivery is now handled by the Orchestrator via Discord MCP tools —
this client only needs fire-and-forget event forwarding.
"""

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from agentic_common.auth import generate_service_token
from src.core.logging import get_logger
from src.events.internal_event import InternalEvent

logger = get_logger(__name__)


class GatewayClient:
    """Client for sending events to the Orchestrator Service."""

    def __init__(self, base_url: str, service_auth_secret: str):
        """Initialize the Orchestrator client.

        Args:
            base_url: Base URL of the Orchestrator Service (e.g., http://orchestrator-service:8000)
            service_auth_secret: Shared secret for generating JWT service tokens
        """
        self.base_url = base_url.rstrip("/")
        self.service_auth_secret = service_auth_secret
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=120.0,  # Agent processing + MCP tool calls can take time
        )

    def _auth_headers(self) -> dict[str, str]:
        """Generate auth headers with a fresh JWT for each request."""
        token = generate_service_token("discord-service", self.service_auth_secret)
        return {"Authorization": f"Bearer {token}"}

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def send_event(self, event: InternalEvent) -> None:
        """Forward an event to the Orchestrator Service (fire-and-forget).

        The Orchestrator processes the event and delivers the response
        to Discord via MCP tools. This method waits for completion but
        does not handle response delivery.

        Args:
            event: The normalized InternalEvent to send
        """
        try:
            # Map InternalEvent to ProcessEventRequest
            payload = {
                "thread_id": event.source_channel_id,
                "message": event.content,
                "correlation_id": event.correlation_id,
                "metadata": event.metadata,
            }

            response = await self.client.post(
                "/process",
                headers=self._auth_headers(),
                json=payload,
            )
            response.raise_for_status()

            logger.debug(
                "Successfully sent event to Orchestrator",
                correlation_id=event.correlation_id,
                status_code=response.status_code,
            )

        except httpx.HTTPStatusError as e:
            logger.error(
                "Orchestrator returned error status",
                correlation_id=event.correlation_id,
                status_code=e.response.status_code,
                response_text=e.response.text,
            )
            raise
        except httpx.RequestError as e:
            logger.error(
                "Failed to send event to Orchestrator",
                correlation_id=event.correlation_id,
                error=str(e),
            )
            raise
