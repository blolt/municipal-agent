"""Tests for the Knowledge Graph MCP server (FastMCP).

Tests each of the 13 MCP tools by mocking the Context Service HTTP layer
(_context_request) and the LLM layer (_llm_call). Follows the same pattern
as test_municode_mcp.py.
"""

import json
from unittest.mock import patch, AsyncMock

import pytest

from mcp_servers.knowledge_graph_server import (
    kg_ingest_code_section,
    kg_ingest_use_permissions,
    kg_ingest_dimensional_standards,
    kg_ingest_definitions,
    kg_build_summaries,
    kg_rebuild_summary,
    kg_query_section,
    kg_query_permissions,
    kg_query_standards,
    kg_query_definition,
    kg_traverse_hierarchy,
    kg_find_related,
    kg_search_by_topic,
    _extract_citations,
    _classify_relationship,
    CitationType,
)


# ---------------------------------------------------------------------------
# Fixtures — reusable mock data
# ---------------------------------------------------------------------------

MOCK_INGEST_RESPONSE = {"status": "ok", "section_id": "50-12-101", "node": {}}
MOCK_COUNT_RESPONSE = {"status": "ok", "count": 3}
MOCK_SECTION = {
    "section": {
        "s": {
            "section_id": "50-12-101",
            "title": "Use tables",
            "level": "section",
            "raw_content": "This section establishes use tables for zoning districts.",
            "summary": "Establishes use tables defining permitted land uses per district.",
            "summary_level": "section",
        }
    }
}
MOCK_PERMISSIONS = {
    "permissions": [
        {"district": "R1", "use_name": "One-family dwelling", "permission_level": "permitted", "conditions": ""},
        {"district": "R1", "use_name": "Restaurant", "permission_level": "conditional", "conditions": "Site plan required"},
    ]
}
MOCK_STANDARDS = {
    "standards": [
        {"district": "R1", "standard_type": "Minimum Lot Area", "value": "5,000 sq ft", "unit": "sq ft", "section_ref": "50-12-201"},
    ]
}
MOCK_DEFINITION = {
    "definition": {"term": "accessory dwelling unit", "definition": "A subordinate dwelling unit...", "section_ref": "50-2-101"}
}
MOCK_TRAVERSE = {
    "sections": [
        {"section_id": "50-12-101", "title": "Use tables", "level": "section", "summary": "..."},
        {"section_id": "50-12-102", "title": "Standards", "level": "section", "summary": "..."},
    ]
}
MOCK_RELATED = {
    "related": [
        {"section_id": "50-12-201", "title": "Site plan", "summary": "...", "relationship_type": "constrains", "context": "", "direction": "outgoing"},
    ]
}
MOCK_ARTICLES = {
    "sections": [
        {"section_id": "art-1", "title": "Article I - General", "summary": "General provisions", "raw_content": ""},
        {"section_id": "art-12", "title": "Article XII - Use Regs", "summary": "Use regulations", "raw_content": ""},
    ]
}
MOCK_CHILDREN = {
    "children": [
        {"c": {"section_id": "div-1", "title": "Division 1", "summary": "Residential uses", "raw_content": ""}},
        {"c": {"section_id": "div-2", "title": "Division 2", "summary": "Commercial uses", "raw_content": ""}},
    ]
}
MOCK_SECTIONS_FOR_BUILD = {
    "sections": [
        {"s": {"section_id": "sec-1", "level": "section", "raw_content": "Content for sec-1"}},
        {"s": {"section_id": "div-1", "level": "division", "raw_content": ""}},
        {"s": {"section_id": "art-1", "level": "article", "raw_content": ""}},
    ]
}


# ---------------------------------------------------------------------------
# Citation extraction tests
# ---------------------------------------------------------------------------

class TestCitationExtraction:
    """Tests for citation extraction (ported from strongtowns-detroit)."""

    def test_section_reference(self):
        citations = _extract_citations("See Section 50-12-101 for details.", "50-1-1")
        targets = [c["target"] for c in citations]
        assert "50-12-101" in targets

    def test_sec_dot_reference(self):
        citations = _extract_citations("Sec. 50-3-200 applies.", "50-1-1")
        targets = [c["target"] for c in citations]
        assert "50-3-200" in targets

    def test_section_range(self):
        citations = _extract_citations("Sections 50-12-101 through 50-12-103.", "50-1-1")
        targets = [c["target"] for c in citations]
        assert "50-12-101" in targets
        assert "50-12-102" in targets
        assert "50-12-103" in targets

    def test_bare_section_number(self):
        citations = _extract_citations("complies with 50-12-101 requirements", "50-1-1")
        targets = [c["target"] for c in citations]
        assert "50-12-101" in targets

    def test_article_reference(self):
        citations = _extract_citations("as provided in Article XII", "50-1-1")
        targets = [c["target"] for c in citations]
        assert "article:XII" in targets

    def test_division_reference(self):
        citations = _extract_citations("Division 2 of this article", "50-1-1")
        targets = [c["target"] for c in citations]
        assert "div:2" in targets

    def test_mcl_reference(self):
        citations = _extract_citations("per MCL 125.3101", "50-1-1")
        targets = [c["target"] for c in citations]
        assert "mcl:125.3101" in targets

    def test_usc_reference(self):
        citations = _extract_citations("42 USC 11001 requirements", "50-1-1")
        targets = [c["target"] for c in citations]
        assert "usc:42-11001" in targets

    def test_cfr_reference(self):
        citations = _extract_citations("44 CFR 60.3 flood standards", "50-1-1")
        targets = [c["target"] for c in citations]
        assert "cfr:44-60.3" in targets

    def test_public_act_reference(self):
        citations = _extract_citations("P.A. 110 of 2006", "50-1-1")
        targets = [c["target"] for c in citations]
        assert "pa:110 of 2006" in targets

    def test_no_duplicate_spans(self):
        """Section range should not also match individual section regex."""
        citations = _extract_citations("Sections 50-12-101 through 50-12-102", "50-1-1")
        # Should have 2 citations (101, 102 from range), not 4 (range + individual)
        section_targets = [c for c in citations if c["target"] in ("50-12-101", "50-12-102")]
        assert len(section_targets) == 2


class TestRelationshipClassification:
    """Tests for cross-reference relationship classification."""

    def test_defines(self):
        assert _classify_relationship("as defined in Section 50-2-1") == "defines"

    def test_constrains(self):
        assert _classify_relationship("subject to the requirements of") == "constrains"

    def test_requires(self):
        assert _classify_relationship("shall comply with Section") == "requires"

    def test_excepts(self):
        assert _classify_relationship("except as provided in Article III") == "excepts"

    def test_supersedes(self):
        assert _classify_relationship("notwithstanding anything to the contrary") == "supersedes"

    def test_unknown_fallback(self):
        assert _classify_relationship("some random text about zoning") == "unknown"


# ---------------------------------------------------------------------------
# Ingestion tool tests
# ---------------------------------------------------------------------------

class TestIngestCodeSection:
    """Tests for kg_ingest_code_section tool."""

    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_ingest_section_success(self, mock_ctx):
        mock_ctx.return_value = MOCK_INGEST_RESPONSE

        result = await kg_ingest_code_section(
            municipality="Detroit",
            state="MI",
            section_id="50-12-101",
            title="Use tables",
            content="This section establishes use tables.",
            level="section",
            parent_id="50-12",
        )

        parsed = json.loads(result)
        assert parsed["status"] == "ok"
        assert parsed["section_id"] == "50-12-101"
        # Should have called ingest/section at minimum
        assert mock_ctx.call_count >= 1
        first_call = mock_ctx.call_args_list[0]
        assert first_call[0] == ("POST", "/kg/ingest/section")

    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_ingest_section_detects_citations(self, mock_ctx):
        """Content with cross-references should trigger citation ingestion."""
        mock_ctx.return_value = MOCK_INGEST_RESPONSE

        result = await kg_ingest_code_section(
            municipality="Detroit",
            state="MI",
            section_id="50-12-101",
            title="Use tables",
            content="Subject to Section 50-12-201 and MCL 125.3101.",
            level="section",
        )

        parsed = json.loads(result)
        assert parsed["cross_references_found"] >= 1
        assert parsed["external_citations_found"] >= 1

    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_ingest_section_no_parent(self, mock_ctx):
        """Ingesting without parent_id should work."""
        mock_ctx.return_value = MOCK_INGEST_RESPONSE

        result = await kg_ingest_code_section(
            municipality="Detroit",
            state="MI",
            section_id="50-12",
            title="Article XII",
            content="Article content",
            level="article",
        )

        parsed = json.loads(result)
        assert parsed["status"] == "ok"

    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_ingest_section_api_error(self, mock_ctx):
        mock_ctx.side_effect = RuntimeError("Context Service error 500: Internal")

        with pytest.raises(RuntimeError, match="500"):
            await kg_ingest_code_section(
                municipality="Detroit", state="MI",
                section_id="50-12-101", title="Test", content="Test",
            )


class TestIngestUsePermissions:
    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_ingest_permissions_success(self, mock_ctx):
        mock_ctx.return_value = MOCK_COUNT_RESPONSE

        result = await kg_ingest_use_permissions(
            municipality="Detroit",
            state="MI",
            permissions=[
                {"use": "One-family dwelling", "district": "R1", "level": "permitted"},
                {"use": "Restaurant", "district": "R1", "level": "conditional", "conditions": "Site plan required"},
            ],
        )

        parsed = json.loads(result)
        assert parsed["status"] == "ok"
        assert parsed["count"] == 3


class TestIngestDimensionalStandards:
    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_ingest_standards_success(self, mock_ctx):
        mock_ctx.return_value = MOCK_COUNT_RESPONSE

        result = await kg_ingest_dimensional_standards(
            municipality="Detroit",
            state="MI",
            standards=[
                {"district": "R1", "name": "Minimum Lot Area", "value": "5,000 sq ft"},
            ],
        )

        parsed = json.loads(result)
        assert parsed["status"] == "ok"


class TestIngestDefinitions:
    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_ingest_definitions_success(self, mock_ctx):
        mock_ctx.return_value = MOCK_COUNT_RESPONSE

        result = await kg_ingest_definitions(
            municipality="Detroit",
            state="MI",
            definitions=[
                {"term": "accessory dwelling unit", "definition": "A subordinate dwelling...", "section_ref": "50-2-101"},
            ],
        )

        parsed = json.loads(result)
        assert parsed["status"] == "ok"


# ---------------------------------------------------------------------------
# Summarization tool tests
# ---------------------------------------------------------------------------

class TestBuildSummaries:
    @patch("mcp_servers.knowledge_graph_server._llm_call", new_callable=AsyncMock)
    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_build_summaries_bottom_up(self, mock_ctx, mock_llm):
        """Builds summaries bottom-up: sections → divisions → articles."""
        mock_llm.return_value = "Generated summary."

        # Route different endpoints to different responses
        async def ctx_router(method, path, **kwargs):
            if "sections-for-build" in path:
                return MOCK_SECTIONS_FOR_BUILD
            if "children" in path:
                return MOCK_CHILDREN
            if "summary/update" in path:
                return {"status": "ok", "node": {}}
            return {"status": "ok"}

        mock_ctx.side_effect = ctx_router

        result = await kg_build_summaries(
            municipality="Detroit", state="MI", scope="all",
        )

        parsed = json.loads(result)
        assert parsed["status"] == "ok"
        assert parsed["count"] > 0
        # LLM should have been called for each level
        assert mock_llm.call_count >= 1

    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_build_summaries_no_sections(self, mock_ctx):
        """Returns gracefully when no sections exist."""
        mock_ctx.return_value = {"sections": []}

        result = await kg_build_summaries(
            municipality="Detroit", state="MI",
        )

        parsed = json.loads(result)
        assert parsed["count"] == 0


class TestRebuildSummary:
    @patch("mcp_servers.knowledge_graph_server._llm_call", new_callable=AsyncMock)
    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_rebuild_summary_with_ancestors(self, mock_ctx, mock_llm):
        mock_llm.return_value = "Rebuilt summary."

        async def ctx_router(method, path, **kwargs):
            if "query/section" in path:
                return MOCK_SECTION
            if "ancestors" in path:
                return {"ancestors": [{"a": {"section_id": "50-12", "level": "article"}}]}
            if "children" in path:
                return MOCK_CHILDREN
            if "summary/update" in path:
                return {"status": "ok", "node": {}}
            return {"status": "ok"}

        mock_ctx.side_effect = ctx_router

        result = await kg_rebuild_summary(
            municipality="Detroit", state="MI",
            section_id="50-12-101",
            instructions="focus on setback requirements",
        )

        parsed = json.loads(result)
        assert parsed["status"] == "ok"
        assert parsed["section_id"] == "50-12-101"
        assert "50-12" in parsed["ancestors_rebuilt"]


# ---------------------------------------------------------------------------
# Query tool tests
# ---------------------------------------------------------------------------

class TestQuerySection:
    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_query_section_raw(self, mock_ctx):
        mock_ctx.return_value = MOCK_SECTION

        result = await kg_query_section(
            municipality="Detroit", state="MI",
            section_id="50-12-101", level="raw",
        )

        parsed = json.loads(result)
        assert parsed["section_id"] == "50-12-101"
        assert "content" in parsed
        assert "summary" in parsed

    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_query_section_summary(self, mock_ctx):
        mock_ctx.return_value = MOCK_SECTION

        result = await kg_query_section(
            municipality="Detroit", state="MI",
            section_id="50-12-101", level="section",
        )

        parsed = json.loads(result)
        assert "summary" in parsed
        assert parsed["summary_level"] == "section"

    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_query_section_not_found(self, mock_ctx):
        mock_ctx.side_effect = RuntimeError("Context Service error 404: Not Found")

        with pytest.raises(RuntimeError, match="404"):
            await kg_query_section(
                municipality="Detroit", state="MI", section_id="99-99-999",
            )


class TestQueryPermissions:
    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_query_permissions_success(self, mock_ctx):
        mock_ctx.return_value = MOCK_PERMISSIONS

        result = await kg_query_permissions(
            municipality="Detroit", state="MI", district="R1",
        )

        parsed = json.loads(result)
        assert parsed["count"] == 2
        assert any(p["use_name"] == "One-family dwelling" for p in parsed["permissions"])

    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_query_permissions_empty(self, mock_ctx):
        mock_ctx.return_value = {"permissions": []}

        result = await kg_query_permissions(
            municipality="Detroit", state="MI", district="X99",
        )

        assert "No use permissions found" in result


class TestQueryStandards:
    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_query_standards_success(self, mock_ctx):
        mock_ctx.return_value = MOCK_STANDARDS

        result = await kg_query_standards(
            municipality="Detroit", state="MI", district="R1",
        )

        parsed = json.loads(result)
        assert parsed["count"] == 1
        assert parsed["standards"][0]["standard_type"] == "Minimum Lot Area"

    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_query_standards_empty(self, mock_ctx):
        mock_ctx.return_value = {"standards": []}

        result = await kg_query_standards(
            municipality="Detroit", state="MI", district="X99",
        )

        assert "No dimensional standards found" in result


class TestQueryDefinition:
    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_query_definition_success(self, mock_ctx):
        mock_ctx.return_value = MOCK_DEFINITION

        result = await kg_query_definition(
            municipality="Detroit", state="MI", term="accessory dwelling unit",
        )

        parsed = json.loads(result)
        assert parsed["term"] == "accessory dwelling unit"

    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_query_definition_not_found(self, mock_ctx):
        mock_ctx.return_value = {"definition": None}

        result = await kg_query_definition(
            municipality="Detroit", state="MI", term="nonexistent term",
        )

        assert "not found" in result


class TestTraverseHierarchy:
    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_traverse_down(self, mock_ctx):
        mock_ctx.return_value = MOCK_TRAVERSE

        result = await kg_traverse_hierarchy(
            municipality="Detroit", state="MI",
            start_section="50-12", direction="down", depth=3,
        )

        parsed = json.loads(result)
        assert parsed["start_section"] == "50-12"
        assert parsed["direction"] == "down"
        assert parsed["count"] == 2

    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_traverse_up(self, mock_ctx):
        mock_ctx.return_value = MOCK_TRAVERSE

        result = await kg_traverse_hierarchy(
            municipality="Detroit", state="MI",
            start_section="50-12-101", direction="up",
        )

        parsed = json.loads(result)
        assert parsed["direction"] == "up"


class TestFindRelated:
    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_find_related_success(self, mock_ctx):
        mock_ctx.return_value = MOCK_RELATED

        result = await kg_find_related(
            municipality="Detroit", state="MI",
            section_id="50-12-101",
        )

        parsed = json.loads(result)
        assert parsed["count"] == 1
        assert parsed["related"][0]["relationship_type"] == "constrains"

    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_find_related_with_type_filter(self, mock_ctx):
        mock_ctx.return_value = MOCK_RELATED

        result = await kg_find_related(
            municipality="Detroit", state="MI",
            section_id="50-12-101",
            relationship_type="constrains",
        )

        # Verify the filter is passed through
        call_body = mock_ctx.call_args[1]["json_body"]
        assert call_body["relationship_type"] == "constrains"


# ---------------------------------------------------------------------------
# Recursive search test
# ---------------------------------------------------------------------------

class TestSearchByTopic:
    @patch("mcp_servers.knowledge_graph_server._llm_call", new_callable=AsyncMock)
    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_search_by_topic_full_descent(self, mock_ctx, mock_llm):
        """Recursive search: articles → divisions → sections."""
        # LLM scores: select item 2 at article level, item 1 at division, item 1 at section
        mock_llm.side_effect = ["[2]", "[1]", "[1]"]

        section_children = {
            "children": [
                {"c": {"section_id": "sec-1", "title": "ADU Standards", "summary": "ADU regs", "raw_content": ""}},
            ]
        }

        async def ctx_router(method, path, **kwargs):
            body = kwargs.get("json_body", {})
            if "sections-by-level" in path:
                return MOCK_ARTICLES
            if "children" in path:
                # First call (article children) → divisions
                # Second call (division children) → sections
                sid = body.get("section_id", "")
                if sid.startswith("art"):
                    return MOCK_CHILDREN
                return section_children
            return {"status": "ok"}

        mock_ctx.side_effect = ctx_router

        result = await kg_search_by_topic(
            municipality="Detroit", state="MI", query="accessory dwelling units",
        )

        parsed = json.loads(result)
        assert len(parsed["results"]) >= 1
        assert len(parsed["trace"]) >= 1
        # Should have called LLM 3 times (one per level)
        assert mock_llm.call_count == 3

    @patch("mcp_servers.knowledge_graph_server._llm_call", new_callable=AsyncMock)
    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_search_no_articles(self, mock_ctx, mock_llm):
        """Returns gracefully when no articles exist."""
        mock_ctx.return_value = {"sections": []}

        result = await kg_search_by_topic(
            municipality="Detroit", state="MI", query="zoning",
        )

        parsed = json.loads(result)
        assert parsed["results"] == []
        assert "No articles found" in parsed["message"]

    @patch("mcp_servers.knowledge_graph_server._llm_call", new_callable=AsyncMock)
    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_search_no_relevant_articles(self, mock_ctx, mock_llm):
        """Returns gracefully when LLM finds no relevant articles."""
        mock_llm.return_value = "[]"
        mock_ctx.return_value = MOCK_ARTICLES

        result = await kg_search_by_topic(
            municipality="Detroit", state="MI", query="quantum physics",
        )

        parsed = json.loads(result)
        assert parsed["results"] == []
        assert "No relevant articles found" in parsed["message"]

    @patch("mcp_servers.knowledge_graph_server._llm_call", new_callable=AsyncMock)
    @patch("mcp_servers.knowledge_graph_server._context_request", new_callable=AsyncMock)
    async def test_search_llm_malformed_response(self, mock_ctx, mock_llm):
        """Handles malformed LLM response gracefully."""
        mock_llm.return_value = "I think items 1 and 3 are relevant [1, 3]"

        async def ctx_router(method, path, **kwargs):
            if "sections-by-level" in path:
                return MOCK_ARTICLES
            if "children" in path:
                return MOCK_CHILDREN
            return {"status": "ok"}

        mock_ctx.side_effect = ctx_router

        result = await kg_search_by_topic(
            municipality="Detroit", state="MI", query="land use",
        )

        # Should still work by extracting [1, 3] from the response
        parsed = json.loads(result)
        assert "trace" in parsed
