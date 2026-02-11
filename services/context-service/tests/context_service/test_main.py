"""Unit tests for main application."""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from context_service.main import app

client = TestClient(app)

def test_health_check():
    """Test GET /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "context-service"}

def test_root():
    """Test GET / endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "context-service"

@pytest.mark.asyncio
async def test_lifespan():
    """Test application lifespan (startup/shutdown)."""
    with patch("context_service.main.init_db_pool", new_callable=AsyncMock) as mock_init, \
         patch("context_service.main.close_db_pool", new_callable=AsyncMock) as mock_close:
        
        # Trigger lifespan
        async with app.router.lifespan_context(app):
            mock_init.assert_called_once()
        
        mock_close.assert_called_once()
