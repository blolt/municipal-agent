#!/usr/bin/env python3
"""Knowledge Graph MCP server — builds and queries a municipal zoning knowledge graph.

Ingestion tools store raw code sections, use permissions, dimensional standards,
and definitions in Apache AGE via the Context Service.  Query tools traverse the
graph, look up permissions/standards/definitions, follow cross-references, and
perform recursive LLM-scored descent search.

Tools (ingestion):
    kg_ingest_code_section         — Store a raw code section
    kg_ingest_use_permissions      — Store use-permission matrix rows
    kg_ingest_dimensional_standards — Store dimensional standards
    kg_ingest_definitions          — Store zoning term definitions
    kg_build_summaries             — Trigger recursive bottom-up summarization
    kg_rebuild_summary             — Re-summarize a section and its ancestors

Tools (query):
    kg_query_section               — Get section content + summary
    kg_query_permissions           — What uses are permitted in a district?
    kg_query_standards             — Dimensional standards for a district
    kg_query_definition            — Look up a zoning term
    kg_traverse_hierarchy          — Walk the document tree
    kg_find_related                — Find cross-referenced sections
    kg_search_by_topic             — Recursive descent search via LLM scoring
"""

from __future__ import annotations

import json
import os
import re
from enum import Enum

import httpx
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONTEXT_SERVICE_URL = os.environ.get("CONTEXT_SERVICE_URL", "http://localhost:8001")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
SERVICE_AUTH_SECRET = os.environ.get("SERVICE_AUTH_SECRET", "")

mcp = FastMCP("knowledge_graph")


# ---------------------------------------------------------------------------
# Context Service HTTP client
# ---------------------------------------------------------------------------

def _auth_headers() -> dict[str, str]:
    """Build auth headers for Context Service calls using JWT."""
    if not SERVICE_AUTH_SECRET:
        return {}
    try:
        from agentic_common.auth import generate_service_token
        token = generate_service_token("execution-service", SERVICE_AUTH_SECRET)
        return {"Authorization": f"Bearer {token}"}
    except Exception:
        # Fallback: pass raw secret (dev-only, auth may be disabled)
        return {"Authorization": f"Bearer {SERVICE_AUTH_SECRET}"}


async def _context_request(
    method: str,
    path: str,
    *,
    json_body: dict | None = None,
    params: dict | None = None,
) -> dict:
    """Make an async request to the Context Service."""
    url = f"{CONTEXT_SERVICE_URL}{path}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.request(
            method, url, json=json_body, params=params, headers=_auth_headers(),
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Context Service error {response.status_code}: {response.text}")
    return response.json()


# ---------------------------------------------------------------------------
# Citation extraction (ported from strongtowns-detroit/citations.py)
# ---------------------------------------------------------------------------

class CitationType(str, Enum):
    SECTION = "section"
    ARTICLE = "article"
    DIVISION = "division"
    MCL = "mcl"
    USC = "usc"
    CFR = "cfr"
    PUBLIC_ACT = "public_act"
    CHAPTER = "chapter"

# Internal references
_SECTION_RE = re.compile(r"(?:Section|Sec\.)\s+(\d{1,3}-\d{1,3}-\d{1,4})", re.IGNORECASE)
_SECTION_RANGE_RE = re.compile(
    r"(?:Sections?)\s+(\d{1,3}-\d{1,3}-\d{1,4})\s+through\s+(\d{1,3}-\d{1,3}-\d{1,4})",
    re.IGNORECASE,
)
_BARE_SECTION_RE = re.compile(r"(?<![.\w])(\d{1,3}-\d{1,3}-\d{1,4})(?!\d)")
_ARTICLE_RE = re.compile(r"Article\s+([IVXLC]+)", re.IGNORECASE)
_DIVISION_RE = re.compile(r"Division\s+(\d+)", re.IGNORECASE)

# External references
_MCL_RE = re.compile(r"MCL\s+(\d+\.\d+[a-z]?(?:\s+et\s+seq\.?)?)", re.IGNORECASE)
_PA_RE = re.compile(r"P\.A\.\s+(\d+(?:\s+of\s+\d{4})?)", re.IGNORECASE)
_USC_RE = re.compile(r"(\d+)\s+USC\s+(\d+)", re.IGNORECASE)
_CFR_RE = re.compile(r"(\d+)\s+CFR\s+(\d+(?:\.\d+)?)", re.IGNORECASE)
_CHAPTER_RE = re.compile(r"Chapter\s+(\d+)", re.IGNORECASE)

# Relationship classification patterns (from rdf_builder.py)
_RELATIONSHIP_PATTERNS = [
    (re.compile(r"as\s+defined\s+in|meaning\s+given\s+in", re.I), "defines"),
    (re.compile(r"notwithstanding.*to\s+the\s+contrary", re.I), "supersedes"),
    (re.compile(r"except\s+as\s+provided\s+in", re.I), "excepts"),
    (re.compile(r"subject\s+to|in\s+accordance\s+with|pursuant\s+to", re.I), "constrains"),
    (re.compile(r"required\s+by|shall\s+comply\s+with|as\s+required", re.I), "requires"),
    (re.compile(r"authorized\s+by|as\s+authorized|permitted\s+under", re.I), "authorizes"),
    (re.compile(r"delegated\s+to|designated\s+by", re.I), "delegates"),
    (re.compile(r"in\s+addition\s+to|supplemented\s+by", re.I), "supplements"),
    (re.compile(r"incorporated\s+by\s+reference|adopted\s+by\s+reference", re.I), "incorporates"),
    (re.compile(r"(?:see|refer\s+to)\s+(?:also\s+)?(?:Section|Sec\.)", re.I), "references"),
]


def _classify_relationship(context: str) -> str:
    """Classify a cross-reference relationship type from surrounding text."""
    for pattern, rel_type in _RELATIONSHIP_PATTERNS:
        if pattern.search(context):
            return rel_type
    return "unknown"


def _extract_citations(text: str, source_section: str = "") -> list[dict]:
    """Extract citations from text, returning dicts with type/target/raw_text."""
    citations: list[dict] = []
    matched_spans: list[tuple[int, int]] = []

    def _overlaps(start: int, end: int) -> bool:
        return any(s <= start < e or s < end <= e for s, e in matched_spans)

    def _add(start: int, end: int, target: str, ctype: str, raw: str, context: str = "") -> None:
        if not _overlaps(start, end):
            matched_spans.append((start, end))
            citations.append({
                "source_section": source_section,
                "target": target,
                "type": ctype,
                "raw_text": raw,
                "context": context,
            })

    # Get surrounding context for relationship classification
    def _get_context(match: re.Match, window: int = 80) -> str:
        start = max(0, match.start() - window)
        end = min(len(text), match.end() + window)
        return text[start:end]

    # 1. Section ranges
    for m in _SECTION_RANGE_RE.finditer(text):
        matched_spans.append((m.start(), m.end()))
        ctx = _get_context(m)
        start_parts = m.group(1).split("-")
        end_parts = m.group(2).split("-")
        if len(start_parts) == 3 and len(end_parts) == 3 and start_parts[:2] == end_parts[:2]:
            try:
                first, last = int(start_parts[2]), int(end_parts[2])
                prefix = f"{start_parts[0]}-{start_parts[1]}"
                for n in range(first, min(last + 1, first + 100)):
                    citations.append({
                        "source_section": source_section,
                        "target": f"{prefix}-{n}",
                        "type": CitationType.SECTION,
                        "raw_text": m.group(0),
                        "context": ctx,
                    })
            except ValueError:
                pass

    # 2. Explicit section references
    for m in _SECTION_RE.finditer(text):
        ctx = _get_context(m)
        _add(m.start(), m.end(), m.group(1), CitationType.SECTION, m.group(0), ctx)

    # 3. Bare section numbers
    for m in _BARE_SECTION_RE.finditer(text):
        ctx = _get_context(m)
        _add(m.start(), m.end(), m.group(1), CitationType.SECTION, m.group(0), ctx)

    # 4. Article references
    for m in _ARTICLE_RE.finditer(text):
        ctx = _get_context(m)
        _add(m.start(), m.end(), f"article:{m.group(1).upper()}", CitationType.ARTICLE, m.group(0), ctx)

    # 5. Division references
    for m in _DIVISION_RE.finditer(text):
        ctx = _get_context(m)
        _add(m.start(), m.end(), f"div:{m.group(1)}", CitationType.DIVISION, m.group(0), ctx)

    # 6. External: MCL
    for m in _MCL_RE.finditer(text):
        _add(m.start(), m.end(), f"mcl:{m.group(1).strip()}", CitationType.MCL, m.group(0))

    # 7. External: Public Acts
    for m in _PA_RE.finditer(text):
        _add(m.start(), m.end(), f"pa:{m.group(1).strip()}", CitationType.PUBLIC_ACT, m.group(0))

    # 8. External: USC
    for m in _USC_RE.finditer(text):
        _add(m.start(), m.end(), f"usc:{m.group(1)}-{m.group(2)}", CitationType.USC, m.group(0))

    # 9. External: CFR
    for m in _CFR_RE.finditer(text):
        _add(m.start(), m.end(), f"cfr:{m.group(1)}-{m.group(2)}", CitationType.CFR, m.group(0))

    # 10. Chapter references
    for m in _CHAPTER_RE.finditer(text):
        _add(m.start(), m.end(), f"chapter:{m.group(1)}", CitationType.CHAPTER, m.group(0))

    return citations


# ---------------------------------------------------------------------------
# LLM helpers (for summarization and search scoring)
# ---------------------------------------------------------------------------

async def _llm_call(prompt: str, system: str = "") -> str:
    """Call Ollama for summarization or relevance scoring."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0},
            },
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Ollama error {response.status_code}: {response.text}")
    return response.json()["message"]["content"]


_SUMMARY_PROMPTS = {
    "section": (
        "Summarize the following zoning code section in 1-2 sentences. "
        "Focus on: what is regulated, who/what it applies to, and key requirements or restrictions.\n\n"
    ),
    "division": (
        "The following are summaries of individual sections within a division of a zoning code. "
        "Synthesize them into a 2-3 sentence summary that captures the division's overall "
        "regulatory scope and key provisions.\n\n"
    ),
    "article": (
        "The following are summaries of divisions within an article of a zoning code. "
        "Synthesize them into a 3-4 sentence summary that captures the article's purpose, "
        "the major topics it covers, and its relationship to the broader zoning framework.\n\n"
    ),
}


async def _summarize(text: str, level: str) -> str:
    """Generate a summary at the specified level."""
    prompt_prefix = _SUMMARY_PROMPTS.get(level, _SUMMARY_PROMPTS["section"])
    return await _llm_call(prompt_prefix + text)


# ---------------------------------------------------------------------------
# MCP Tools — Ingestion
# ---------------------------------------------------------------------------

@mcp.tool()
async def kg_ingest_code_section(
    municipality: str,
    state: str,
    section_id: str,
    title: str,
    content: str,
    level: str = "section",
    parent_id: str = "",
) -> str:
    """Store a raw code section in the knowledge graph and detect cross-references.

    Args:
        municipality: Name of the city (e.g., "Detroit")
        state: Two-letter state abbreviation (e.g., "MI")
        section_id: Unique section identifier (e.g., "50-12-101")
        title: Section title
        content: Full text content of the section
        level: Hierarchy level — "article", "division", or "section"
        parent_id: Parent section ID (empty string if top-level)
    """
    # Store the section
    result = await _context_request("POST", "/kg/ingest/section", json_body={
        "municipality": municipality,
        "state": state,
        "section_id": section_id,
        "title": title,
        "content": content,
        "level": level,
        "parent_id": parent_id if parent_id else None,
    })

    # Extract and store cross-references
    citations = _extract_citations(content, source_section=section_id)
    internal_count = 0
    external_count = 0

    for cit in citations:
        target = cit["target"]
        rel_type = _classify_relationship(cit.get("context", ""))

        if cit["type"] in (CitationType.MCL, CitationType.USC, CitationType.CFR, CitationType.PUBLIC_ACT):
            # External citation
            await _context_request("POST", "/kg/ingest/external-citation", json_body={
                "municipality": municipality,
                "state": state,
                "source_section_id": section_id,
                "law_id": target,
                "law_type": cit["type"],
                "raw_citation": cit["raw_text"],
            })
            external_count += 1
        elif cit["type"] == CitationType.SECTION:
            # Internal cross-reference (only if target looks like a section ID)
            await _context_request("POST", "/kg/ingest/cross-reference", json_body={
                "municipality": municipality,
                "state": state,
                "source_section_id": section_id,
                "target_section_id": target,
                "relationship_type": rel_type,
                "context": cit.get("context", ""),
                "raw_citation": cit["raw_text"],
            })
            internal_count += 1

    return json.dumps({
        "status": "ok",
        "section_id": section_id,
        "cross_references_found": internal_count,
        "external_citations_found": external_count,
    })


@mcp.tool()
async def kg_ingest_use_permissions(
    municipality: str,
    state: str,
    permissions: list[dict],
) -> str:
    """Store use-permission matrix rows in the knowledge graph.

    Args:
        municipality: Name of the city
        state: Two-letter state abbreviation
        permissions: List of permission dicts, each with keys:
            - use: Land use name (e.g., "One-family dwelling")
            - district: Zoning district code (e.g., "R1")
            - level: "permitted", "conditional", or "not_permitted"
            - conditions: Optional conditions text
    """
    result = await _context_request("POST", "/kg/ingest/permissions", json_body={
        "municipality": municipality,
        "state": state,
        "permissions": permissions,
    })
    return json.dumps({"status": "ok", "count": result.get("count", 0)})


@mcp.tool()
async def kg_ingest_dimensional_standards(
    municipality: str,
    state: str,
    standards: list[dict],
) -> str:
    """Store dimensional standards in the knowledge graph.

    Args:
        municipality: Name of the city
        state: Two-letter state abbreviation
        standards: List of standard dicts, each with keys:
            - district: Zoning district code
            - name: Standard name (e.g., "Minimum Lot Area")
            - value: Standard value (e.g., "5,000 sq ft")
            - unit: Optional unit
            - section_ref: Optional source section reference
    """
    result = await _context_request("POST", "/kg/ingest/standards", json_body={
        "municipality": municipality,
        "state": state,
        "standards": standards,
    })
    return json.dumps({"status": "ok", "count": result.get("count", 0)})


@mcp.tool()
async def kg_ingest_definitions(
    municipality: str,
    state: str,
    definitions: list[dict],
) -> str:
    """Store zoning term definitions in the knowledge graph.

    Args:
        municipality: Name of the city
        state: Two-letter state abbreviation
        definitions: List of definition dicts, each with keys:
            - term: The defined term
            - definition: The definition text
            - section_ref: Optional source section reference
    """
    result = await _context_request("POST", "/kg/ingest/definitions", json_body={
        "municipality": municipality,
        "state": state,
        "definitions": definitions,
    })
    return json.dumps({"status": "ok", "count": result.get("count", 0)})


@mcp.tool()
async def kg_build_summaries(
    municipality: str,
    state: str,
    scope: str = "all",
) -> str:
    """Trigger recursive bottom-up summarization for a municipality's code tree.

    Summarizes leaf sections first, then divisions (from child summaries),
    then articles (from division summaries). This builds the RAPTOR-like
    summary tree that enables recursive search.

    Args:
        municipality: Name of the city
        state: Two-letter state abbreviation
        scope: Section ID to scope summarization, or "all" for everything
    """
    # Get sections organized for summarization
    sections_resp = await _context_request("POST", "/kg/summary/sections-for-build", json_body={
        "municipality": municipality,
        "state": state,
        "scope": scope,
    })
    sections = sections_resp.get("sections", [])

    if not sections:
        return json.dumps({"status": "ok", "message": "No sections to summarize", "count": 0})

    # Group by level for bottom-up processing
    by_level: dict[str, list[dict]] = {"section": [], "division": [], "article": []}
    for s in sections:
        data = s.get("s", s)  # Handle AGE result wrapping
        level = data.get("level", "section") if isinstance(data, dict) else "section"
        if level in by_level:
            by_level[level].append(data)

    summarized = 0

    # Phase 1: Summarize leaf sections from raw content
    for sec in by_level["section"]:
        sid = sec.get("section_id", "")
        raw = sec.get("raw_content", "")
        if not raw or not sid:
            continue
        summary = await _summarize(raw, "section")
        await _context_request("POST", "/kg/summary/update", json_body={
            "municipality": municipality,
            "state": state,
            "section_id": sid,
            "summary": summary,
            "summary_level": "section",
        })
        summarized += 1

    # Phase 2: Summarize divisions from child section summaries
    for div in by_level["division"]:
        sid = div.get("section_id", "")
        if not sid:
            continue
        children_resp = await _context_request("POST", "/kg/children", json_body={
            "municipality": municipality,
            "state": state,
            "section_id": sid,
        })
        children = children_resp.get("children", [])
        child_summaries = []
        for child in children:
            child_data = child.get("c", child)
            s = child_data.get("summary", "") if isinstance(child_data, dict) else ""
            if s:
                child_summaries.append(s)

        if child_summaries:
            combined = "\n\n".join(child_summaries)
            summary = await _summarize(combined, "division")
        else:
            # Fall back to raw content if no child summaries
            raw = div.get("raw_content", "")
            summary = await _summarize(raw, "section") if raw else ""

        if summary:
            await _context_request("POST", "/kg/summary/update", json_body={
                "municipality": municipality,
                "state": state,
                "section_id": sid,
                "summary": summary,
                "summary_level": "division",
            })
            summarized += 1

    # Phase 3: Summarize articles from child division summaries
    for art in by_level["article"]:
        sid = art.get("section_id", "")
        if not sid:
            continue
        children_resp = await _context_request("POST", "/kg/children", json_body={
            "municipality": municipality,
            "state": state,
            "section_id": sid,
        })
        children = children_resp.get("children", [])
        child_summaries = []
        for child in children:
            child_data = child.get("c", child)
            s = child_data.get("summary", "") if isinstance(child_data, dict) else ""
            if s:
                child_summaries.append(s)

        if child_summaries:
            combined = "\n\n".join(child_summaries)
            summary = await _summarize(combined, "article")
        else:
            raw = art.get("raw_content", "")
            summary = await _summarize(raw, "section") if raw else ""

        if summary:
            await _context_request("POST", "/kg/summary/update", json_body={
                "municipality": municipality,
                "state": state,
                "section_id": sid,
                "summary": summary,
                "summary_level": "article",
            })
            summarized += 1

    return json.dumps({
        "status": "ok",
        "message": f"Summarized {summarized} sections",
        "count": summarized,
        "by_level": {k: len(v) for k, v in by_level.items()},
    })


@mcp.tool()
async def kg_rebuild_summary(
    municipality: str,
    state: str,
    section_id: str,
    instructions: str = "",
) -> str:
    """Re-summarize a specific section and rebuild ancestor summaries.

    Use this when the initial summarization missed important details.
    Rebuilds the section's summary, then propagates up to parent → article.

    Args:
        municipality: Name of the city
        state: Two-letter state abbreviation
        section_id: Section to re-summarize
        instructions: Optional guidance for the LLM (e.g., "focus on setback requirements")
    """
    # Get the section
    section_resp = await _context_request("POST", "/kg/query/section", json_body={
        "municipality": municipality,
        "state": state,
        "section_id": section_id,
    })
    section = section_resp.get("section", {})
    section_data = section.get("s", section)
    raw = section_data.get("raw_content", "") if isinstance(section_data, dict) else ""

    if not raw:
        return json.dumps({"status": "error", "message": "Section has no raw content"})

    # Re-summarize with optional instructions
    prompt = _SUMMARY_PROMPTS.get("section", "") + raw
    if instructions:
        prompt += f"\n\nAdditional focus: {instructions}"
    summary = await _llm_call(prompt)

    await _context_request("POST", "/kg/summary/update", json_body={
        "municipality": municipality,
        "state": state,
        "section_id": section_id,
        "summary": summary,
        "summary_level": section_data.get("level", "section") if isinstance(section_data, dict) else "section",
    })

    # Rebuild ancestor summaries
    ancestors_resp = await _context_request("POST", "/kg/ancestors", json_body={
        "municipality": municipality,
        "state": state,
        "section_id": section_id,
    })
    ancestors = ancestors_resp.get("ancestors", [])
    rebuilt_ancestors = []

    for anc in ancestors:
        anc_data = anc.get("a", anc)
        anc_id = anc_data.get("section_id", "") if isinstance(anc_data, dict) else ""
        anc_level = anc_data.get("level", "division") if isinstance(anc_data, dict) else "division"
        if not anc_id:
            continue

        # Get children summaries for this ancestor
        children_resp = await _context_request("POST", "/kg/children", json_body={
            "municipality": municipality,
            "state": state,
            "section_id": anc_id,
        })
        children = children_resp.get("children", [])
        child_summaries = []
        for child in children:
            child_data = child.get("c", child)
            s = child_data.get("summary", "") if isinstance(child_data, dict) else ""
            if s:
                child_summaries.append(s)

        if child_summaries:
            combined = "\n\n".join(child_summaries)
            anc_summary = await _summarize(combined, anc_level)
            await _context_request("POST", "/kg/summary/update", json_body={
                "municipality": municipality,
                "state": state,
                "section_id": anc_id,
                "summary": anc_summary,
                "summary_level": anc_level,
            })
            rebuilt_ancestors.append(anc_id)

    return json.dumps({
        "status": "ok",
        "section_id": section_id,
        "summary": summary,
        "ancestors_rebuilt": rebuilt_ancestors,
    })


# ---------------------------------------------------------------------------
# MCP Tools — Query
# ---------------------------------------------------------------------------

@mcp.tool()
async def kg_query_section(
    municipality: str,
    state: str,
    section_id: str,
    level: str = "raw",
) -> str:
    """Get a section's content and/or summary at the requested abstraction level.

    Args:
        municipality: Name of the city
        state: Two-letter state abbreviation
        section_id: Section identifier
        level: "raw" for full text, "section"/"division"/"article" for summary at that level
    """
    section_resp = await _context_request("POST", "/kg/query/section", json_body={
        "municipality": municipality,
        "state": state,
        "section_id": section_id,
    })
    section = section_resp.get("section", {})
    section_data = section.get("s", section)

    if not isinstance(section_data, dict):
        return json.dumps({"error": "Section not found"})

    if level == "raw":
        return json.dumps({
            "section_id": section_data.get("section_id", section_id),
            "title": section_data.get("title", ""),
            "content": section_data.get("raw_content", ""),
            "summary": section_data.get("summary", ""),
        })
    else:
        # Return summary, falling back to raw if no summary available
        summary = section_data.get("summary", "")
        if not summary:
            summary = f"[No summary available — raw content]: {section_data.get('raw_content', '')[:500]}"
        return json.dumps({
            "section_id": section_data.get("section_id", section_id),
            "title": section_data.get("title", ""),
            "summary": summary,
            "summary_level": section_data.get("summary_level", ""),
        })


@mcp.tool()
async def kg_query_permissions(
    municipality: str,
    state: str,
    district: str = "",
    use: str = "",
    permission_level: str = "",
) -> str:
    """Query what uses are permitted/conditional/prohibited in a district.

    Args:
        municipality: Name of the city
        state: Two-letter state abbreviation
        district: Optional zoning district code to filter (e.g., "R1")
        use: Optional land use name to filter (e.g., "restaurant")
        permission_level: Optional "permitted" or "conditional" filter
    """
    result = await _context_request("POST", "/kg/query/permissions", json_body={
        "municipality": municipality,
        "state": state,
        "district": district or None,
        "use": use or None,
        "permission_level": permission_level or None,
    })
    permissions = result.get("permissions", [])
    if not permissions:
        msg = f"No use permissions found"
        if district:
            msg += f" for district {district}"
        if use:
            msg += f" for use '{use}'"
        return msg

    return json.dumps({"permissions": permissions, "count": len(permissions)}, indent=2)


@mcp.tool()
async def kg_query_standards(
    municipality: str,
    state: str,
    district: str = "",
    standard_type: str = "",
) -> str:
    """Query dimensional standards (lot area, setbacks, height, etc.) for a district.

    Args:
        municipality: Name of the city
        state: Two-letter state abbreviation
        district: Optional zoning district code to filter
        standard_type: Optional standard type to filter (e.g., "Minimum Lot Area")
    """
    result = await _context_request("POST", "/kg/query/standards", json_body={
        "municipality": municipality,
        "state": state,
        "district": district or None,
        "standard_type": standard_type or None,
    })
    standards = result.get("standards", [])
    if not standards:
        return f"No dimensional standards found for the given filters"

    return json.dumps({"standards": standards, "count": len(standards)}, indent=2)


@mcp.tool()
async def kg_query_definition(
    municipality: str,
    state: str,
    term: str,
) -> str:
    """Look up a zoning term definition.

    Args:
        municipality: Name of the city
        state: Two-letter state abbreviation
        term: The zoning term to look up (e.g., "accessory dwelling unit")
    """
    result = await _context_request("POST", "/kg/query/definition", json_body={
        "municipality": municipality,
        "state": state,
        "term": term,
    })
    defn = result.get("definition")
    if not defn:
        return f"Definition for '{term}' not found in {municipality}, {state}"

    return json.dumps(defn, indent=2)


@mcp.tool()
async def kg_traverse_hierarchy(
    municipality: str,
    state: str,
    start_section: str,
    direction: str = "down",
    depth: int = 3,
) -> str:
    """Walk the document tree from a starting point.

    Args:
        municipality: Name of the city
        state: Two-letter state abbreviation
        start_section: Section ID to start from
        direction: "up" (ancestors), "down" (descendants), or "both"
        depth: Maximum depth to traverse (default 3)
    """
    result = await _context_request("POST", "/kg/traverse", json_body={
        "municipality": municipality,
        "state": state,
        "start_section": start_section,
        "direction": direction,
        "depth": depth,
    })
    sections = result.get("sections", [])
    return json.dumps({
        "start_section": start_section,
        "direction": direction,
        "sections": sections,
        "count": len(sections),
    }, indent=2)


@mcp.tool()
async def kg_find_related(
    municipality: str,
    state: str,
    section_id: str,
    relationship_type: str = "",
) -> str:
    """Find cross-referenced sections and follow citation edges.

    Args:
        municipality: Name of the city
        state: Two-letter state abbreviation
        section_id: Section to find relationships for
        relationship_type: Optional filter (e.g., "constrains", "defines", "requires")
    """
    result = await _context_request("POST", "/kg/related", json_body={
        "municipality": municipality,
        "state": state,
        "section_id": section_id,
        "relationship_type": relationship_type or None,
    })
    related = result.get("related", [])
    return json.dumps({
        "section_id": section_id,
        "related": related,
        "count": len(related),
    }, indent=2)


@mcp.tool()
async def kg_search_by_topic(
    municipality: str,
    state: str,
    query: str,
) -> str:
    """Recursive descent search — start from article summaries, drill into matching branches.

    Instead of vector search, this uses the LLM to score relevance at each level
    of the document hierarchy:
    1. Compare query against article-level summaries → pick top matches
    2. Descend into divisions within matched articles → pick top matches
    3. Descend into sections within matched divisions → return leaf results

    This gives a reasoning trace: "Found in Article XII → Division 2 → Section 50-12-201"

    Args:
        municipality: Name of the city
        state: Two-letter state abbreviation
        query: Natural language query (e.g., "accessory dwelling units")
    """
    scoring_system = (
        "You are a zoning code search assistant. Given a user query and a list of "
        "summaries from a municipal zoning code, return ONLY the numbers (1-indexed) "
        "of the most relevant items as a JSON array. Return at most 3 items. "
        "Example: [1, 3] means items 1 and 3 are relevant. "
        "Return [] if none are relevant. Return ONLY the JSON array, nothing else."
    )

    trace = []
    visited: set[str] = set()  # Cycle prevention

    # Level 1: Article summaries
    articles_resp = await _context_request("POST", "/kg/sections-by-level", json_body={
        "municipality": municipality,
        "state": state,
        "level": "article",
    })
    articles = articles_resp.get("sections", [])
    if not articles:
        return json.dumps({"message": "No articles found. Has the code been ingested?", "results": []})

    # Score articles
    article_list = "\n".join(
        f"{i+1}. [{a.get('section_id', '?')}] {a.get('title', 'Untitled')}: "
        f"{a.get('summary', '') or a.get('raw_content', '')[:200]}"
        for i, a in enumerate(articles)
    )
    score_prompt = f"User query: {query}\n\nArticle summaries:\n{article_list}"
    score_result = await _llm_call(score_prompt, system=scoring_system)

    try:
        selected_indices = json.loads(score_result.strip())
    except (json.JSONDecodeError, ValueError):
        # Try to extract array from response
        match = re.search(r"\[[\d\s,]*\]", score_result)
        selected_indices = json.loads(match.group()) if match else []

    selected_articles = [
        articles[i - 1] for i in selected_indices
        if isinstance(i, int) and 1 <= i <= len(articles)
    ]

    if not selected_articles:
        return json.dumps({
            "message": "No relevant articles found for this query",
            "query": query,
            "results": [],
        })

    trace.append({
        "level": "article",
        "matched": [a.get("section_id", "") for a in selected_articles],
    })

    # Level 2: Division summaries within matched articles
    all_divisions = []
    for art in selected_articles:
        art_id = art.get("section_id", "")
        if not art_id or art_id in visited:
            continue
        visited.add(art_id)
        children_resp = await _context_request("POST", "/kg/children", json_body={
            "municipality": municipality,
            "state": state,
            "section_id": art_id,
        })
        children = children_resp.get("children", [])
        for child in children:
            child_data = child.get("c", child)
            if isinstance(child_data, dict):
                child_data["_parent_article"] = art_id
                all_divisions.append(child_data)

    if all_divisions:
        div_list = "\n".join(
            f"{i+1}. [{d.get('section_id', '?')}] {d.get('title', 'Untitled')}: "
            f"{d.get('summary', '') or d.get('raw_content', '')[:200]}"
            for i, d in enumerate(all_divisions)
        )
        score_prompt = f"User query: {query}\n\nDivision summaries:\n{div_list}"
        score_result = await _llm_call(score_prompt, system=scoring_system)

        try:
            selected_indices = json.loads(score_result.strip())
        except (json.JSONDecodeError, ValueError):
            match = re.search(r"\[[\d\s,]*\]", score_result)
            selected_indices = json.loads(match.group()) if match else []

        selected_divisions = [
            all_divisions[i - 1] for i in selected_indices
            if isinstance(i, int) and 1 <= i <= len(all_divisions)
        ]
    else:
        selected_divisions = []

    if selected_divisions:
        trace.append({
            "level": "division",
            "matched": [d.get("section_id", "") for d in selected_divisions],
        })

    # Level 3: Sections within matched divisions (or directly under articles)
    all_sections = []
    search_parents = selected_divisions if selected_divisions else selected_articles
    for parent in search_parents:
        parent_id = parent.get("section_id", "")
        if not parent_id or parent_id in visited:
            continue
        visited.add(parent_id)
        children_resp = await _context_request("POST", "/kg/children", json_body={
            "municipality": municipality,
            "state": state,
            "section_id": parent_id,
        })
        children = children_resp.get("children", [])
        for child in children:
            child_data = child.get("c", child)
            if isinstance(child_data, dict):
                child_data["_parent"] = parent_id
                all_sections.append(child_data)

    results = []
    if all_sections:
        sec_list = "\n".join(
            f"{i+1}. [{s.get('section_id', '?')}] {s.get('title', 'Untitled')}: "
            f"{s.get('summary', '') or (s.get('raw_content', '') or '')[:200]}"
            for i, s in enumerate(all_sections)
        )
        score_prompt = f"User query: {query}\n\nSection summaries:\n{sec_list}"
        score_result = await _llm_call(score_prompt, system=scoring_system)

        try:
            selected_indices = json.loads(score_result.strip())
        except (json.JSONDecodeError, ValueError):
            match = re.search(r"\[[\d\s,]*\]", score_result)
            selected_indices = json.loads(match.group()) if match else []

        for i in selected_indices:
            if isinstance(i, int) and 1 <= i <= len(all_sections):
                sec = all_sections[i - 1]
                results.append({
                    "section_id": sec.get("section_id", ""),
                    "title": sec.get("title", ""),
                    "summary": sec.get("summary", ""),
                    "level": sec.get("level", "section"),
                    "parent": sec.get("_parent", ""),
                })

        trace.append({
            "level": "section",
            "matched": [r["section_id"] for r in results],
        })

    return json.dumps({
        "query": query,
        "results": results,
        "trace": trace,
        "message": f"Found {len(results)} relevant sections via recursive search",
    }, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
