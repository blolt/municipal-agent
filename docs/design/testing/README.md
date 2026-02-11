# Testing Documentation Structure

The Agentic Bridge testing strategy is organized into the following documents:

## Overview
- **[Testing Strategy](testing_strategy.md)**: Comprehensive overview of the testing philosophy, pyramid, and CI/CD integration

## Testing Standards by Type

### 1. [Unit Testing Standards](unit_testing.md)
Standards for testing individual functions, classes, and modules within a single service. Python 3.12, pytest.

**Status**: ✅ Documented — Tests implemented per-service (`services/*/tests/`)

### 2. [Integration Testing Standards](integration_testing.md)
Standards for testing multi-service interactions, database operations, and HTTP communication between services.

**Status**: ✅ Documented — Tests implemented (`tests/integration/`)

### 3. [Contract Testing Standards](contract_testing.md)
Standards for validating API contracts, MCP tool schemas, and event schemas.

**Status**: ⏳ Not Yet Implemented — Design document only

### 4. [LLM Testing Standards](llm_testing.md)
Standards for testing agent reasoning, tool selection, and response quality.

**Status**: ⏳ Not Yet Implemented — Design document only

### 5. [End-to-End Testing Standards](e2e_testing.md)
Standards for testing full user workflows across all services via the E2ETestHarness.

**Status**: ✅ Documented — Tests implemented (`tests/e2e/`)

### 6. [Performance Testing Standards](performance_testing.md)
Standards for testing latency, throughput, and resource utilization.

**Status**: ⏳ Not Yet Implemented — Design document only

---

**Last Updated**: 2026-02-07
