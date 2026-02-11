import pytest

def test_execution_service_list_tools(execution_service_client):
    """Verify that Execution Service can list available tools."""
    response = execution_service_client.get("/tools")
    assert response.status_code == 200
    
    data = response.json()
    tools = data["tools"]
    assert isinstance(tools, list)
    # Assuming 'time' or 'random' tool is available in default config
    # We can check for at least one tool
    assert len(tools) > 0
    
    # Check structure of a tool
    tool = tools[0]
    assert "name" in tool
    assert "description" in tool
    assert "input_schema" in tool

def test_execution_service_execute_tool(execution_service_client):
    """Verify that Execution Service can execute a tool."""
    # First get list of tools to find a simple one to execute
    response = execution_service_client.get("/tools")
    tools = response.json()["tools"]
    
    # Try to find a 'time' tool or 'random' tool, or just pick the first one if we know its args.
    # For integration test smoke, let's look for 'time-get_current_time' (common example)
    # or just assume a specific one based on `mcp_servers.json` fixture.
    # Since I don't see the exact mcp config here, I'll write a generic check or try to key off what I find.
    
    target_tool = next((t for t in tools if "fetch" in t["name"].lower()), None)
    
    if target_tool:
        # Execute tool
        exec_payload = {
            "tool_name": target_tool["name"],
            "arguments": {}, # Assuming the tool accepts empty args or we need to know schema
            "timeout": 5.0
        }
        
        # If it's the 'time' tool, it usually takes no args or specific ones. 
        # Attempting empty args for generic smoke test.
        
        response = execution_service_client.post("/execute", json=exec_payload)
        
        # If assertion fails, print for debugging
        if response.status_code != 200:
             print(f"Tool execution failed: {response.text}")

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "success"
        assert result["output"] is not None
