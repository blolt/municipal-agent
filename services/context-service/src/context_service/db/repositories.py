"""Data access layer with repository pattern."""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import asyncpg

from context_service.db.connection import get_db_connection
from context_service.models.schemas import (
    InternalEvent,
    CheckpointCreate,
    CheckpointResponse,
)


class EventRepository:
    """Repository for event ingestion and retrieval."""

    @staticmethod
    async def create_event(event: InternalEvent) -> Dict[str, Any]:
        """Insert a new event into the database."""
        async with get_db_connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO events (correlation_id, event_type, source, payload)
                VALUES ($1, $2, $3, $4)
                RETURNING event_id, created_at
                """,
                event.correlation_id,
                event.event_type,
                event.source,
                json.dumps(event.payload),
            )
            return {"event_id": row["event_id"], "created_at": row["created_at"]}


class StateRepository:
    """Repository for state management (checkpoints)."""

    @staticmethod
    async def get_latest_checkpoint(thread_id: str) -> Optional[CheckpointResponse]:
        """Get the most recent checkpoint for a thread."""
        async with get_db_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT checkpoint_id, run_id, thread_id, checkpoint_ns,
                       checkpoint_id_str, parent_checkpoint_id_str,
                       state_dump, created_at
                FROM checkpoints
                WHERE thread_id = $1
                ORDER BY created_at DESC
                LIMIT 1
                """,
                thread_id,
            )
            if row is None:
                return None
            # Deserialize state_dump if needed (though asyncpg usually handles JSONB as str/dict depending on codec, 
            # but we are storing as JSONB. If we inserted as string, it comes back as string or dict?
            # asyncpg decodes JSONB to string by default unless a codec is set.
            # Wait, earlier I saw error "expected str, got dict" on INSERT.
            # So on SELECT, it might return string.
            result = dict(row)
            if isinstance(result["state_dump"], str):
                 result["state_dump"] = json.loads(result["state_dump"])
            return CheckpointResponse(**result)

    @staticmethod
    async def save_checkpoint(
        thread_id: str, checkpoint: CheckpointCreate
    ) -> CheckpointResponse:
        """Save a new checkpoint."""
        async with get_db_connection() as conn:
            # Create a run if run_id is not provided
            run_id = checkpoint.run_id
            if run_id is None:
                # For MVP, create a simple run entry
                run_row = await conn.fetchrow(
                    """
                    INSERT INTO runs (correlation_id, status)
                    VALUES (gen_random_uuid(), 'running')
                    RETURNING run_id
                    """
                )
                run_id = run_row["run_id"]

            row = await conn.fetchrow(
                """
                INSERT INTO checkpoints (
                    run_id, thread_id, checkpoint_ns, checkpoint_id_str,
                    parent_checkpoint_id_str, state_dump
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING checkpoint_id, run_id, thread_id, checkpoint_ns,
                          checkpoint_id_str, parent_checkpoint_id_str,
                          state_dump, created_at
                """,
                run_id,
                thread_id,
                checkpoint.checkpoint_ns,
                checkpoint.checkpoint_id_str,
                checkpoint.parent_checkpoint_id_str,
                json.dumps(checkpoint.state_dump),
            )
            # Deserialize state_dump for response
            result = dict(row)
            if isinstance(result["state_dump"], str):
                 result["state_dump"] = json.loads(result["state_dump"])
            return CheckpointResponse(**result)

    @staticmethod
    async def get_checkpoint_history(thread_id: str) -> List[CheckpointResponse]:
        """Get all checkpoints for a thread in reverse chronological order."""
        async with get_db_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT checkpoint_id, run_id, thread_id, checkpoint_ns,
                       checkpoint_id_str, parent_checkpoint_id_str,
                       state_dump, created_at
                FROM checkpoints
                WHERE thread_id = $1
                ORDER BY created_at DESC
                """,
                thread_id,
            )
            return [CheckpointResponse(**dict(row)) for row in rows]


class GraphRepository:
    """Repository for graph queries (Apache AGE)."""

    @staticmethod
    async def query_graph(query: str) -> List[Dict[str, Any]]:
        """Execute a Cypher query on the knowledge graph (MVP: basic implementation)."""
        async with get_db_connection() as conn:
            # For MVP, we'll provide hardcoded example queries
            # In P1, this will be a dynamic query builder
            rows = await conn.fetch(
                """
                SELECT result::text 
                FROM cypher('knowledge_graph', $$
                    MATCH (n) RETURN n LIMIT 10
                $$) as (result agtype);
                """
            )
            return [{"result": row["result"]} for row in rows]
