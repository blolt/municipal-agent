"""FastAPI application entry point for Orchestrator Service.

Runs the FastAPI server for the HTTP API, including synchronous
(/process) and streaming (/v1/agent/run) agent endpoints.
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import json
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from orchestrator_service.agent.graph import create_agent_graph
from orchestrator_service.config import settings
from orchestrator_service.core.logging import get_logger, setup_logging
from orchestrator_service.integrations.context_client import ContextServiceClient
from orchestrator_service.integrations.execution_client import ExecutionServiceClient
from orchestrator_service.models.schemas import (
    ProcessEventRequest,
    ProcessEventResponse,
    AgentRunRequest,
)
from agentic_common.auth import ServiceAuthDependency, ServiceIdentity


# Setup logging
setup_logging(
    service_name=settings.service_name,
    service_version=settings.service_version,
    log_level=settings.log_level,
    log_format=settings.log_format,
)
logger = get_logger(__name__)

# Auth dependency — accepts tokens from discord-service (and any future callers)
require_service_auth = ServiceAuthDependency(
    secret=settings.service_auth_secret,
    allowed_services=["discord-service"],
)

# Global instances
agent_graph = None
context_client = None
execution_client = None
checkpointer = None

shutdown_event = asyncio.Event()


def _agent_called_discord_tool(result: dict) -> bool:
    """Check if the agent called discord_send_message during execution.

    Scans the message history for any ToolMessage that followed a
    discord_send_message tool call.

    Args:
        result: Agent graph result containing messages list

    Returns:
        True if a discord_send_message tool was called
    """
    from langchain_core.messages import AIMessage
    for msg in result.get("messages", []):
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls"):
            for tc in (msg.tool_calls or []):
                if tc.get("name") == "discord_send_message":
                    return True
    return False








@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle (startup/shutdown)."""
    global agent_graph, context_client, execution_client, checkpointer

    # Startup
    logger.info("Initializing Orchestrator Service...")
    logger.info("Database URL", url=settings.database_url[:30] + "...")

    # Initialize PostgreSQL checkpointer
    async with AsyncPostgresSaver.from_conn_string(settings.database_url) as checkpointer:
        await checkpointer.setup()
        logger.info("AsyncPostgresSaver initialized")

        # Create agent graph
        agent_graph = await create_agent_graph(checkpointer)
        logger.info("Agent graph compiled")

        # Initialize Context Service client
        context_client = ContextServiceClient()
        logger.info("Context Service client ready")

        # Initialize Execution Service client
        execution_client = ExecutionServiceClient()
        logger.info("Execution Service client ready", url=settings.execution_service_url)

        # Start queue consumer if enabled


        yield

        # Shutdown
        logger.info("Shutting down...")



        if context_client:
            await context_client.close()
        if execution_client:
            await execution_client.close()

        logger.info("Orchestrator Service shutdown complete")


app = FastAPI(
    title="Orchestrator Service",
    description="LangGraph-based agent orchestration for Agentic Bridge",
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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "orchestrator-service",
        "graph_ready": agent_graph is not None,

    }


@app.post("/process", response_model=ProcessEventResponse)
async def process_event(
    request: ProcessEventRequest,
    caller: ServiceIdentity = Depends(require_service_auth),
) -> ProcessEventResponse:
    """Process an event through the agent graph (HTTP API).

    This endpoint:
    1. Logs the event to Context Service
    2. Invokes the LangGraph agent with checkpointing
    3. Returns the agent's response

    Note: Discord Service connects via SSE at /v1/agent/run.
    This endpoint is for direct synchronous API access.
    """
    if agent_graph is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent graph not initialized",
        )

    try:
        # Log event to Context Service
        await context_client.log_event(
            correlation_id=request.correlation_id,
            event_type="agent.process_start",
            payload={"thread_id": request.thread_id, "message": request.message},
        )

        # Invoke agent graph with checkpointing
        result = await agent_graph.ainvoke(
            {
                "messages": [HumanMessage(content=request.message)],
                "thread_id": request.thread_id,
                "correlation_id": str(request.correlation_id),
                "next_action": None,
            },
            config={"configurable": {"thread_id": request.thread_id}},
        )

        # Extract response from final message
        final_message = result["messages"][-1]
        response_text = (
            final_message.content if hasattr(final_message, "content") else str(final_message)
        )

        # Fallback: if source is Discord and agent didn't call discord_send_message,
        # auto-deliver the response via the Discord MCP tool
        source = request.metadata.get("source")
        if source == "discord" and not _agent_called_discord_tool(result):
            channel_id = request.thread_id  # thread_id IS the Discord channel_id
            try:
                await execution_client.execute_tool(
                    tool_name="discord_send_message",
                    arguments={"channel_id": channel_id, "content": response_text},
                )
                logger.info(
                    "Fallback: delivered response via discord MCP",
                    thread_id=request.thread_id,
                )
            except Exception as e:
                logger.error(
                    "Fallback discord delivery failed",
                    error=str(e),
                    thread_id=request.thread_id,
                )

        # Log completion
        await context_client.log_event(
            correlation_id=request.correlation_id,
            event_type="agent.process_complete",
            payload={"thread_id": request.thread_id, "response_length": len(response_text)},
        )

        return ProcessEventResponse(
            thread_id=request.thread_id,
            response=response_text,
            correlation_id=request.correlation_id,
        )

    except Exception as e:
        # Log error
        await context_client.log_event(
            correlation_id=request.correlation_id,
            event_type="agent.process_error",
            payload={"error": str(e)},
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process event: {str(e)}",
        )


@app.post("/v1/agent/run")
async def run_agent(
    request: AgentRunRequest,
    caller: ServiceIdentity = Depends(require_service_auth),
):
    """Run the agent with streaming output.
    
    Returns a Server-Sent Events (SSE) stream of agent events.
    """
    if agent_graph is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent graph not initialized",
        )

    async def event_generator():
        try:
            # Log start
            await context_client.log_event(
                correlation_id=request.correlation_id,
                event_type="agent.run_start",
                payload={"thread_id": request.thread_id, "input": request.input},
            )

            # Stream events from LangGraph
            async for event in agent_graph.astream_events(
                {
                    "messages": [HumanMessage(content=request.input)],
                    "thread_id": request.thread_id,
                    "correlation_id": str(request.correlation_id),
                },
                config={"configurable": {"thread_id": request.thread_id}},
                version="v1",
            ):
                # Format event for SSE
                # We filter and map LangGraph events to our StreamEvent schema
                kind = event["event"]
                
                stream_event = None
                
                if kind == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if content:
                        stream_event = {"type": "thinking", "content": content}
                
                elif kind == "on_tool_start":
                    stream_event = {
                        "type": "tool_start", 
                        "name": event["name"], 
                        "args": event["data"].get("input")
                    }
                
                elif kind == "on_tool_end":
                    stream_event = {
                        "type": "tool_result",
                        "name": event["name"],
                        "result": str(event["data"].get("output")),
                        "success": True # Simplified for now
                    }
                
                if stream_event:
                    yield f"data: {json.dumps(stream_event)}\n\n"

            # Done event
            yield f"data: {json.dumps({'type': 'done', 'usage': {'tokens': 0}})}\n\n"

        except Exception as e:
            logger.error("Error in agent stream", error=str(e), exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e), 'code': 'INTERNAL_ERROR'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "orchestrator-service",
        "version": "0.1.0",
        "docs": "/docs",

    }

