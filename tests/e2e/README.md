# E2E Tests

End-to-end tests for the Agentic Bridge system.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Start services:
```bash
cd ../..
docker-compose up -d
```

3. Wait for services to be healthy (~30 seconds)

## Running Tests

### Run all E2E tests
```bash
pytest tests/e2e/ -v
```

### Run smoke tests only
```bash
pytest tests/e2e/ -m smoke -v
```

### Run specific test file
```bash
pytest tests/e2e/test_smoke.py -v
```

## Test Structure

- `harness.py` - E2ETestHarness class for test utilities
- `conftest.py` - Pytest fixtures and configuration
- `test_smoke.py` - Smoke tests (basic functionality)
- `test_golden_path.py` - Golden path tests (complete workflows)
- `fixtures/` - Test data and fixtures

## Test Markers

- `@pytest.mark.e2e` - All E2E tests
- `@pytest.mark.smoke` - Smoke tests (fast, basic checks)
- `@pytest.mark.golden_path` - Golden path tests (complete workflows)
- `@pytest.mark.slow` - Slow tests (may take >10 seconds)

## Troubleshooting

### Services not healthy
```bash
docker-compose ps
docker-compose logs
```

### Tests timing out
Increase timeout in harness initialization or wait_for_services call.

### Connection refused
Ensure services are running and ports are not blocked:
```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
```
