"""
DEPRECATED: State management API

This module is deprecated as of the LangGraph integration.
Checkpoint management is now handled by LangGraph's AsyncPostgresSaver
in the Orchestrator Service.

The Context Service now focuses on:
- Event logging (POST /events)
- Run tracking (future)
- Knowledge graph queries (POST /query)

For checkpoint operations, use LangGraph's built-in methods:
- graph.aget_state(config)
- graph.aupdate_state(config, values)
"""
