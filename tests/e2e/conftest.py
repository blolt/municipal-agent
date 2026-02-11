"""Pytest configuration and fixtures for E2E tests."""
import pytest
from .harness import E2ETestHarness


@pytest.fixture(scope="session")
def harness():
    """Provide a test harness for the entire test session.
    
    This harness connects to services running via docker-compose.
    """
    h = E2ETestHarness()
    
    # Wait for services to be ready
    if not h.wait_for_services(timeout=60):
        pytest.fail("Services did not become healthy in time")
    
    yield h
    
    h.close()


@pytest.fixture(scope="function")
def unique_thread_id():
    """Generate a unique thread ID for each test."""
    import time
    return f"test_thread_{int(time.time() * 1000)}"


@pytest.fixture(scope="function")
def clean_sandbox(harness):
    """Ensure sandbox is clean before each test.
    
    Note: This is a placeholder. In a real implementation,
    you might want to clear the sandbox directory.
    """
    yield
    # Cleanup after test if needed
