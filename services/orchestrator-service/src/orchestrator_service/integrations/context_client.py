"""HTTP client for Context Service integration."""
import httpx
from uuid import UUID
from typing import Any, Dict

from agentic_common.auth import generate_service_token
from ..config import settings


class ContextServiceClient:
    """Client for Context Service API."""

    def __init__(self):
        self.base_url = settings.context_service_url
        self.client = httpx.AsyncClient(timeout=30.0)

    def _auth_headers(self) -> dict[str, str]:
        """Generate auth headers with a fresh JWT for each request."""
        token = generate_service_token("orchestrator-service", settings.service_auth_secret)
        return {"Authorization": f"Bearer {token}"}
    
    async def log_event(
        self,
        correlation_id: UUID,
        event_type: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Log an event to Context Service.
        
        Args:
            correlation_id: Event correlation ID
            event_type: Type of event (e.g., 'agent.started')
            payload: Event payload data
            
        Returns:
            Event creation response
        """
        response = await self.client.post(
            f"{self.base_url}/events",
            headers=self._auth_headers(),
            json={
                "correlation_id": str(correlation_id),
                "event_type": event_type,
                "source": "orchestrator",
                "payload": payload
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def query_knowledge(
        self,
        query: str,
        strategies: list[str] = None
    ) -> Dict[str, Any]:
        """Query the knowledge graph.
        
        Args:
            query: Cypher query or natural language query
            strategies: Query strategies (default: ["graph"])
            
        Returns:
            Query results
        """
        if strategies is None:
            strategies = ["graph"]
            
        response = await self.client.post(
            f"{self.base_url}/query",
            headers=self._auth_headers(),
            json={
                "query": query,
                "strategies": strategies
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
