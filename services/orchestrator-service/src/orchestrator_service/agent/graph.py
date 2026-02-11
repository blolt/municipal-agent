"""LangGraph definition for the customer support agent."""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from .state import AgentState
from .nodes import reasoning_node, tool_call_node, response_node


async def create_agent_graph(checkpointer: AsyncPostgresSaver):
    """Create the customer support agent graph.
    
    Graph Flow:
    1. reasoning -> Decides next action (tool or respond)
    2. tool_call -> Executes tools if needed
    3. respond -> Generates final response
    
    Args:
        checkpointer: AsyncPostgresSaver for state persistence
        
    Returns:
        Compiled LangGraph application
    """
    # Create graph
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("reasoning", reasoning_node)
    graph.add_node("tool_call", tool_call_node)
    graph.add_node("respond", response_node)
    
    # Set entry point
    graph.set_entry_point("reasoning")
    
    # Add conditional routing from reasoning
    graph.add_conditional_edges(
        "reasoning",
        lambda state: state["next_action"],
        {
            "call_tool": "tool_call",
            "respond": "respond",
        }
    )
    
    # Tool call loops back to reasoning
    graph.add_edge("tool_call", "reasoning")
    
    # Response ends the graph
    graph.add_edge("respond", END)
    
    # Compile with checkpointer
    return graph.compile(checkpointer=checkpointer)
