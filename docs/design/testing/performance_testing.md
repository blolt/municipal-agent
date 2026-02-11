# Performance Testing Standards

> **Not Yet Implemented** (2026-02-07): No performance testing framework or benchmarks are in place. This document describes the planned approach for performance testing. See `testing_strategy.md` for the current test implementation status.

## 0. Overview

This document defines standards and best practices for performance testing in the Agentic Bridge system. Performance testing ensures the system meets latency, throughput, and resource utilization requirements under various load conditions. This is critical for maintaining a good user experience and controlling infrastructure costs.

## 0.1 Glossary

- **Latency**: Time from request to response (measured in milliseconds)
- **Throughput**: Number of requests processed per unit time (requests/second)
- **Load Testing**: Testing system behavior under expected load
- **Stress Testing**: Testing system behavior beyond expected load to find breaking points
- **Spike Testing**: Testing system response to sudden traffic increases
- **Soak Testing**: Testing system stability over extended periods
- **Percentile (p50, p95, p99)**: Statistical measure of latency distribution
- **RPS**: Requests per second
- **Concurrent Users**: Number of simultaneous active users
- **Resource Utilization**: CPU, memory, disk, network usage

## 1. Scope and Objectives

### 1.1 What Performance Tests Cover

Performance tests in Agentic Bridge verify:

1. **Latency Requirements**
   - End-to-end response time
   - Service-to-service communication latency
   - Database query performance
   - LLM API call latency
   - Queue message processing time

2. **Throughput Capacity**
   - Maximum requests per second
   - Concurrent user capacity
   - Message queue throughput
   - Database transaction rate

3. **Resource Utilization**
   - CPU usage under load
   - Memory consumption
   - Database connection pool usage
   - Network bandwidth

4. **Scalability**
   - Horizontal scaling behavior
   - Performance degradation under load
   - Resource bottlenecks

### 1.2 What Performance Tests Do NOT Cover

- **Functional correctness**: Use unit/integration tests
- **Business logic**: Use unit tests
- **Security**: Use security testing tools
- **User experience**: Use E2E tests

## 2. Performance Requirements

### 2.1 Latency Targets

| Operation | p50 | p95 | p99 | Max |
|-----------|-----|-----|-----|-----|
| Simple Query (no tools) | < 1s | < 2s | < 3s | < 5s |
| Query with 1 Tool | < 2s | < 4s | < 6s | < 10s |
| Query with Multiple Tools | < 5s | < 10s | < 15s | < 30s |
| Context Service Query | < 100ms | < 200ms | < 500ms | < 1s |
| Execution Service Tool Call | < 500ms | < 1s | < 2s | < 5s |
| Database Query | < 50ms | < 100ms | < 200ms | < 500ms |

### 2.2 Throughput Targets

| Metric | MVP (P0) | Production (P1) |
|--------|----------|-----------------|
| Concurrent Users | 10 | 100 |
| Requests/Second | 5 | 50 |
| Messages/Second (Queue) | 20 | 200 |
| Database Queries/Second | 100 | 1000 |

### 2.3 Resource Utilization Limits

| Resource | Warning Threshold | Critical Threshold |
|----------|------------------|-------------------|
| CPU Usage | 70% | 85% |
| Memory Usage | 75% | 90% |
| Database Connections | 70% of pool | 90% of pool |
| Disk I/O | 70% | 85% |

## 3. Testing Approaches

### 3.1 Load Testing

**Purpose**: Verify system performs acceptably under expected load.

**Tool**: Locust

**Example Test**:
```python
# tests/performance/locustfile.py
from locust import HttpUser, task, between
import random

class AgenticBridgeUser(HttpUser):
    wait_time = between(1, 3)  # Wait 1-3 seconds between requests
    
    def on_start(self):
        """Called when a user starts."""
        self.user_id = f"perf_test_user_{random.randint(1000, 9999)}"
    
    @task(3)  # Weight: 3x more likely than other tasks
    def simple_query(self):
        """Simulate a simple query without tools."""
        self.client.post("/ingress", json={
            "event_id": f"evt_{random.randint(10000, 99999)}",
            "correlation_id": f"thread_{self.user_id}_{random.randint(1, 100)}",
            "event_type": "user.message",
            "timestamp": "2026-01-22T20:00:00Z",
            "payload": {
                "user_id": self.user_id,
                "message": "Hello, how are you?"
            }
        })
    
    @task(2)
    def order_status_query(self):
        """Simulate an order status query (requires tool execution)."""
        order_id = f"ORD-{random.randint(100000, 999999)}"
        self.client.post("/ingress", json={
            "event_id": f"evt_{random.randint(10000, 99999)}",
            "correlation_id": f"thread_{self.user_id}_{random.randint(1, 100)}",
            "event_type": "user.message",
            "timestamp": "2026-01-22T20:00:00Z",
            "payload": {
                "user_id": self.user_id,
                "message": f"What's the status of order {order_id}?"
            }
        })
    
    @task(1)
    def complex_query(self):
        """Simulate a complex query requiring multiple tools."""
        self.client.post("/ingress", json={
            "event_id": f"evt_{random.randint(10000, 99999)}",
            "correlation_id": f"thread_{self.user_id}_{random.randint(1, 100)}",
            "event_type": "user.message",
            "timestamp": "2026-01-22T20:00:00Z",
            "payload": {
                "user_id": self.user_id,
                "message": "Show me all my orders from last month and calculate the total"
            }
        })
```

**Running Load Test**:
```bash
# Start with 10 users, ramp up to 50 users over 2 minutes
locust -f tests/performance/locustfile.py \
  --host http://localhost:8000 \
  --users 50 \
  --spawn-rate 5 \
  --run-time 10m \
  --html performance-report.html
```

### 3.2 Stress Testing

**Purpose**: Find the breaking point of the system.

**Approach**: Gradually increase load until system fails or degrades significantly.

**Example**:
```bash
# Ramp up to 200 users to find breaking point
locust -f tests/performance/locustfile.py \
  --host http://localhost:8000 \
  --users 200 \
  --spawn-rate 10 \
  --run-time 15m \
  --html stress-test-report.html
```

### 3.3 Spike Testing

**Purpose**: Test system response to sudden traffic increases.

**Tool**: k6

**Example Test**:
```javascript
// tests/performance/spike-test.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '1m', target: 10 },   // Ramp up to 10 users
    { duration: '30s', target: 100 }, // Spike to 100 users
    { duration: '1m', target: 100 },  // Stay at 100 users
    { duration: '30s', target: 10 },  // Ramp down to 10 users
    { duration: '1m', target: 10 },   // Stay at 10 users
  ],
  thresholds: {
    http_req_duration: ['p(95)<5000'], // 95% of requests < 5s
    http_req_failed: ['rate<0.1'],     // Error rate < 10%
  },
};

export default function () {
  const payload = JSON.stringify({
    event_id: `evt_${Date.now()}`,
    correlation_id: `thread_${__VU}_${__ITER}`,
    event_type: 'user.message',
    timestamp: new Date().toISOString(),
    payload: {
      user_id: `perf_user_${__VU}`,
      message: 'What is the status of order ORD-123456?',
    },
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
  };

  const res = http.post('http://localhost:8000/ingress', payload, params);
  
  check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 5s': (r) => r.timings.duration < 5000,
  });

  sleep(1);
}
```

**Running Spike Test**:
```bash
k6 run tests/performance/spike-test.js
```

### 3.4 Soak Testing

**Purpose**: Verify system stability over extended periods (detect memory leaks, connection leaks).

**Duration**: 4-24 hours

**Example**:
```bash
# Run at moderate load for 8 hours
locust -f tests/performance/locustfile.py \
  --host http://localhost:8000 \
  --users 20 \
  --spawn-rate 2 \
  --run-time 8h \
  --html soak-test-report.html
```

**Monitoring During Soak Test**:
- Memory usage trend (should be stable, not increasing)
- Database connection count (should be stable)
- Error rate (should remain low)
- Response time (should remain consistent)

## 4. Database Performance Testing

### 4.1 Query Performance Benchmarks

**Tool**: pgbench (PostgreSQL) or custom scripts

**Example Benchmark**:
```python
# tests/performance/db_benchmark.py
import time
import psycopg2
from statistics import mean, median

def benchmark_query(connection, query, iterations=100):
    """Benchmark a database query."""
    cursor = connection.cursor()
    timings = []
    
    for _ in range(iterations):
        start = time.time()
        cursor.execute(query)
        cursor.fetchall()
        end = time.time()
        timings.append((end - start) * 1000)  # Convert to ms
    
    return {
        "mean": mean(timings),
        "median": median(timings),
        "p95": sorted(timings)[int(0.95 * len(timings))],
        "p99": sorted(timings)[int(0.99 * len(timings))],
        "max": max(timings)
    }

# Benchmark critical queries
connection = psycopg2.connect(DATABASE_URL)

queries = {
    "event_lookup": "SELECT * FROM events WHERE event_id = 'evt_123'",
    "vector_search": "SELECT * FROM knowledge ORDER BY embedding <-> '[0.1, 0.2, ...]' LIMIT 10",
    "graph_query": "SELECT * FROM ag_catalog.cypher('graph', $$ MATCH (n) RETURN n LIMIT 10 $$) as (v agtype)",
}

for name, query in queries.items():
    results = benchmark_query(connection, query)
    print(f"{name}: p50={results['median']:.2f}ms, p95={results['p95']:.2f}ms")
```

### 4.2 Index Optimization

**Requirement**: Verify indexes improve query performance.

**Example Test**:
```python
def test_index_improves_performance():
    """Verify that index significantly improves query performance."""
    # Benchmark without index
    connection.execute("DROP INDEX IF EXISTS idx_events_correlation_id")
    without_index = benchmark_query(
        connection,
        "SELECT * FROM events WHERE correlation_id = 'thread_123'"
    )
    
    # Create index
    connection.execute("CREATE INDEX idx_events_correlation_id ON events(correlation_id)")
    
    # Benchmark with index
    with_index = benchmark_query(
        connection,
        "SELECT * FROM events WHERE correlation_id = 'thread_123'"
    )
    
    # Index should improve performance by at least 50%
    improvement = (without_index["median"] - with_index["median"]) / without_index["median"]
    assert improvement > 0.5, f"Index only improved performance by {improvement:.1%}"
```

## 5. LLM Performance Testing

### 5.1 Latency Measurement

**Challenge**: LLM latency is highly variable and depends on external APIs.

**Approach**: Measure and track trends, not absolute values.

**Example**:
```python
import time
from langchain_openai import ChatOpenAI

def benchmark_llm_latency(model_name, prompt, iterations=10):
    """Benchmark LLM API latency."""
    llm = ChatOpenAI(model=model_name, temperature=0)
    timings = []
    
    for _ in range(iterations):
        start = time.time()
        llm.invoke(prompt)
        end = time.time()
        timings.append((end - start) * 1000)
    
    return {
        "mean": mean(timings),
        "median": median(timings),
        "p95": sorted(timings)[int(0.95 * len(timings))],
    }

# Benchmark different models
models = ["gpt-4o-mini", "gpt-4o", "gpt-4"]
prompt = "What is the capital of France?"

for model in models:
    results = benchmark_llm_latency(model, prompt)
    print(f"{model}: p50={results['median']:.0f}ms, p95={results['p95']:.0f}ms")
```

### 5.2 Cost Tracking

**Requirement**: Track LLM API costs during performance tests.

**Example**:
```python
from langchain.callbacks import get_openai_callback

def test_llm_cost_under_load():
    """Measure LLM costs during load test."""
    with get_openai_callback() as cb:
        # Simulate 100 requests
        for _ in range(100):
            agent.process("What's the status of my order?")
        
        print(f"Total Tokens: {cb.total_tokens}")
        print(f"Total Cost: ${cb.total_cost:.2f}")
        
        # Assert cost is within budget
        assert cb.total_cost < 5.00, f"Cost ${cb.total_cost:.2f} exceeds budget"
```

## 6. Monitoring and Observability

### 6.1 Metrics to Collect

**Application Metrics**:
- Request rate (requests/second)
- Response time (p50, p95, p99)
- Error rate (%)
- Active threads/connections

**Infrastructure Metrics**:
- CPU usage (%)
- Memory usage (MB)
- Disk I/O (MB/s)
- Network I/O (MB/s)

**Database Metrics**:
- Query rate (queries/second)
- Query latency (ms)
- Connection pool usage
- Cache hit rate

**LLM Metrics**:
- API call rate
- API latency
- Token usage
- Cost per request

### 6.2 Prometheus + Grafana Setup

**Example Prometheus Config**:
```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'orchestrator'
    static_configs:
      - targets: ['orchestrator:8000']
  
  - job_name: 'context-service'
    static_configs:
      - targets: ['context-service:8001']
  
  - job_name: 'execution-service'
    static_configs:
      - targets: ['execution-service:8002']
  
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']
```

**Example Grafana Dashboard**:
- Panel 1: Request rate over time
- Panel 2: Response time percentiles (p50, p95, p99)
- Panel 3: Error rate
- Panel 4: CPU and memory usage
- Panel 5: Database query latency

## 7. CI/CD Integration

### 7.1 Performance Regression Detection

**Approach**: Run performance tests on every deployment and compare to baseline.

**GitHub Actions Example**:
```yaml
name: Performance Tests

on:
  push:
    branches: [main]
  schedule:
    - cron: '0 4 * * *'  # Nightly at 4 AM

jobs:
  performance-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Start services
        run: docker-compose -f tests/performance/docker-compose.perf.yml up -d
      
      - name: Wait for services
        run: sleep 30
      
      - name: Run load test
        run: |
          pip install locust
          locust -f tests/performance/locustfile.py \
            --host http://localhost:8000 \
            --users 20 \
            --spawn-rate 2 \
            --run-time 5m \
            --headless \
            --html performance-report.html \
            --csv performance-results
      
      - name: Check performance regression
        run: |
          python tests/performance/check_regression.py \
            --current performance-results_stats.csv \
            --baseline tests/performance/baseline.csv \
            --threshold 0.2  # Fail if 20% slower
      
      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: performance-report
          path: performance-report.html
      
      - name: Cleanup
        if: always()
        run: docker-compose -f tests/performance/docker-compose.perf.yml down -v
```

### 7.2 Baseline Management

**Requirement**: Maintain baseline performance metrics for comparison.

**Example Baseline File**:
```csv
# tests/performance/baseline.csv
metric,p50,p95,p99,max
simple_query,800,1500,2000,3000
order_status_query,1500,3000,4500,8000
complex_query,3500,7000,10000,20000
```

**Regression Check Script**:
```python
# tests/performance/check_regression.py
import csv
import sys

def load_metrics(filepath):
    """Load metrics from CSV file."""
    metrics = {}
    with open(filepath) as f:
        reader = csv.DictReader(f)
        for row in reader:
            metrics[row['metric']] = {
                'p50': float(row['p50']),
                'p95': float(row['p95']),
                'p99': float(row['p99']),
            }
    return metrics

def check_regression(current, baseline, threshold=0.2):
    """Check if current metrics regressed compared to baseline."""
    regressions = []
    
    for metric, current_values in current.items():
        if metric not in baseline:
            continue
        
        baseline_values = baseline[metric]
        
        for percentile in ['p50', 'p95', 'p99']:
            current_val = current_values[percentile]
            baseline_val = baseline_values[percentile]
            
            if current_val > baseline_val * (1 + threshold):
                regression_pct = (current_val - baseline_val) / baseline_val
                regressions.append(
                    f"{metric} {percentile}: {regression_pct:.1%} slower "
                    f"({current_val:.0f}ms vs {baseline_val:.0f}ms)"
                )
    
    if regressions:
        print("Performance regressions detected:")
        for r in regressions:
            print(f"  - {r}")
        sys.exit(1)
    else:
        print("No performance regressions detected")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--threshold", type=float, default=0.2)
    args = parser.parse_args()
    
    current = load_metrics(args.current)
    baseline = load_metrics(args.baseline)
    check_regression(current, baseline, args.threshold)
```

## 8. Best Practices

### 8.1 Test in Production-Like Environment

- Use production-equivalent hardware
- Use production-equivalent data volumes
- Use production-equivalent network conditions

### 8.2 Warm Up Before Testing

```python
def warm_up_system(duration_seconds=60):
    """Send warm-up traffic before performance test."""
    print(f"Warming up system for {duration_seconds}s...")
    end_time = time.time() + duration_seconds
    
    while time.time() < end_time:
        # Send light traffic
        send_request()
        time.sleep(0.5)
    
    print("Warm-up complete")
```

### 8.3 Use Realistic Test Data

- Match production data distribution
- Use realistic query patterns
- Include edge cases

### 8.4 Monitor During Tests

- Watch for errors
- Check resource utilization
- Look for bottlenecks

### 8.5 Analyze Results Thoroughly

- Look at percentiles, not just averages
- Identify outliers
- Correlate metrics (e.g., high latency with high CPU)

## 9. Common Performance Issues

### 9.1 Database Connection Pool Exhaustion

**Symptom**: Requests timeout waiting for database connections

**Solution**: Increase connection pool size or optimize query patterns

### 9.2 N+1 Query Problem

**Symptom**: Many small database queries instead of one large query

**Solution**: Use joins or batch queries

### 9.3 Memory Leaks

**Symptom**: Memory usage increases over time

**Solution**: Profile application, fix resource leaks

### 9.4 LLM API Rate Limiting

**Symptom**: Requests fail with 429 errors

**Solution**: Implement rate limiting, request queuing, or use multiple API keys

## 10. Metrics and Reporting

### 10.1 Performance Test Report Template

```markdown
# Performance Test Report

**Date**: 2026-01-22
**Test Type**: Load Test
**Duration**: 10 minutes
**Peak Load**: 50 concurrent users

## Results Summary

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| p50 Latency | < 2s | 1.2s | ✅ Pass |
| p95 Latency | < 4s | 3.8s | ✅ Pass |
| p99 Latency | < 6s | 7.2s | ❌ Fail |
| Error Rate | < 1% | 0.3% | ✅ Pass |
| Throughput | > 5 RPS | 12 RPS | ✅ Pass |

## Observations

- p99 latency exceeded target by 20%
- CPU usage peaked at 65% (within limits)
- No errors observed during test
- Database query performance was good

## Recommendations

1. Investigate p99 latency outliers
2. Consider caching for frequently accessed data
3. Monitor LLM API latency (contributed 60% of total latency)
```

## 11. Evolution

This document will evolve as the system matures:
- Add chaos engineering tests
- Implement continuous performance monitoring
- Add capacity planning guidelines
- Expand to multi-region testing

---

**Document Status**: Initial Draft  
**Last Updated**: 2026-01-22  
**Owner**: Engineering Team
