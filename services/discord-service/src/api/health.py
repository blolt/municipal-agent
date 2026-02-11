"""Health check API for container orchestration."""

from fastapi import FastAPI
from pydantic import BaseModel

from src.core.config import get_settings

app = FastAPI(
    title="Discord Service",
    description="Health check API for Discord Service",
    version="0.1.0",
)


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    service: str
    version: str


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return service health status."""
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        service=settings.service_name,
        version=settings.service_version,
    )


@app.get("/ready", response_model=HealthResponse)
async def readiness_check() -> HealthResponse:
    """Return service readiness status.

    This could be extended to check Discord connection, Redis connection, etc.
    """
    settings = get_settings()
    return HealthResponse(
        status="ready",
        service=settings.service_name,
        version=settings.service_version,
    )
