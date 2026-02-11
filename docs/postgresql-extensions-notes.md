# PostgreSQL Extensions: Implementation Notes

## Date: January 21, 2026

## Overview

This document captures the challenges encountered while implementing Apache AGE and pgvector extensions for the Context Service, and outlines the path forward.

## Context

The Context Service design specification called for two PostgreSQL extensions:
- **Apache AGE**: Graph database functionality for knowledge graph queries
- **pgvector**: Vector similarity search for semantic retrieval (RAG)

## Issues Encountered

### 1. Docker Image Availability

**Problem**: The standard `postgres:16` Docker image does not include Apache AGE or pgvector extensions.

**Attempted Solutions**:
- Tried `apache/age:PG16_latest` - Image tag not found
- Tried `apache/age:PG16` - Image tag not found
- Verified `apache/age` exists on Docker Hub but with unclear/inconsistent tags

**Result**: Fell back to standard `postgres:16` image without extensions.

### 2. Extension Installation Complexity

**Problem**: Installing PostgreSQL extensions in a Docker container requires:
1. Compiling the extension from source (requires build tools)
2. Installing to the correct PostgreSQL extension directory
3. Ensuring compatibility with PostgreSQL version
4. Potential C library dependencies

**Implications**:
- Significantly increases Docker image build time
- Adds maintenance burden for version compatibility
- Increases image size
- May require custom Dockerfile

### 3. Migration Failures

**Observed Errors**:
```
ERROR: extension "age" is not available
DETAIL: Could not open extension control file "/usr/share/postgresql/16/extension/age.control"

ERROR: extension "vector" is not available  
DETAIL: Could not open extension control file "/usr/share/postgresql/16/extension/vector.control"
```

**Impact**: 
- Graph query functionality unavailable
- Vector search functionality unavailable
- Core functionality (events, state management) **unaffected**

## Current Status

✅ **Working**:
- Event ingestion (`POST /events`)
- State management (`GET/POST /state/{thread_id}`)
- Database schema (events, runs, checkpoints tables)
- FastAPI application with environment-based configuration
- **Custom Docker Image** - Built from `pgvector/pgvector:pg16` + Apache AGE
- **Apache AGE Extension** - Successfully enabled and `knowledge_graph` created
- **pgvector Extension** - Successfully enabled (v0.8.1)

⚠️ **In Progress**:
- Graph queries (`POST /query`) - Extension ready, endpoint logic needs testing
- Vector similarity search - Extension ready, endpoint logic needs testing

## MVP Decision

**For the MVP ("Steel Thread"), we are proceeding WITHOUT the graph extensions.**

**Rationale**:
1. Core state management functionality works perfectly without them
2. Graph queries were marked as "basic/hardcoded" for MVP anyway
3. Extensions add significant infrastructure complexity
4. Can be added in P1 when needed

## Next Steps

### Immediate (MVP - P0)

- [x] Document this issue
- [ ] Update README to mark AGE/pgvector migrations as optional
- [ ] Update repository pattern to gracefully handle missing extensions
- [ ] Test core functionality (events + state) without extensions
- [ ] Deploy MVP with just relational tables

### Short-term (P1)

**Option 1: Pre-built Docker Image**
- Research and identify stable Apache AGE Docker image
- Test compatibility with PostgreSQL 16
- Update docker-compose.yml
- Alternatively: Build custom Dockerfile with extensions

**Option 2: Managed Database Service**
- Consider AWS RDS with pg_vector support
- Evaluate managed graph databases (Neptune, Neo4j)
- Trade-off: Cost vs. operational simplicity

**Option 3: Alternative Graph Solution**
- Store graph relationships as JSON in relational tables (interim)
- Use application-level graph traversal
- Evaluate alternatives to Apache AGE (e.g., pure Cypher libraries)

### Long-term (P2+)

**If sticking with Apache AGE**:
1. Create custom Dockerfile:
   ```dockerfile
   FROM postgres:16
   RUN apt-get update && apt-get install -y build-essential postgresql-server-dev-16 git
   RUN git clone https://github.com/apache/age.git
   RUN cd age && make install
   ```
2. Document build process
3. Set up CI/CD for image builds
4. Version pin for stability

**If moving to managed services**:
- Migrate to AWS RDS with pgvector
- Use Amazon Neptune for graph queries
- Update connection configuration for production

## Recommendations

1. **For MVP**: Continue without extensions - core functionality is sufficient
2. **For P1**: Invest time in either:
   - Finding/building proper Docker image with extensions
   - OR migrating to managed database services
3. **Document**: Keep this file updated as we make progress

## Resources

- [Apache AGE GitHub](https://github.com/apache/age)
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [Apache AGE Docker Hub](https://hub.docker.com/r/apache/age)
- [PostgreSQL Extension Installation Guide](https://www.postgresql.org/docs/16/extend-extensions.html)

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-21 | Use `postgres:16` without extensions for MVP | AGE Docker images unavailable/unclear, extensions not critical for steel thread |
| TBD | P1 extension strategy | To be determined based on actual graph query requirements |

---

**Maintainer**: Document updated as issues are resolved or new information is discovered.
