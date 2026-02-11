"""Smoke tests - minimal E2E tests to verify basic functionality."""
import pytest


@pytest.mark.e2e
@pytest.mark.smoke
def test_all_services_healthy(harness):
    """Verify all services are running and healthy."""
    health = harness.health_check_all()
    
    assert health["orchestrator"], "Orchestrator service is not healthy"
    assert health["context"], "Context service is not healthy"
    assert health["execution"], "Execution service is not healthy"


@pytest.mark.e2e
@pytest.mark.smoke
def test_can_send_simple_message(harness, unique_thread_id):
    """Verify we can send a message and get a response."""
    response = harness.send_message(
        message="Hello, this is a test",
        thread_id=unique_thread_id,
    )
    
    assert response.status is not None
    assert response.text is not None
    assert len(response.text) > 0
    assert response.thread_id == unique_thread_id


@pytest.mark.e2e
@pytest.mark.smoke
def test_can_send_streaming_message(harness, unique_thread_id):
    """Verify we can send a message and get a streaming response."""
    chunks = harness.send_message_stream(
        message="Hello stream",
        thread_id=unique_thread_id,
    )
    
    assert len(chunks) > 0
    # We might expect the response to echo or just be standard
    # Asserting we got chunks is sufficient for smoke test connectivity.
    # We can join them to see if it makes sense roughly
    full_text = "".join(chunks)
    assert len(full_text) > 0


@pytest.mark.e2e
@pytest.mark.smoke
def test_execution_service_has_tools(harness):
    """Verify Execution Service has discovered tools."""
    tools = harness.get_available_tools()
    
    assert len(tools) > 0, "No tools discovered"
    
    # Check for expected filesystem tools
    tool_names = [tool["name"] for tool in tools]
    assert "read_file" in tool_names
    assert "write_file" in tool_names


@pytest.mark.e2e
@pytest.mark.smoke
def test_can_create_and_read_file(harness):
    """Verify we can create and read files in the sandbox."""
    test_content = "This is a smoke test file"
    test_filename = "smoke_test.txt"
    
    # Create file
    created = harness.create_sandbox_file(test_filename, test_content)
    assert created, "Failed to create file in sandbox"
    
    # Read file back
    content = harness.read_sandbox_file(test_filename)
    assert content is not None, "Failed to read file from sandbox"
    assert test_content in content, f"File content mismatch: expected '{test_content}', got '{content}'"
