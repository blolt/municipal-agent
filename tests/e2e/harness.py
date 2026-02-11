"""End-to-end test harness for Agentic Bridge system."""
import os
import time
import httpx
from typing import Any, Dict, Optional

from agentic_common.auth import generate_service_token


class Response:
    """Wrapper for agent response."""

    def __init__(self, data: dict):
        self.status = data.get("status", "unknown")
        self.text = data.get("response", "")
        self.thread_id = data.get("thread_id", "")
        self.correlation_id = data.get("correlation_id", "")
        self.raw = data


class E2ETestHarness:
    """Test harness for end-to-end testing.
    
    Provides utilities for:
    - Sending messages to the orchestrator
    - Checking service health
    - Querying tool execution logs
    - Managing test data
    """

    def __init__(
        self,
        orchestrator_url: str = "http://localhost:8000",
        context_url: str = "http://localhost:8001",
        execution_url: str = "http://localhost:8002",
    ):
        """Initialize the test harness.

        Args:
            orchestrator_url: URL of the Orchestrator Service
            context_url: URL of the Context Service
            execution_url: URL of the Execution Service
        """
        self.orchestrator_url = orchestrator_url
        self.context_url = context_url
        self.execution_url = execution_url
        self.service_auth_secret = os.environ.get("SERVICE_AUTH_SECRET", "dev-secret-change-me")
        self.client = httpx.Client(timeout=60.0)  # Increased for Ollama first load

    def _orchestrator_auth_headers(self) -> dict[str, str]:
        """Generate JWT auth headers for Orchestrator (as discord-service)."""
        token = generate_service_token("discord-service", self.service_auth_secret)
        return {"Authorization": f"Bearer {token}"}

    def _internal_auth_headers(self) -> dict[str, str]:
        """Generate JWT auth headers for internal services (as orchestrator-service)."""
        token = generate_service_token("orchestrator-service", self.service_auth_secret)
        return {"Authorization": f"Bearer {token}"}

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def wait_for_services(self, timeout: int = 60) -> bool:
        """Wait for all services to be healthy.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if all services are healthy, False otherwise
        """
        start_time = time.time()
        services = {
            "orchestrator": f"{self.orchestrator_url}/health",
            "context": f"{self.context_url}/health",
            "execution": f"{self.execution_url}/health",
        }

        while time.time() - start_time < timeout:
            all_healthy = True
            for name, url in services.items():
                try:
                    response = self.client.get(url)
                    if response.status_code != 200:
                        all_healthy = False
                        break
                except httpx.RequestError:
                    all_healthy = False
                    break

            if all_healthy:
                return True

            time.sleep(2)

        return False

    def send_message_stream(
        self,
        message: str,
        thread_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> list[str]:
        """Send a message to the orchestrator and get streaming response text chunks.
        
        Args:
            message: User message to send
            thread_id: Optional thread ID
            correlation_id: Optional correlation ID
            
        Returns:
            List of text chunks from the stream
        """
        import uuid
        import json
        
        if thread_id is None:
            thread_id = f"test_thread_{int(time.time())}"
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())
            
        payload = {
            "input": message,
            "thread_id": thread_id,
            "correlation_id": correlation_id,
            "config": {}
        }
        
        chunks = []
        with self.client.stream("POST", f"{self.orchestrator_url}/v1/agent/run", json=payload, headers=self._orchestrator_auth_headers()) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        if data.get("type") == "thinking" and "content" in data:
                             chunks.append(data["content"])
                        elif data.get("type") == "message" and "content" in data:
                             chunks.append(data["content"])
                    except json.JSONDecodeError:
                        continue
        return chunks

    def send_message(
        self,
        message: str,
        thread_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Response:
        """Send a message to the orchestrator and get response.
        
        Args:
            message: User message to send
            thread_id: Optional thread ID for conversation context
            correlation_id: Optional correlation ID for tracking
            
        Returns:
            Response object with agent's reply
            
        Raises:
            httpx.HTTPError: If the request fails
        """
        import uuid
        
        if thread_id is None:
            thread_id = f"test_thread_{int(time.time())}"
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())
        else:
            # Ensure it's a valid UUID string
            correlation_id = str(uuid.UUID(correlation_id))

        payload = {
            "thread_id": thread_id,
            "message": message,
            "correlation_id": correlation_id,
        }

        response = self.client.post(
            f"{self.orchestrator_url}/process",
            json=payload,
            headers=self._orchestrator_auth_headers(),
        )
        response.raise_for_status()
        
        # Handle UUID in response
        data = response.json()
        if "correlation_id" in data and not isinstance(data["correlation_id"], str):
            data["correlation_id"] = str(data["correlation_id"])
        
        return Response(data)

    def get_events(
        self, correlation_id: Optional[str] = None, limit: int = 100
    ) -> list[Dict[str, Any]]:
        """Get events from the Context Service.
        
        Args:
            correlation_id: Optional correlation ID to filter by
            limit: Maximum number of events to return
            
        Returns:
            List of event dictionaries
        """
        # Note: This assumes a GET /events endpoint exists
        # You may need to add this to the Context Service
        params = {"limit": limit}
        if correlation_id:
            params["correlation_id"] = correlation_id

        response = self.client.get(
            f"{self.context_url}/events",
            params=params,
        )
        
        if response.status_code == 404:
            # Endpoint doesn't exist yet
            return []
            
        response.raise_for_status()
        return response.json().get("events", [])

    def get_available_tools(self) -> list[Dict[str, Any]]:
        """Get list of available tools from Execution Service.
        
        Returns:
            List of tool schemas
        """
        response = self.client.get(f"{self.execution_url}/tools", headers=self._internal_auth_headers())
        response.raise_for_status()
        return response.json().get("tools", [])

    def create_sandbox_file(self, filename: str, content: str) -> bool:
        """Create a file in the execution service sandbox.
        
        Args:
            filename: Name of the file to create
            content: Content to write to the file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            result = self.client.post(
                f"{self.execution_url}/execute",
                headers=self._internal_auth_headers(),
                json={
                    "tool_name": "write_file",
                    "arguments": {
                        "path": filename,
                        "content": content,
                    },
                },
            )
            result.raise_for_status()
            data = result.json()
            return data.get("status") == "success"
        except Exception:
            return False

    def read_sandbox_file(self, filename: str) -> Optional[str]:
        """Read a file from the execution service sandbox.
        
        Args:
            filename: Name of the file to read
            
        Returns:
            File content if successful, None otherwise
        """
        try:
            result = self.client.post(
                f"{self.execution_url}/execute",
                headers=self._internal_auth_headers(),
                json={
                    "tool_name": "read_file",
                    "arguments": {"path": filename},
                },
            )
            result.raise_for_status()
            data = result.json()
            
            if data.get("status") == "success":
                output = data.get("output", {})
                
                # Handle different output formats
                if isinstance(output, dict):
                    # Try structuredContent first
                    structured = output.get("structuredContent", {})
                    if structured and "content" in structured:
                        return structured["content"]
                    
                    # Try content array
                    content_array = output.get("content", [])
                    if content_array and len(content_array) > 0:
                        first_item = content_array[0]
                        if isinstance(first_item, dict) and "text" in first_item:
                            return first_item["text"]
                    
                    # Try direct content field
                    if "content" in output:
                        return str(output["content"])
                
                # Fallback to string conversion
                return str(output)
            
            return None
        except Exception as e:
            print(f"Error reading file: {e}")
            return None

    def health_check_all(self) -> Dict[str, bool]:
        """Check health of all services.
        
        Returns:
            Dictionary mapping service names to health status
        """
        services = {
            "orchestrator": f"{self.orchestrator_url}/health",
            "context": f"{self.context_url}/health",
            "execution": f"{self.execution_url}/health",
        }

        health = {}
        for name, url in services.items():
            try:
                response = self.client.get(url)
                health[name] = response.status_code == 200
            except Exception:
                health[name] = False

        return health
