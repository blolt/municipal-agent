"""Agent node implementations for LangGraph."""
import os
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from .state import AgentState


# Initialize LLM with Ollama (local or Docker)
ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
llm = ChatOllama(model="llama3.2:3b", temperature=0, base_url=ollama_base_url)

# Module-level cache for bound LLM (with tools)
_llm_with_tools = None

# System prompt guiding the agent through the two-MCP workflow
AGENT_SYSTEM_PROMPT = """You are a municipal zoning expert assistant. You help users understand \
zoning codes, land use regulations, dimensional standards, and development requirements.

You have two groups of tools:

## Municode Tools (fetch raw data from the Municode REST API)
- municode_get_state_info, municode_list_municipalities, municode_get_municipality_info
- municode_get_code_structure — get the table of contents for a municipality's code
- municode_get_code_section — get the full text of a specific code section
- municode_search_codes — search municipal codes by keyword

## Knowledge Graph Tools (build and query the zoning knowledge graph)
### Ingestion (after fetching from Municode):
- kg_ingest_code_section — store a section in the knowledge graph
- kg_ingest_use_permissions — store use-permission matrix rows
- kg_ingest_dimensional_standards — store dimensional standards
- kg_ingest_definitions — store zoning term definitions
- kg_build_summaries — trigger recursive summarization of ingested code
- kg_rebuild_summary — re-summarize a section with better focus

### Query (answer user questions):
- kg_query_section — get a section's content or summary
- kg_query_permissions — what uses are permitted in a district?
- kg_query_standards — dimensional standards (lot area, setbacks, height)
- kg_query_definition — look up a zoning term
- kg_traverse_hierarchy — walk the document tree
- kg_find_related — find cross-referenced sections
- kg_search_by_topic — recursive search across the code hierarchy

## Workflow Patterns

**When asked about a new municipality:** First check if it's in the knowledge graph \
(try kg_search_by_topic or kg_query_section). If not found, use Municode tools to fetch \
the code structure and sections, then ingest them with kg_ingest_* tools, then build \
summaries with kg_build_summaries. Finally, answer the user's question.

**When asked a question about an ingested municipality:** Use knowledge graph query \
tools directly. Start with kg_search_by_topic for thematic questions, kg_query_permissions \
for use/district questions, or kg_query_standards for dimensional questions. Use \
kg_find_related to follow cross-references.

**When the user's question is unclear:** Use kg_search_by_topic to find relevant \
sections, then present the findings with context from the document hierarchy."""


async def _get_llm_with_tools():
    """Get the LLM with tools bound, fetching schemas on first call.

    Fetches tool schemas from the Execution Service once and caches the
    bound LLM for subsequent requests.

    Returns:
        ChatOllama with tools bound (or plain LLM if tools unavailable)
    """
    global _llm_with_tools

    if _llm_with_tools is not None:
        return _llm_with_tools

    try:
        from orchestrator_service.integrations.execution_client import ExecutionServiceClient
        client = ExecutionServiceClient()
        try:
            mcp_tools = await client.list_tools()
        finally:
            await client.close()

        if mcp_tools:
            # Convert MCP tool schemas to LangChain format
            langchain_tools = _mcp_to_langchain_tools(mcp_tools)
            _llm_with_tools = llm.bind_tools(langchain_tools)
        else:
            _llm_with_tools = llm

    except Exception:
        # If Execution Service is unavailable, fall back to plain LLM
        _llm_with_tools = llm

    return _llm_with_tools


def _mcp_to_langchain_tools(mcp_tools: list[dict]) -> list[dict]:
    """Convert MCP tool schemas to LangChain tool format.

    LangChain's bind_tools() accepts dicts with 'name', 'description',
    and 'parameters' (JSON Schema). MCP tools use 'inputSchema' instead.

    Args:
        mcp_tools: List of MCP tool definitions

    Returns:
        List of tool dicts in LangChain format
    """
    langchain_tools = []
    for tool in mcp_tools:
        langchain_tools.append({
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get("inputSchema", {"type": "object", "properties": {}}),
        })
    return langchain_tools


async def reasoning_node(state: AgentState) -> AgentState:
    """LLM reasoning node - decides next action.

    The LLM analyzes the conversation and decides whether to:
    - Call a tool to gather more information
    - Respond directly to the user

    Injects a system prompt on the first turn to guide the agent
    through Municode fetch → Knowledge Graph ingest → query workflows.
    """
    bound_llm = await _get_llm_with_tools()

    # Ensure system prompt is present at the start of the conversation
    messages = state["messages"]
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=AGENT_SYSTEM_PROMPT)] + list(messages)

    response = await bound_llm.ainvoke(messages)

    # Check if LLM wants to call a tool
    if hasattr(response, "tool_calls") and response.tool_calls:
        state["next_action"] = "call_tool"
    else:
        state["next_action"] = "respond"

    # Add LLM response to messages
    state["messages"].append(response)
    return state


async def tool_call_node(state: AgentState) -> AgentState:
    """Tool execution node - runs requested tools via Execution Service.

    Calls the Execution Service to execute tools discovered via MCP.
    """
    from orchestrator_service.integrations.execution_client import ExecutionServiceClient

    last_message = state["messages"][-1]

    # Execute tools via Execution Service
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        execution_client = ExecutionServiceClient()

        try:
            for tool_call in last_message.tool_calls:
                tool_name = tool_call.get("name", "")
                tool_args = tool_call.get("args", {})

                try:
                    # Call Execution Service
                    result = await execution_client.execute_tool(
                        tool_name=tool_name,
                        arguments=tool_args
                    )

                    # Format result for LLM
                    if result.get("status") == "success":
                        content = str(result.get("output", ""))
                    else:
                        content = f"Error: {result.get('error', 'Unknown error')}"

                except Exception as e:
                    content = f"Tool execution failed: {str(e)}"

                # Add tool result to messages
                state["messages"].append(
                    ToolMessage(
                        content=content,
                        tool_call_id=tool_call.get("id", "")
                    )
                )
        finally:
            await execution_client.close()

    return state


async def response_node(state: AgentState) -> AgentState:
    """Final response node - prepares response for user.

    The final AI message is already in state from reasoning_node,
    so this node just marks completion.
    """
    # Response is already in messages from reasoning_node
    return state
