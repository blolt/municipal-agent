"""FastAPI router for knowledge retrieval."""
from fastapi import APIRouter, HTTPException, status

from context_service.db.repositories import GraphRepository
from context_service.models.schemas import KnowledgeQuery, KnowledgeQueryResponse

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=KnowledgeQueryResponse)
async def query_knowledge(query: KnowledgeQuery) -> KnowledgeQueryResponse:
    """
    Query the knowledge graph (MVP implementation).

    For the MVP, this uses hardcoded graph traversal queries.
    P1 will implement dynamic query generation based on the query text.
    """
    try:
        # MVP: Basic graph query
        results = await GraphRepository.query_graph(query.query)
        return KnowledgeQueryResponse(
            results=results,
            metadata={"strategies_used": query.strategies, "query": query.query},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query knowledge graph: {str(e)}",
        )
