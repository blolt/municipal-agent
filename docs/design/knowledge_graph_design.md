# Knowledge Graph Design — Municipal Zoning with Recursive LLM Retrieval

> **Status**: Implemented (2026-02-10)

## Overview

The Knowledge Graph system stores municipal zoning code in Apache AGE (property graph) and builds a recursive summary tree (RAPTOR-like) at each level of the document hierarchy. Instead of pgvector semantic search, the system uses recursive LLM-scored descent — summaries at progressively higher levels of abstraction — so the agent can answer both granular and thematic questions by traversing the summary tree.

## Architecture

Two MCP servers work together:

| Server | Responsibility |
|--------|---------------|
| **Municode MCP** (existing) | Fetch raw data from Municode REST API |
| **Knowledge Graph MCP** (new) | Build graph, generate summaries, query/traverse |

The LangGraph agent orchestrates: fetch via Municode → ingest via KG → query via KG.

```
Municode REST API → [Municode MCP] → raw data
                                         ↓
                                    [KG MCP] → Context Service → Apache AGE
                                         ↓
                                    [KG MCP] ← query results ← Apache AGE
```

## Apache AGE Schema

**Graph name**: `municipal_knowledge`

### Vertex Labels

| Label | Key Properties |
|-------|---------------|
| `Municipality` | `name`, `state`, `fetched_at` |
| `CodeSection` | `section_id`, `title`, `level`, `raw_content`, `summary`, `summary_level`, `summary_built_at` |
| `ZoningDistrict` | `code`, `name`, `category` |
| `LandUse` | `name`, `category` |
| `DimensionalStandard` | `standard_type`, `value`, `unit`, `section_ref` |
| `Definition` | `term`, `definition_text`, `section_ref` |
| `ExternalLaw` | `law_id`, `law_type` |

### Edge Labels

| Label | From → To | Properties |
|-------|----------|-----------|
| `HAS_CHILD` | CodeSection → CodeSection | `order` |
| `BELONGS_TO` | CodeSection → Municipality | |
| `PERMITS` | ZoningDistrict → LandUse | `conditions` |
| `CONDITIONALLY_PERMITS` | ZoningDistrict → LandUse | `conditions`, `review_section` |
| `HAS_STANDARD` | ZoningDistrict → DimensionalStandard | |
| `DEFINED_IN` | Definition → CodeSection | |
| `REFERENCES` | CodeSection → CodeSection | `relationship_type`, `context`, `raw_citation` |
| `CITES_EXTERNAL` | CodeSection → ExternalLaw | `raw_citation` |
| `IN_DISTRICT` | Municipality → ZoningDistrict | |

All queries are scoped by `(m:Municipality {name, state})` for multi-city support.

## Recursive Summary Tree

Each `CodeSection` carries `raw_content`, `summary`, `summary_level`, and `summary_built_at`.

### Build process (bottom-up)

1. **Leaf sections**: Summarize `raw_content` → 1-2 sentences
2. **Divisions**: Concatenate child summaries → LLM synthesizes division summary (2-3 sentences)
3. **Articles**: Concatenate division summaries → LLM synthesizes article summary (3-4 sentences)

### Recursive Search (`kg_search_by_topic`)

1. Compare query against article-level summaries → select top-k
2. Descend into divisions within selected articles → select top-k
3. Descend into sections within selected divisions → return leaf results

The LLM acts as relevance scorer at each level. Returns a reasoning trace showing the path.

## MCP Tools

### Ingestion (6 tools)
- `kg_ingest_code_section` — Store section + auto-detect cross-references
- `kg_ingest_use_permissions` — Store use-permission matrix
- `kg_ingest_dimensional_standards` — Store dimensional standards
- `kg_ingest_definitions` — Store zoning definitions
- `kg_build_summaries` — Trigger bottom-up summarization
- `kg_rebuild_summary` — Re-summarize a section + ancestors

### Query (7 tools)
- `kg_query_section` — Get section content/summary
- `kg_query_permissions` — Use permissions by district/use
- `kg_query_standards` — Dimensional standards by district
- `kg_query_definition` — Term lookup
- `kg_traverse_hierarchy` — Walk the document tree
- `kg_find_related` — Cross-references and citations
- `kg_search_by_topic` — Recursive descent search

## File Locations

| File | Purpose |
|------|---------|
| `services/execution-service/mcp_servers/knowledge_graph_server.py` | KG MCP server |
| `services/context-service/src/context_service/db/kg_repository.py` | AGE Cypher repository |
| `services/context-service/src/context_service/api/knowledge_graph.py` | HTTP API endpoints |
| `services/execution-service/config/mcp_servers.json` | MCP server registration |

## Ontology Mapping

Ported from `strongtowns-detroit` RDF/OWL ontology to AGE property graph:

| RDF (strongtowns-detroit) | AGE (agentic-bridge) |
|---------------------------|---------------------|
| `mzo:Section` (OWL Class) | `CodeSection` vertex |
| `mzo:UsePermission` (reified node) | `PERMITS`/`CONDITIONALLY_PERMITS` edge |
| `mzo:CrossReference` (reified node) | `REFERENCES` edge with `relationship_type` |
| `skos:broader`/`skos:narrower` | `HAS_CHILD` edges |
| 11 `mzo:RelationshipType` individuals | `relationship_type` property values |

Key difference: RDF needs reified nodes for property-bearing relationships. AGE uses property edges natively.

## Citation Extraction

14 regex patterns ported from `strongtowns-detroit/citations.py`:
- Internal: Section, Section range, bare section number, Article, Division
- External: MCL, USC, CFR, Public Act, Chapter

10 relationship classification patterns ported from `rdf_builder.py`:
- defines, constrains, requires, excepts, supersedes, authorizes, delegates, supplements, incorporates, references
