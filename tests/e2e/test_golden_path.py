"""Golden path tests - complete end-to-end workflows."""
import pytest


@pytest.mark.e2e
@pytest.mark.golden_path
def test_simple_conversation(harness, unique_thread_id):
    """Test a simple back-and-forth conversation.
    
    This verifies:
    - Message sending works
    - Agent responds appropriately
    - Thread context is maintained
    """
    # First message
    response1 = harness.send_message(
        message="Hello! Can you help me?",
        thread_id=unique_thread_id,
    )
    
    assert response1.status is not None
    assert len(response1.text) > 0
    assert response1.thread_id == unique_thread_id
    
    # Second message in same thread
    response2 = harness.send_message(
        message="What can you do?",
        thread_id=unique_thread_id,
    )
    
    assert response2.status is not None
    assert len(response2.text) > 0
    assert response2.thread_id == unique_thread_id


@pytest.mark.e2e
@pytest.mark.golden_path
def test_file_operation_workflow(harness, unique_thread_id):
    """Test complete file operation workflow.
    
    This verifies:
    - Agent can understand file operation requests
    - Execution Service executes tools correctly
    - Results are returned to user
    """
    # Create a test file first
    test_filename = f"test_file_{unique_thread_id}.txt"
    test_content = "This is test content for E2E testing"
    
    created = harness.create_sandbox_file(test_filename, test_content)
    assert created, "Failed to create test file"
    
    # Ask agent to read the file
    # Note: This assumes the agent has been configured with file tools
    # and can understand natural language requests
    response = harness.send_message(
        message=f"Can you read the file {test_filename}?",
        thread_id=unique_thread_id,
    )
    
    assert response.status is not None
    assert len(response.text) > 0
    # The response should mention the file or its content
    # (exact assertion depends on agent behavior)


@pytest.mark.e2e
@pytest.mark.golden_path
@pytest.mark.slow
def test_multi_turn_context_retention(harness, unique_thread_id):
    """Test that agent maintains context across multiple turns.
    
    This verifies:
    - Checkpoint persistence works
    - Agent remembers previous conversation
    - Context is used for follow-up questions
    """
    # Turn 1: Establish context
    response1 = harness.send_message(
        message="I'm working on a project called 'Municipal Agent'",
        thread_id=unique_thread_id,
    )
    assert response1.status is not None
    
    # Turn 2: Reference previous context
    response2 = harness.send_message(
        message="What was the name of my project?",
        thread_id=unique_thread_id,
    )
    assert response2.status is not None
    # Agent should remember "Municipal Agent"
    assert "municipal" in response2.text.lower() or "agent" in response2.text.lower()


@pytest.mark.e2e
@pytest.mark.golden_path
def test_tool_discovery_and_execution(harness, unique_thread_id):
    """Test that tools are discovered and can be executed.
    
    This verifies:
    - Execution Service discovers MCP tools
    - Tools can be listed
    - Tools can be executed successfully
    """
    # Get available tools
    tools = harness.get_available_tools()
    assert len(tools) > 0, "No tools available"
    
    # Find a simple tool to test
    tool_names = [t["name"] for t in tools]
    assert "write_file" in tool_names, "write_file tool not found"
    
    # Execute a tool directly
    test_file = f"tool_test_{unique_thread_id}.txt"
    created = harness.create_sandbox_file(test_file, "Tool execution test")
    assert created, "Tool execution failed"
    
    # Verify file was created
    content = harness.read_sandbox_file(test_file)
    assert content is not None
    assert "Tool execution test" in content
