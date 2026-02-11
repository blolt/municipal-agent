# GCP Deployment Architecture

**Status:** Reference Only — Not Yet Deployed
**Date:** 2026-01-23 (Updated: 2026-02-07)
**Decision:** Deploy Agentic Bridge on Google Cloud Platform

> **Note:** This document is a reference architecture for future GCP deployment. The system currently runs locally via Docker Compose. See `DOCKER_COMPOSE.md` for the current deployment guide.

---

## Executive Summary

This document outlines the deployment architecture for Agentic Bridge on GCP, with a phased migration from Docker Compose to fully managed services.

**Key Services:**
- **Compute**: GKE Autopilot (Kubernetes with sidecar pattern)
- **Database**: AlloyDB (PostgreSQL + pgvector + AGE)
- **LLM**: Vertex AI (Gemini / Claude) — replaces Ollama
- **Storage**: Cloud Storage
- **Graph** (Future): Neo4j AuraDB

**Current Services to Deploy (4 application + 2 infrastructure):**
| Service | Port | Description |
|---------|------|-------------|
| Orchestrator Service | 8000 | LangGraph agent, SSE streaming |
| Context Service | 8001 | Event logging, knowledge retrieval |
| Execution Service | 8002 | MCP tool execution, sandboxing |
| Discord Service | 8003 | Discord bot integration |
| PostgreSQL 16 | 5433 | AGE + pgvector extensions |
| Ollama (MVP) | 11434 | Local LLM (replaced by Vertex AI in production) |

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Cloud Load Balancer                         │
│                    (HTTPS, SSL termination)                         │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│                         GKE Autopilot                               │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │              Orchestrator Pod (Sidecar Pattern)                │ │
│  │  ┌──────────────────────┐  ┌────────────────────────────────┐ │ │
│  │  │   Orchestrator       │  │   Execution Service            │ │ │
│  │  │   (LangGraph Agent)  │  │   (Sidecar + MCP Tools)        │ │ │
│  │  │   Port 8000          │  │   Port 8002                    │ │ │
│  │  └──────────┬───────────┘  └────────────┬───────────────────┘ │ │
│  │             └───────────┬───────────────┘                     │ │
│  │              Shared Volume: /workspace                        │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌──────────────────────────────┐  ┌───────────────────────────┐   │
│  │     Context Service Pod      │  │   Discord Service Pod     │   │
│  │  Event Logging + Knowledge   │  │   Discord Bot + SSE       │   │
│  │  Port 8001                   │  │   Port 8003               │   │
│  └──────────────────────────────┘  └───────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
         │                                        │
         ▼                                        ▼
┌─────────────────────┐              ┌─────────────────────────┐
│      AlloyDB        │              │      Vertex AI          │
│  (PostgreSQL +      │              │  (Gemini / Claude)      │
│   pgvector + AGE)   │              │                         │
└─────────────────────┘              └─────────────────────────┘
```

---

## 2. Phased Migration Plan

### 2.1 Phase 1: Compute Engine (MVP) 
**Timeline:** Week 1-2  
**Cost:** ~$50-80/month

Deploy current Docker Compose setup on a single GCE instance.

**Components:**
- e2-medium instance (2 vCPU, 4GB RAM)
- 50GB SSD persistent disk
- Docker Compose (as-is)
- Cloud SQL for PostgreSQL (optional)

**Benefits:**
- Minimal changes required
- Fast deployment
- Low cost for development

```yaml
# GCE Instance Spec
machine_type: e2-medium
disk_size: 50GB
image: cos-cloud/cos-stable  # Container-Optimized OS
```

---

### 2.2 Phase 2: GKE Autopilot (Production)
**Timeline:** Week 3-4  
**Cost:** ~$150-250/month

Migrate to GKE with sidecar pattern for auto-scaling and high availability.

**Components:**
- GKE Autopilot cluster
- Orchestrator + Execution as sidecar pods
- Context Service as separate deployment
- Discord Service as separate deployment
- Horizontal Pod Autoscaler (HPA)

**Kubernetes Manifests:**

```yaml
# orchestrator-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orchestrator
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: orchestrator
          image: gcr.io/PROJECT/orchestrator:latest
          ports:
            - containerPort: 8000
          env:
            - name: EXECUTION_SERVICE_URL
              value: "http://localhost:8002"
          volumeMounts:
            - name: workspace
              mountPath: /workspace
              
        - name: execution-sidecar
          image: gcr.io/PROJECT/execution:latest
          ports:
            - containerPort: 8002
          volumeMounts:
            - name: workspace
              mountPath: /workspace
              
      volumes:
        - name: workspace
          emptyDir: {}
```

---

### 2.3 Phase 3: Managed Services (Scale)
**Timeline:** Week 5-8  
**Cost:** ~$300-500/month

Replace self-managed databases with GCP managed services.

**Migration:**

| Current | GCP Managed | Benefits |
|---------|-------------|----------|
| PostgreSQL + pgvector + AGE | AlloyDB | 4x faster, native vectors |
| Ollama (llama3.2:3b) | Vertex AI | No GPU management, better models |
| Docker volumes | Cloud Storage | Persistent, shared |

**AlloyDB Configuration:**

```yaml
# AlloyDB provides:
# - PostgreSQL 15 compatible
# - Native pgvector support
# - Automatic backups
# - 99.99% SLA

instance_type: db-s-1
cpu: 2
memory: 8GB
storage: 100GB
```

---

### 2.4 Phase 4: AI Enhancement (Future)
**Timeline:** Month 2-3

Integrate advanced AI services including managed LLMs and knowledge graphs.

#### 2.4.1 Vertex AI Services

| Feature | Service | Use Case |
|---------|---------|----------|
| Managed LLM | Vertex AI Gemini | Replace Ollama |
| Vector Search | Vertex AI Matching | Semantic search |
| Embeddings | text-embedding-004 | Document embedding |
| RAG | Vertex AI Search | Knowledge retrieval |
| Fine-tuning | Vertex AI Tuning | Custom models |

#### 2.4.2 Neo4j Knowledge Graph

**Purpose:** Migrate from PostgreSQL AGE to Neo4j for advanced graph capabilities:
- Graph algorithms (PageRank, community detection, centrality)
- Complex pattern matching with full Cypher
- Graph data science and ML
- Visual graph exploration

**Neo4j Replaces Only AGE** (keeps relational + vectors in AlloyDB):

```
┌──────────────────────────────────────────────────────┐
│                  Current: AlloyDB                     │
│  ┌────────────┐  ┌────────────┐  ┌────────────────┐  │
│  │ Relational │  │  pgvector  │  │      AGE       │  │
│  │  (keep)    │  │   (keep)   │  │  (→ Neo4j)     │  │
│  └────────────┘  └────────────┘  └────────────────┘  │
└──────────────────────────────────────────────────────┘
                                            │
                                            ▼
                              ┌─────────────────────────┐
                              │      Neo4j AuraDB       │
                              │  (Graph queries only)   │
                              └─────────────────────────┘
```

**Neo4j Deployment Options:**

| Option | Free Tier | Setup | Best For |
|--------|-----------|-------|----------|
| **AuraDB Free** | ✅ 1GB RAM, forever | 5 min | Development |
| **AuraDB Professional** | ❌ ~$65+/mo | 5 min | Production |
| **Self-hosted on GKE** | ❌ (compute costs) | 2+ hrs | Full control |

**AuraDB Free Tier Details:**
- RAM: 1GB | Storage: 0.5GB | Nodes: ~50,000
- Duration: Forever (no time limit)
- VPC Peering: ❌ (public endpoint only)

**Migration Path:**
1. **Phase 4a:** Parallel operation (keep AGE, add Neo4j for new features)
2. **Phase 4b:** Migrate graph-heavy queries to Neo4j
3. **Phase 4c:** Full migration (optional, remove AGE)

**When to Trigger:**
- [ ] Graph has >1M edges
- [ ] Need graph algorithms (PageRank, shortest path)
- [ ] Need graph data science features
- [ ] AGE performance becomes bottleneck

---

## 3. Service Selection

### 3.1 Compute: GKE Autopilot

**Why Autopilot:**
- No node management
- Pay per pod (not per node)
- Automatic scaling
- Built-in security

**Configuration:**
```yaml
cluster_name: agentic-bridge
region: us-central1
release_channel: REGULAR
autopilot: true
```

---

### 3.2 Database: AlloyDB

**Why AlloyDB over Cloud SQL:**
- 4x faster than standard PostgreSQL
- Native pgvector support with ScaNN indexing
- Compatible with existing schema
- Columnar engine for analytics

**Migration Path:**
1. Export PostgreSQL dump
2. Create AlloyDB instance
3. Import data
4. Update connection strings

---

### 3.3 LLM: Vertex AI

**Options:**

| Model | Latency | Cost | Best For |
|-------|---------|------|----------|
| Gemini 1.5 Flash | ~200ms | $0.075/1M tokens | Fast responses |
| Gemini 1.5 Pro | ~500ms | $1.25/1M tokens | Complex reasoning |
| Claude 3.5 Sonnet | ~300ms | $3/1M tokens | Coding tasks |

**Integration:**
```python
from vertexai.generative_models import GenerativeModel

model = GenerativeModel("gemini-1.5-flash")
response = model.generate_content("Hello!")
```

---

## Free Tiers & Cost Optimization

**Important for development:** GCP offers generous free tiers. For intermittent testing, you can minimize costs significantly.

| Service | Free Tier | Notes |
|---------|-----------|-------|
| **GCE** | 1 e2-micro (Oregon) | 24/7, 30GB disk, 1GB egress |
| **GKE Autopilot** | ❌ None | $0.10/hr cluster fee applies |
| **Cloud SQL** | ❌ None | Use GCE + Docker for free |
| **AlloyDB** | ❌ None | Use Cloud SQL or self-managed |
| **Ollama** | N/A (self-hosted) | Included in GCE instance |
| **Cloud Storage** | 5GB | Standard class |
| **Vertex AI** | $300 credit (90 days) | New accounts only |
| **Cloud Build** | 120 min/day | Free build minutes |
| **Artifact Registry** | 500MB | Container images |
| **Cloud Logging** | 50GB/month | Log ingestion |
| **Cloud Monitoring** | Free | Basic metrics |
| **Neo4j AuraDB** | 1 instance | 1GB RAM, 0.5GB storage, forever free |

### Cost-Saving Strategy for Development

**Option A: Free Tier Stack (~$0/month)**
```
┌─────────────────────────────────────────┐
│  GCE e2-micro (FREE)                    │
│  └─ Docker Compose                      │
│     ├─ PostgreSQL + pgvector + AGE      │
│     ├─ Ollama (llama3.2:3b)            │
│     └─ All 4 services                   │
└─────────────────────────────────────────┘
```

**Option B: Teardown Strategy**
```bash
# Deploy for testing
gcloud compute instances start agentic-bridge

# Tear down after testing (no charges)
gcloud compute instances stop agentic-bridge

# Delete entirely when not needed
gcloud compute instances delete agentic-bridge
```

**Costs when stopped:**
- Compute: $0 (only charged when running)
- Disk: ~$2/month (50GB SSD)
- Static IP: $0 if released

---

## 4. Cost Estimates

> **Important:** These estimates are based on official GCP pricing as of January 2024. Actual costs vary by region, usage patterns, and committed use discounts. Always verify with the [GCP Pricing Calculator](https://cloud.google.com/products/calculator) before deployment.

### 4.1 Pricing Methodology

**Assumptions:**
- Region: `us-central1` (Iowa) - one of the lowest-cost US regions
- Currency: USD
- No committed use discounts (pay-as-you-go)
- 730 hours/month (24/7 operation)
- Minimal egress (internal traffic only)

**Official Pricing Sources:**
| Service | Pricing Page |
|---------|--------------|
| Compute Engine | [cloud.google.com/compute/vm-instance-pricing](https://cloud.google.com/compute/vm-instance-pricing) |
| GKE | [cloud.google.com/kubernetes-engine/pricing](https://cloud.google.com/kubernetes-engine/pricing) |
| Cloud SQL | [cloud.google.com/sql/pricing](https://cloud.google.com/sql/pricing) |
| AlloyDB | [cloud.google.com/alloydb/pricing](https://cloud.google.com/alloydb/pricing) |
| Cloud Storage | [cloud.google.com/storage/pricing](https://cloud.google.com/storage/pricing) |
| Vertex AI | [cloud.google.com/vertex-ai/pricing](https://cloud.google.com/vertex-ai/pricing) |

### 4.2 Phase 1: Development (GCE + Docker Compose)

| Service | Specification | Unit Price | Monthly Cost | Source |
|---------|--------------|------------|--------------|--------|
| GCE e2-medium | 2 vCPU, 4GB RAM | $0.033503/hr | ~$24.46 | [VM Pricing](https://cloud.google.com/compute/vm-instance-pricing#e2_machine_types) |
| Boot Disk | 50GB SSD | $0.17/GB/mo | $8.50 | [Disk Pricing](https://cloud.google.com/compute/disks-image-pricing#disk) |
| Cloud Storage | 10GB Standard | $0.020/GB/mo | $0.20 | [Storage Pricing](https://cloud.google.com/storage/pricing#cloud-storage-pricing) |
| Egress | 1GB/mo | $0.12/GB | $0.12 | [Network Pricing](https://cloud.google.com/vpc/network-pricing) |
| **Total** | | | **~$33/month** | |

**Free Tier Alternative:** Using `e2-micro` in `us-west1`, `us-central1`, or `us-east1` qualifies for [Always Free tier](https://cloud.google.com/free/docs/free-cloud-features#compute) (1 instance, 30GB disk).

### 4.3 Phase 2: Production (GKE Autopilot)

| Service | Specification | Unit Price | Monthly Cost | Source |
|---------|--------------|------------|--------------|--------|
| GKE Autopilot | Cluster fee | $0.10/hr | $73.00 | [GKE Pricing](https://cloud.google.com/kubernetes-engine/pricing#autopilot_mode) |
| Pod Compute | 2 vCPU, 4GB (3 pods) | $0.0445/vCPU-hr + $0.0049/GB-hr | ~$120.00 | [Pod Pricing](https://cloud.google.com/kubernetes-engine/pricing#autopilot_mode) |
| Cloud SQL | db-g1-small (1 vCPU, 1.7GB) | $0.0150/hr + storage | ~$45.00 | [Cloud SQL Pricing](https://cloud.google.com/sql/pricing#instance-pricing) |
| Load Balancer | HTTP(S) | $0.025/hr + data | ~$18.25 | [LB Pricing](https://cloud.google.com/vpc/network-pricing#lb) |
| **Total** | | | **~$256/month** | |

### 4.4 Phase 3: Scale (Managed Services)

| Service | Specification | Unit Price | Monthly Cost | Source |
|---------|--------------|------------|--------------|--------|
| GKE Autopilot | Cluster + 4 pods | See above | ~$193.00 | |
| AlloyDB | 2 vCPU, 16GB | $0.1386/vCPU-hr + $0.0152/GB-hr | ~$379.00 | [AlloyDB Pricing](https://cloud.google.com/alloydb/pricing#alloydb-pricing) |
| Vertex AI | Gemini 1.5 Flash, 1M tokens/day | $0.075/1M input | ~$2.25 | [Vertex Pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing) |
| Neo4j AuraDB | Professional (4GB) | Flat rate | ~$65.00 | [Neo4j Pricing](https://neo4j.com/pricing/) |
| **Total** | | | **~$639/month** | |

> **Note:** AlloyDB has a minimum configuration of 2 vCPU and is significantly more expensive than Cloud SQL. Consider Cloud SQL for PostgreSQL if cost is a primary concern.

### 4.5 Cost Optimization Strategies

| Strategy | Potential Savings | How to Apply |
|----------|-------------------|--------------|
| **Committed Use Discounts** | 20-57% | 1-3 year commitments via [CUDs](https://cloud.google.com/compute/docs/instances/signing-up-committed-use-discounts) |
| **Spot VMs** | 60-91% | For non-critical workloads, batch processing |
| **Free Tier** | 100% | e2-micro + 30GB disk in eligible regions |
| **Tear Down** | ~95% | Stop instances when not in use (disk charges only) |
| **Cloud SQL vs AlloyDB** | ~60% | Use Cloud SQL for PostgreSQL instead of AlloyDB |
| **Ollama vs Vertex AI** | Variable | Keep Ollama if cost > model quality matters |
| **Autopilot vs Standard GKE** | Varies | Standard GKE may be cheaper for predictable loads |

### 4.6 Cost Comparison: Cloud SQL vs AlloyDB

| Feature | Cloud SQL (db-g1-small) | AlloyDB (2 vCPU) | Difference |
|---------|------------------------|------------------|------------|
| Monthly Cost | ~$45 | ~$379 | +742% |
| Performance | 1x | 4x faster | Worth it for scale |
| pgvector | ✅ Supported | ✅ Native + ScaNN | Better indexing |
| Use Case | MVP, low traffic | Production, scale | |

**Recommendation:** Start with Cloud SQL, migrate to AlloyDB when performance justifies cost.

---

## 5. Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      VPC Network                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                  Private Subnet                          ││
│  │  ┌─────────────────────────┐  ┌─────────────────────┐    ││
│  │  │ GKE Pods               │  │  AlloyDB             │    ││
│  │  │ (Private IP)           │  │ (Private)            │    ││
│  │  └─────────────────────────┘  └─────────────────────┘    ││
│  └─────────────────────────────────────────────────────────┘│
│                            │                                 │
│  ┌─────────────────────────▼───────────────────────────────┐│
│  │              Cloud NAT (Egress Only)                     ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
                   ┌─────────────────┐
                   │ Cloud Armor WAF │
                   │  (DDoS, Rules)  │
                   └─────────────────┘
                             │
                             ▼
                   ┌─────────────────┐
                   │  Load Balancer  │
                   │  (HTTPS Only)   │
                   └─────────────────┘
```

**Security Features:**
- Private GKE cluster (no public IPs on nodes)
- VPC Service Controls
- Cloud Armor (WAF/DDoS)
- IAM with least privilege
- Secret Manager for credentials
- Binary Authorization for images

---

## 6. CI/CD Pipeline

```yaml
# .github/workflows/deploy.yaml
name: Deploy to GKE

on:
  push:
    branches: [main]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Auth to GCP
        uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      
      - name: Build and Push
        run: |
          gcloud builds submit --tag gcr.io/$PROJECT/orchestrator
          gcloud builds submit --tag gcr.io/$PROJECT/execution
          
      - name: Deploy to GKE
        run: |
          gcloud container clusters get-credentials agentic-bridge
          kubectl apply -f k8s/
```

---

## 7. Monitoring & Observability

**Stack:**
- **Metrics**: Cloud Monitoring (Prometheus-compatible)
- **Logs**: Cloud Logging (structured JSON)
- **Traces**: Cloud Trace (OpenTelemetry)
- **Alerts**: Cloud Monitoring Alerting

**Key Metrics to Track:**
- Request latency (p50, p95, p99)
- LLM response time
- Tool execution time
- Error rates
- Pod CPU/memory usage

---

## 8. Implementation Checklist

### Phase 1: GCE Deployment
- [ ] Create GCP project
- [ ] Enable required APIs
- [ ] Create VPC network
- [ ] Deploy GCE instance
- [ ] Install Docker Compose
- [ ] Configure firewall rules
- [ ] Set up Cloud SQL (optional)
- [ ] Configure domain/SSL

### Phase 2: GKE Migration
- [ ] Create GKE Autopilot cluster
- [ ] Push images to Container Registry
- [ ] Create Kubernetes manifests
- [ ] Deploy services
- [ ] Configure HPA
- [ ] Set up Ingress/Load Balancer
- [ ] Migrate data

### Phase 3: Managed Services
- [ ] Create AlloyDB instance
- [ ] Migrate PostgreSQL data
- [ ] Update connection strings
- [ ] Configure Vertex AI
- [ ] Remove self-hosted Ollama

---

## 9. Next Steps

1. **Create GCP project** and enable billing
2. **Deploy Phase 1** (GCE with Docker Compose)
3. **Test in production** with real traffic
4. **Iterate** on Phase 2 migration

---

## 10. References

- [GKE Autopilot](https://cloud.google.com/kubernetes-engine/docs/concepts/autopilot-overview)
- [AlloyDB](https://cloud.google.com/alloydb/docs)
- [Vertex AI](https://cloud.google.com/vertex-ai/docs)
- [Cloud Armor](https://cloud.google.com/armor/docs)
- [Neo4j AuraDB](https://neo4j.com/cloud/platform/aura-graph-database/)
- [GCP Free Tier](https://cloud.google.com/free)
