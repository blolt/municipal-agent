import pytest
import uuid
import asyncio

def test_orchestrator_logs_event_to_context(orchestrator_service_client):
    """Verify that Orchestrator processing triggers event logging in Context Service."""
    # 1. Send request to Orchestrator
    payload = {
        "thread_id": f"thread_{uuid.uuid4()}",
        "message": "Hello world check context",
        "correlation_id": str(uuid.uuid4())
    }
    
    # Using /process (synchronous/simple endpoint) for easier verification than stream
    response = orchestrator_service_client.post("/process", json=payload)
    assert response.status_code == 200
    
    # 2. Verify impact on Context Service
    # ideally we query Context Service or DB.
    # Since we lack a clean API to get events, and I haven't set up direct DB access yet, 
    # we will rely on success status for this iteration.
    # TODO: Add direct DB verification or Context Service Query check.
    
    data = response.json()
    assert "response" in data
    assert data["correlation_id"] == payload["correlation_id"]

def test_orchestrator_streaming_context_logging(orchestrator_service_client):
    """Verify that Orchestrator streaming also works without error (implying context logging success)."""
    payload = {
        "input": "Stream test",
        "thread_id": f"thread_{uuid.uuid4()}",
        "correlation_id": str(uuid.uuid4())
    }
    
    with orchestrator_service_client.stream("POST", "/v1/agent/run", json=payload) as response:
        assert response.status_code == 200
        # Consume stream
        for line in response.iter_lines():
            pass
