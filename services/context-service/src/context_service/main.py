"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agentic_common.auth import ServiceAuthDependency
from context_service.api import events, knowledge_graph, query
from context_service.config import settings
from context_service.core.logging import get_logger, setup_logging
from context_service.db.connection import close_db_pool, init_db_pool
from context_service.db.kg_repository import KnowledgeGraphRepository

# Setup logging
setup_logging(
    service_name=settings.service_name,
    service_version=settings.service_version,
    log_level=settings.log_level,
    log_format=settings.log_format,
)
logger = get_logger(__name__)

# Auth dependency — only orchestrator-service may call Context Service
require_service_auth = ServiceAuthDependency(
    secret=settings.service_auth_secret,
    allowed_services=["orchestrator-service", "execution-service"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle (startup/shutdown)."""
    # Startup
    logger.info("Starting Context Service...")
    await init_db_pool()
    # Initialize the AGE knowledge graph schema (idempotent)
    try:
        await KnowledgeGraphRepository.ensure_graph()
        logger.info("Knowledge graph schema initialized")
    except Exception:
        logger.warning("Could not initialize knowledge graph (AGE may not be available)")
    logger.info("Context Service started successfully")
    yield
    # Shutdown
    logger.info("Shutting down Context Service...")
    await close_db_pool()
    logger.info("Context Service shutdown complete")


app = FastAPI(
    title="Context Service",
    description="State Management and Knowledge Retrieval for Municipal Agent",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration
_allowed_origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
if _allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Register routers (auth required on all routes)
app.include_router(events.router, dependencies=[Depends(require_service_auth)])
app.include_router(query.router, dependencies=[Depends(require_service_auth)])
app.include_router(knowledge_graph.router, dependencies=[Depends(require_service_auth)])
# Note: State management (checkpoints) is now handled by LangGraph's AsyncPostgresSaver
# in the Orchestrator Service. The /state endpoints have been deprecated.


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "context-service"}


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "context-service",
        "version": "0.1.0",
        "docs": "/docs",
    }
