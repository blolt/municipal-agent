"""Unit tests for query API."""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from context_service.main import app

client = TestClient(app)

@pytest.mark.asyncio
async def test_query_knowledge():
    """Test POST /query endpoint."""
    with patch("context_service.api.query.GraphRepository.query_graph", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = [{"result": "data"}]
        
        response = client.post(
            "/query",
            json={
                "query": "MATCH (n) RETURN n",
                "strategies": ["graph"]
            }
        )
        
        assert response.status_code == 200
        assert response.json()["results"] == [{"result": "data"}]
        mock_query.assert_called_once_with("MATCH (n) RETURN n")

@pytest.mark.asyncio
async def test_query_knowledge_error():
    """Test POST /query error handling."""
    with patch("context_service.api.query.GraphRepository.query_graph", new_callable=AsyncMock) as mock_query:
        mock_query.side_effect = Exception("DB Error")
        
        response = client.post(
            "/query",
            json={
                "query": "MATCH (n) RETURN n",
                "strategies": ["graph"]
            }
        )
        
        assert response.status_code == 500
        assert "DB Error" in response.json()["detail"]
