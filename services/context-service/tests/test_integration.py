"""Integration test for Context Service."""
import pytest
from httpx import AsyncClient, ASGITransport
from context_service.main import app


@pytest.mark.asyncio
async def test_full_workflow():
    """
    Integration test simulating a mock Orchestrator workflow:
    1. Ingest event
    2. Save checkpoint
    3. Retrieve checkpoint
    4. Query knowledge graph (basic)
    """
    from context_service.db.connection import init_db_pool, close_db_pool
    
    # Initialize DB pool manually since AsyncClient doesn't trigger lifespan
    await init_db_pool()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Step 1: Ingest an event
            event_response = await client.post(
                "/events",
                json={
                    "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
                    "event_type": "webhook.slack",
                    "source": "slack",
                    "payload": {"text": "Hello, agent!"},
                },
            )
            if event_response.status_code != 201:
                print(f"Error response: {event_response.text}")
            assert event_response.status_code == 201

            # Step 2: Save a checkpoint
            checkpoint_response = await client.post(
                "/state/test-thread-123",
                json={
                    "checkpoint_id_str": "chk-1",
                    "checkpoint_ns": "",
                    "state_dump": {"messages": [{"role": "user", "content": "hi"}]},
                },
            )
            assert checkpoint_response.status_code == 201

            # Step 3: Retrieve checkpoint
            get_response = await client.get("/state/test-thread-123")
            assert get_response.status_code == 200
            assert get_response.json()["checkpoint_id_str"] == "chk-1"

            # Step 4: Query knowledge graph
            query_response = await client.post(
                "/query",
                json={
                    "query": "MATCH (n) RETURN n",
                    "strategies": ["graph"],
                },
            )
            assert query_response.status_code == 200
            assert "results" in query_response.json()
    finally:
        await close_db_pool()
