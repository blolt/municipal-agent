"""FastAPI router for event ingestion."""
from fastapi import APIRouter, HTTPException, status

from context_service.db.repositories import EventRepository
from context_service.models.schemas import InternalEvent, InternalEventResponse

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=InternalEventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(event: InternalEvent) -> InternalEventResponse:
    """
    Ingest a new event into the system.

    This endpoint stores an immutable log of all ingress/egress signals.
    """
    try:
        result = await EventRepository.create_event(event)
        return InternalEventResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create event: {str(e)}",
        )
