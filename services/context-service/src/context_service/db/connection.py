"""Database connection management using asyncpg."""
import asyncpg
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from context_service.config import settings

# Global connection pool
_pool: Optional[asyncpg.Pool] = None


async def init_db_pool() -> None:
    """Initialize the database connection pool."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=settings.database_pool_min_size,
            max_size=settings.database_pool_max_size,
            server_settings={
                "search_path": 'ag_catalog, "$user", public',
            },
        )


async def close_db_pool() -> None:
    """Close the database connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """Get a database connection from the pool."""
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db_pool() first.")

    async with _pool.acquire() as connection:
        yield connection
