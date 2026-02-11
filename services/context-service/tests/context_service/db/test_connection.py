"""Unit tests for database connection."""
import pytest
from unittest.mock import AsyncMock, patch
from context_service.db.connection import init_db_pool, close_db_pool, get_db_connection

@pytest.mark.asyncio
async def test_init_db_pool():
    """Test initializing the database pool."""
    with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create_pool:
        mock_pool = AsyncMock()
        mock_create_pool.return_value = mock_pool
        
        await init_db_pool()
        
        mock_create_pool.assert_called_once()
        
        # Cleanup
        await close_db_pool()

@pytest.mark.asyncio
async def test_close_db_pool():
    """Test closing the database pool."""
    with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create_pool:
        mock_pool = AsyncMock()
        mock_create_pool.return_value = mock_pool
        
        await init_db_pool()
        await close_db_pool()
        
        mock_pool.close.assert_called_once()

@pytest.mark.asyncio
async def test_get_db_connection_error_if_not_init():
    """Test get_db_connection raises error if pool not initialized."""
    # Ensure pool is closed (it might be open from other tests if not cleaned up, 
    # but since we are running unit tests in isolation or sequence, we should be careful.
    # Ideally we reset the global _pool variable, but it's private.
    # For now, we assume clean state or use close_db_pool first.
    await close_db_pool()
    
    with pytest.raises(RuntimeError, match="Database pool not initialized"):
        async with get_db_connection():
            pass
