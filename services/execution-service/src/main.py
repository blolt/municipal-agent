"""Main FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router, set_connection_manager
from src.core.config import settings
from src.core.logging import get_logger, setup_logging
from src.mcp.connection_manager import ConnectionManager

# Setup logging
setup_logging(
    service_name=settings.service_name,
    service_version=settings.service_version,
    log_level=settings.log_level,
    log_format=settings.log_format,
)
logger = get_logger(__name__)

# Global connection manager
connection_manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Execution Service...")
    try:
        await connection_manager.initialize()
        set_connection_manager(connection_manager)
        logger.info("Execution Service started successfully")
    except Exception as e:
        logger.error(f"Failed to start Execution Service: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Execution Service...")
    try:
        await connection_manager.shutdown()
        logger.info("Execution Service shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Create FastAPI app
app = FastAPI(
    title="Execution Service",
    description="MCP tool execution service for Agentic Bridge",
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

# Include routes
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Execution Service",
        "version": "0.1.0",
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
