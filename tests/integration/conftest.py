import os
import subprocess
import time
from pathlib import Path

import httpx
import pytest

from agentic_common.auth import generate_service_token

# Paths
INTEGRATION_TESTS_DIR = Path(__file__).parent
DOCKER_COMPOSE_FILE = INTEGRATION_TESTS_DIR / "docker-compose.test.yml"

@pytest.fixture(scope="session")
def docker_compose_env():
    """Start the integration test environment using Docker Compose."""
    print(f"Starting Docker Compose environment from {DOCKER_COMPOSE_FILE}...")
    
    # Check if we are running in CI (skip build if desired, or just always build)
    subprocess.run(
        ["docker", "compose", "-f", str(DOCKER_COMPOSE_FILE), "up", "-d", "--build"],
        check=True
    )
    
    # Wait for services to be healthy
    print("Waiting for services to be healthy...")
    # Simple wait loop (could be more robust)
    max_retries = 30
    for i in range(max_retries):
        try:
            # Check context service
            subprocess.run(
                ["curl", "-f", "http://localhost:8001/health"],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            # Check execution service
            subprocess.run(
                ["curl", "-f", "http://localhost:8002/health"],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            # Check orchestrator service
            subprocess.run(
                ["curl", "-f", "http://localhost:8000/health"],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            print("All services are healthy!")
            break
        except subprocess.CalledProcessError:
            if i == max_retries - 1:
                print("Services failed to become healthy.")
                subprocess.run(["docker", "compose", "-f", str(DOCKER_COMPOSE_FILE), "logs"])
                subprocess.run(["docker", "compose", "-f", str(DOCKER_COMPOSE_FILE), "down", "-v"])
                pytest.fail("Services failed to start")
            time.sleep(2)
            print("Waiting...")

    yield

    # Teardown
    print("Tearing down Docker Compose environment...")
    subprocess.run(
        ["docker", "compose", "-f", str(DOCKER_COMPOSE_FILE), "down", "-v"],
        check=True
    )

SERVICE_AUTH_SECRET = os.environ.get("SERVICE_AUTH_SECRET", "dev-secret-change-me")


def _auth_headers(service_name: str) -> dict[str, str]:
    """Generate JWT auth headers for integration test requests."""
    token = generate_service_token(service_name, SERVICE_AUTH_SECRET)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def service_auth_secret():
    """Provide the shared auth secret for tests."""
    return SERVICE_AUTH_SECRET


@pytest.fixture(scope="session")
def context_service_client(docker_compose_env):
    """Client for Context Service (with auth)."""
    return httpx.Client(
        base_url="http://localhost:8001",
        headers=_auth_headers("orchestrator-service"),
        timeout=10.0,
    )

@pytest.fixture(scope="session")
def execution_service_client(docker_compose_env):
    """Client for Execution Service (with auth)."""
    return httpx.Client(
        base_url="http://localhost:8002",
        headers=_auth_headers("orchestrator-service"),
        timeout=10.0,
    )

@pytest.fixture(scope="session")
def orchestrator_service_client(docker_compose_env):
    """Client for Orchestrator Service (with auth)."""
    return httpx.Client(
        base_url="http://localhost:8000",
        headers=_auth_headers("discord-service"),
        timeout=30.0,
    )

@pytest.fixture(scope="function")
def context_client(context_service_client):
    """Function-scoped context client."""
    return context_service_client

@pytest.fixture(scope="function")
def orchestrator_client(orchestrator_service_client):
    """Function-scoped orchestrator client."""
    return orchestrator_service_client
