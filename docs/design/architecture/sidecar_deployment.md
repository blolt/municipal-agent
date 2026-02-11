# Sidecar Architecture Design Document

**Status:** Reference Design (Not Yet Deployed)
**Date:** 2026-01-23 (Updated: 2026-02-07)
**Author:** Architecture Team
**Decision:** Adopt sidecar pattern for Orchestrator + Execution Service deployment

> **Note:** This document describes a future production deployment optimization. The current architecture runs all 4 services as separate containers via Docker Compose with Docker DNS networking. The sidecar pattern described here would co-locate Orchestrator and Execution Service in the same pod for sub-millisecond tool execution.

---

## 1. Executive Summary

This document outlines the decision to deploy the Orchestrator Service and Execution Service as **sidecar containers** rather than independent microservices. This architecture provides optimal performance, cost efficiency, and operational simplicity while maintaining separation of concerns.

**Key Decision:** Deploy Orchestrator and Execution Service as co-located containers sharing a network namespace and filesystem volumes.

---

## 2. Problem Statement

### Current Architecture Issues

1. **Network Latency:** HTTP calls between Orchestrator → Execution Service add 1-5ms locally, 50-100ms cross-AZ
2. **Filesystem Isolation:** MCP filesystem server cannot access files across container boundaries
3. **Cost:** Cross-AZ data transfer costs $0.01/GB on AWS
4. **Complexity:** Managing 4 separate application services (Orchestrator, Context, Execution, Discord) increases operational overhead

### Requirements

- ✅ Low-latency tool execution (<1ms overhead)
- ✅ Shared filesystem access for MCP tools
- ✅ Separation of concerns (security, maintainability)
- ✅ Cost-effective deployment
- ✅ Production-ready on AWS or GCP

---

## 3. Proposed Architecture

### 3.1 Sidecar Pattern

```
┌─────────────────────────────────────────────────────┐
│                    Pod / Task                        │
│                                                      │
│  ┌──────────────────────┐  ┌────────────────────┐  │
│  │ Orchestrator         │  │ Execution Service  │  │
│  │ (Main Container)     │  │ (Sidecar)          │  │
│  │                      │  │                    │  │
│  │ - LangGraph Agent    │  │ - MCP Client       │  │
│  │ - Checkpoint Mgmt    │  │ - Tool Execution   │  │
│  │                      │  │ - Sandboxing       │  │
│  └──────────┬───────────┘  └─────────┬──────────┘  │
│             │                        │              │
│             └────────────┬───────────┘              │
│                          │                          │
│                  localhost:8002                     │
│                  (no network hop)                   │
│                                                      │
│  ┌──────────────────────────────────────────────┐  │
│  │         Shared Volume: /workspace            │  │
│  │  - Agent can read/write files                │  │
│  │  - MCP tools access same filesystem          │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### 3.2 Services Not in the Sidecar

The sidecar pattern applies only to Orchestrator + Execution Service. The remaining services deploy as separate pods/containers:

- **Context Service** — Separate pod. Communicates with Orchestrator via HTTP (`POST /events`). Depends only on PostgreSQL.
- **Discord Service** — Separate pod. Consumes SSE from Orchestrator (`POST /v1/agent/run`). No shared volume needed.
- **PostgreSQL** — Managed database or separate container.
- **Ollama** — Separate container or replaced by cloud LLM (Vertex AI) in production.

### 3.3 Communication Flow

1. **Agent decides to use a tool** (e.g., "read file X")
2. **Orchestrator calls Execution Service** via `http://localhost:8002/execute`
3. **Execution Service invokes MCP tool** (filesystem server)
4. **MCP tool accesses shared volume** at `/workspace/X`
5. **Result returned** to Orchestrator (same memory space, no serialization)

---

## 4. Cloud Platform Analysis

### 4.1 AWS Deployment Options

#### Option A: Amazon ECS (Fargate)

**Architecture:**
```yaml
Task Definition:
  Containers:
    - Name: orchestrator
      Image: orchestrator:latest
      PortMappings: [8000:8000]
      
    - Name: execution-sidecar
      Image: execution:latest
      PortMappings: [8002:8002]
      
  Volumes:
    - Name: workspace
      EFSVolumeConfiguration:
        FileSystemId: fs-12345678
        TransitEncryption: ENABLED
```

**Pros:**
- ✅ Serverless (no EC2 management)
- ✅ Auto-scaling built-in
- ✅ Shared volumes via EFS
- ✅ Localhost communication (same task)

**Cons:**
- ❌ EFS adds latency (~1-3ms per file operation)
- ❌ EFS costs $0.30/GB-month
- ❌ Cold start time (10-30s for new tasks)
- ❌ Limited to 4 vCPU, 30GB RAM per task

**Cost Estimate:**
- Fargate: $0.04048/vCPU-hour + $0.004445/GB-hour
- EFS: $0.30/GB-month + $0.03/GB data transfer
- **Total:** ~$50-100/month for 1 task running 24/7

#### Option B: Amazon EKS (Kubernetes)

**Architecture:**
```yaml
apiVersion: v1
kind: Pod
spec:
  containers:
    - name: orchestrator
      image: orchestrator:latest
      
    - name: execution-sidecar
      image: execution:latest
      
  volumes:
    - name: workspace
      emptyDir: {}  # In-memory, fast
      # OR
      persistentVolumeClaim:
        claimName: efs-workspace
```

**Pros:**
- ✅ Full Kubernetes features (scaling, monitoring)
- ✅ `emptyDir` volumes (in-memory, no latency)
- ✅ Can use EFS or EBS for persistence
- ✅ More control over resources

**Cons:**
- ❌ Must manage Kubernetes cluster
- ❌ More complex than ECS
- ❌ EKS costs $0.10/hour (~$73/month) + EC2

**Cost Estimate:**
- EKS: $73/month (control plane)
- EC2: $30-100/month (t3.medium nodes)
- **Total:** ~$103-173/month

#### Option C: EC2 with Docker Compose

**Architecture:**
```yaml
# docker-compose.yml (current setup)
services:
  orchestrator:
    volumes:
      - workspace:/workspace
      
  execution:
    volumes:
      - workspace:/workspace
      
volumes:
  workspace:
```

**Pros:**
- ✅ Simplest deployment
- ✅ No EFS needed (local volumes)
- ✅ Lowest latency
- ✅ Full control

**Cons:**
- ❌ Manual scaling
- ❌ No auto-recovery
- ❌ Must manage EC2 instances

**Cost Estimate:**
- EC2: $30/month (t3.medium)
- **Total:** ~$30/month

---

### 4.2 GCP Deployment Options

#### Option A: Cloud Run (Serverless)

**Limitations:**
- ❌ **No sidecar support** (single container per service)
- ❌ No shared volumes between services
- ❌ Not suitable for this architecture

**Verdict:** ❌ Not recommended

#### Option B: GKE (Google Kubernetes Engine)

**Architecture:**
```yaml
apiVersion: v1
kind: Pod
spec:
  containers:
    - name: orchestrator
      image: orchestrator:latest
      
    - name: execution-sidecar
      image: execution:latest
      
  volumes:
    - name: workspace
      emptyDir: {}  # In-memory
      # OR
      persistentVolumeClaim:
        claimName: filestore-workspace
```

**Pros:**
- ✅ Full Kubernetes features
- ✅ `emptyDir` volumes (fast)
- ✅ Can use Filestore for persistence
- ✅ GKE Autopilot (managed nodes)

**Cons:**
- ❌ GKE costs $0.10/hour (~$73/month)
- ❌ Filestore expensive ($0.20/GB-month)

**Cost Estimate:**
- GKE Autopilot: $73/month
- Compute: $30-80/month
- **Total:** ~$103-153/month

#### Option C: Compute Engine with Docker Compose

**Same as AWS EC2 option**

**Cost Estimate:**
- Compute Engine: $25/month (e2-medium)
- **Total:** ~$25/month

---

## 5. Comparison Matrix

| Feature | AWS ECS | AWS EKS | AWS EC2 | GCP Cloud Run | GCP GKE | GCP Compute |
|---------|---------|---------|---------|---------------|---------|-------------|
| **Sidecar Support** | ✅ Yes | ✅ Yes | ✅ Yes | ❌ No | ✅ Yes | ✅ Yes |
| **Shared Volumes** | ✅ EFS | ✅ EFS/emptyDir | ✅ Local | ❌ No | ✅ Filestore/emptyDir | ✅ Local |
| **Auto-Scaling** | ✅ Built-in | ✅ HPA | ❌ Manual | ✅ Built-in | ✅ HPA | ❌ Manual |
| **Serverless** | ✅ Yes | ❌ No | ❌ No | ✅ Yes | ❌ No | ❌ No |
| **Latency** | Medium (EFS) | Low (emptyDir) | Lowest | N/A | Low (emptyDir) | Lowest |
| **Cost (monthly)** | $50-100 | $103-173 | $30 | N/A | $103-153 | $25 |
| **Complexity** | Low | High | Lowest | N/A | High | Lowest |
| **Recommendation** | ✅ MVP | ⚠️ Scale | ✅ Dev | ❌ No | ⚠️ Scale | ✅ Dev |

---

## 6. Recommended Deployment Strategy

### Phase 1: MVP (Current)
**Platform:** Docker Compose on single VM (AWS EC2 or GCP Compute Engine)

**Why:**
- Simplest deployment
- Lowest cost ($25-30/month)
- Fastest iteration
- No vendor lock-in

**Configuration:**
```yaml
services:
  orchestrator:
    volumes:
      - workspace:/workspace
    environment:
      EXECUTION_SERVICE_URL: http://localhost:8002
      
  execution:
    volumes:
      - workspace:/workspace
      
volumes:
  workspace:  # Local volume, no network latency
```

### Phase 2: Production (Scale)
**Platform:** AWS ECS Fargate or GCP GKE Autopilot

**Why:**
- Auto-scaling
- High availability
- Managed infrastructure
- Production-grade monitoring

**Migration Path:**
1. Containerize with existing Dockerfiles ✅ (already done)
2. Test on ECS/GKE staging environment
3. Set up CI/CD pipeline
4. Gradual traffic migration

---

## 7. Shared Volume Strategy

### 7.1 Volume Types

| Volume Type | Latency | Persistence | Use Case |
|-------------|---------|-------------|----------|
| **emptyDir** (K8s) | <0.1ms | ❌ Pod lifetime | Temporary workspace |
| **Local Docker Volume** | <0.1ms | ✅ Host lifetime | Development |
| **EFS** (AWS) | 1-3ms | ✅ Permanent | Shared state |
| **Filestore** (GCP) | 1-3ms | ✅ Permanent | Shared state |

### 7.2 Recommendation

**For MVP:**
- Use **local Docker volumes** (fastest, simplest)
- Data lost on container restart (acceptable for MVP)

**For Production:**
- Use **emptyDir** for temporary workspace (fast)
- Use **EFS/Filestore** only if persistence needed
- Consider S3/GCS for long-term storage

---

## 8. Security Considerations

### 8.1 Sidecar Isolation

**Pros:**
- ✅ Separate containers = separate process spaces
- ✅ Can set different resource limits
- ✅ Can use different security contexts

**Cons:**
- ⚠️ Shared network namespace (localhost access)
- ⚠️ Shared volume (file access)

### 8.2 Mitigation

1. **Network:** Use authentication tokens for localhost communication
2. **Filesystem:** Use path validation (already implemented)
3. **Resources:** Set CPU/memory limits per container
4. **Secrets:** Use separate secret mounts

---

## 9. Implementation Plan

### 9.1 Immediate Changes (MVP)

1. **Update docker-compose.yml:** ✅ Done
   - Shared `workspace` volume added to both Orchestrator and Execution Service
   - Execution Service sandbox configured to `/workspace`
   - Note: Services currently communicate via Docker DNS (`http://execution-service:8002`), not localhost. The sidecar (localhost) pattern applies to Kubernetes/ECS pod deployments.

2. **Update Orchestrator:** Partially done
   - Currently uses `http://execution-service:8002` (Docker DNS)
   - Sidecar migration would change to `http://localhost:8002`
   - Health check exists for Execution Service

3. **Update Execution Service:** ✅ Done
   - MCP filesystem server configured for `/workspace`
   - Volume mount configured in docker-compose.yml

### 9.2 Future Enhancements

1. **Monitoring:**
   - Add Prometheus metrics
   - Track tool execution latency
   - Monitor volume usage

2. **Scaling:**
   - Migrate to ECS/GKE
   - Implement horizontal pod autoscaling
   - Add load balancing

---

## 10. Alternatives Considered

### Alternative 1: Monolithic (Rejected)
**Why rejected:** Harder to test, deploy, and maintain. Security concerns.

### Alternative 2: Full Microservices (Rejected)
**Why rejected:** Network latency, cost, filesystem isolation issues.

### Alternative 3: Serverless Functions (Rejected)
**Why rejected:** Cold starts, no shared state, expensive for long-running agents.

---

## 11. Decision

**Adopt sidecar pattern with the following configuration:**

- ✅ Deploy Orchestrator + Execution as co-located containers
- ✅ Use shared local volumes for filesystem access
- ✅ Communicate via localhost (no network hop)
- ✅ Start with Docker Compose on single VM
- ✅ Migrate to ECS/GKE for production scale

**Rationale:**
- Optimal performance (sub-millisecond tool execution)
- Cost-effective ($25-30/month for MVP)
- Production-ready migration path
- Maintains separation of concerns

---

## 12. Open Questions

1. **Persistence:** Do we need persistent storage for workspace? (Probably not for MVP)
2. **Multi-tenancy:** How to isolate workspaces for different users? (Future)
3. **Scaling:** When to migrate from single VM to ECS/GKE? (Based on load)

---

## 13. References

- [AWS ECS Task Definitions](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definitions.html)
- [Kubernetes Sidecar Pattern](https://kubernetes.io/docs/concepts/workloads/pods/#how-pods-manage-multiple-containers)
- [MCP Filesystem Server](https://github.com/modelcontextprotocol/servers)

---

**Next Steps:**
1. Review and approve this design
2. Implement shared volume configuration
3. Test end-to-end with shared filesystem
4. Document deployment procedures
