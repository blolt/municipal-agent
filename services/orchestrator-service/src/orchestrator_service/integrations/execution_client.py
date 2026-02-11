"""Client for Execution Service integration."""
import httpx
from typing import Any, Dict, List

from agentic_common.auth import generate_service_token
from orchestrator_service.config import settings


class ExecutionServiceClient:
    """Client for interacting with the Execution Service."""

    def __init__(self):
        """Initialize the Execution Service client."""
        self.base_url = settings.execution_service_url
        self.client = httpx.AsyncClient(timeout=30.0)

    def _auth_headers(self) -> dict[str, str]:
        """Generate auth headers with a fresh JWT for each request."""
        token = generate_service_token("orchestrator-service", settings.service_auth_secret)
        return {"Authorization": f"Bearer {token}"}

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools from the Execution Service.

        Returns:
            List of tool schemas with name, description, and input schema.

        Raises:
            httpx.HTTPError: If the request fails.
        """
        response = await self.client.get(f"{self.base_url}/tools", headers=self._auth_headers())
        response.raise_for_status()
        data = response.json()
        return data.get("tools", [])

    async def execute_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a tool via the Execution Service.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            Tool execution result with status, output, and error fields.

        Raises:
            httpx.HTTPError: If the request fails.
        """
        response = await self.client.post(
            f"{self.base_url}/execute",
            headers=self._auth_headers(),
            json={"tool_name": tool_name, "arguments": arguments},
        )
        response.raise_for_status()
        return response.json()

    async def health_check(self) -> Dict[str, Any]:
        """Check if the Execution Service is healthy.

        Returns:
            Health status including MCP server status.
        """
        response = await self.client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
