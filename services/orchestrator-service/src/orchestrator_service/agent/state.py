"""Agent state schema for LangGraph."""
from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """State for the customer support agent.
    
    This state flows through the LangGraph nodes and is persisted
    via AsyncPostgresSaver checkpoints.
    """
    
    messages: Annotated[list[BaseMessage], add_messages]
    """Conversation history with automatic message reduction."""
    
    thread_id: str
    """Thread identifier for checkpoint persistence."""
    
    correlation_id: str
    """Links to original event in Context Service."""
    
    next_action: str | None
    """Routing decision: 'respond' | 'call_tool' | 'escalate'."""
