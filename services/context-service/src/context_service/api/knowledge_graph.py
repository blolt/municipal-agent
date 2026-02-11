"""FastAPI router for Knowledge Graph operations.

Exposes the KnowledgeGraphRepository as HTTP endpoints consumed by
the Knowledge Graph MCP server in the Execution Service.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from context_service.db.kg_repository import KnowledgeGraphRepository

router = APIRouter(prefix="/kg", tags=["knowledge-graph"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class IngestSectionRequest(BaseModel):
    municipality: str
    state: str
    section_id: str
    title: str
    content: str
    level: str = "section"
    parent_id: str | None = None


class IngestSectionResponse(BaseModel):
    status: str = "ok"
    section_id: str
    node: dict[str, Any] = Field(default_factory=dict)


class IngestPermissionsRequest(BaseModel):
    municipality: str
    state: str
    permissions: list[dict[str, Any]]


class IngestStandardsRequest(BaseModel):
    municipality: str
    state: str
    standards: list[dict[str, Any]]


class IngestDefinitionsRequest(BaseModel):
    municipality: str
    state: str
    definitions: list[dict[str, Any]]


class IngestCountResponse(BaseModel):
    status: str = "ok"
    count: int


class CrossReferenceRequest(BaseModel):
    municipality: str
    state: str
    source_section_id: str
    target_section_id: str
    relationship_type: str = "unknown"
    context: str = ""
    raw_citation: str = ""


class ExternalCitationRequest(BaseModel):
    municipality: str
    state: str
    source_section_id: str
    law_id: str
    law_type: str
    raw_citation: str = ""


class UpdateSummaryRequest(BaseModel):
    municipality: str
    state: str
    section_id: str
    summary: str
    summary_level: str


class BuildSummariesRequest(BaseModel):
    municipality: str
    state: str
    scope: str | None = None


class SectionsForSummarizationResponse(BaseModel):
    status: str = "ok"
    sections: list[dict[str, Any]]


class QueryPermissionsParams(BaseModel):
    municipality: str
    state: str
    district: str | None = None
    use: str | None = None
    permission_level: str | None = None


class QueryStandardsParams(BaseModel):
    municipality: str
    state: str
    district: str | None = None
    standard_type: str | None = None


class TraverseRequest(BaseModel):
    municipality: str
    state: str
    start_section: str
    direction: str = "down"
    depth: int = 3


class FindRelatedRequest(BaseModel):
    municipality: str
    state: str
    section_id: str
    relationship_type: str | None = None


class SectionsByLevelRequest(BaseModel):
    municipality: str
    state: str
    level: str


class SectionIdRequest(BaseModel):
    municipality: str
    state: str
    section_id: str


class TermLookupRequest(BaseModel):
    municipality: str
    state: str
    term: str


# ---------------------------------------------------------------------------
# Endpoints — Ingestion (write path)
# ---------------------------------------------------------------------------

@router.post("/ingest/section", response_model=IngestSectionResponse, status_code=status.HTTP_201_CREATED)
async def ingest_section(req: IngestSectionRequest) -> IngestSectionResponse:
    """Ingest a raw code section into the knowledge graph."""
    try:
        await KnowledgeGraphRepository.get_or_create_municipality(req.municipality, req.state)
        node = await KnowledgeGraphRepository.ingest_code_section(
            municipality=req.municipality,
            state=req.state,
            section_id=req.section_id,
            title=req.title,
            content=req.content,
            level=req.level,
            parent_id=req.parent_id,
        )
        return IngestSectionResponse(section_id=req.section_id, node=node)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest section: {e}",
        )


@router.post("/ingest/permissions", response_model=IngestCountResponse, status_code=status.HTTP_201_CREATED)
async def ingest_permissions(req: IngestPermissionsRequest) -> IngestCountResponse:
    """Ingest use-permission matrix rows."""
    try:
        await KnowledgeGraphRepository.get_or_create_municipality(req.municipality, req.state)
        count = await KnowledgeGraphRepository.ingest_use_permissions(
            municipality=req.municipality,
            state=req.state,
            permissions=req.permissions,
        )
        return IngestCountResponse(count=count)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest permissions: {e}",
        )


@router.post("/ingest/standards", response_model=IngestCountResponse, status_code=status.HTTP_201_CREATED)
async def ingest_standards(req: IngestStandardsRequest) -> IngestCountResponse:
    """Ingest dimensional standards."""
    try:
        await KnowledgeGraphRepository.get_or_create_municipality(req.municipality, req.state)
        count = await KnowledgeGraphRepository.ingest_dimensional_standards(
            municipality=req.municipality,
            state=req.state,
            standards=req.standards,
        )
        return IngestCountResponse(count=count)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest standards: {e}",
        )


@router.post("/ingest/definitions", response_model=IngestCountResponse, status_code=status.HTTP_201_CREATED)
async def ingest_definitions(req: IngestDefinitionsRequest) -> IngestCountResponse:
    """Ingest zoning term definitions."""
    try:
        await KnowledgeGraphRepository.get_or_create_municipality(req.municipality, req.state)
        count = await KnowledgeGraphRepository.ingest_definitions(
            municipality=req.municipality,
            state=req.state,
            definitions=req.definitions,
        )
        return IngestCountResponse(count=count)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest definitions: {e}",
        )


@router.post("/ingest/cross-reference", status_code=status.HTTP_201_CREATED)
async def ingest_cross_reference(req: CrossReferenceRequest) -> dict[str, str]:
    """Add a cross-reference edge between two sections."""
    try:
        await KnowledgeGraphRepository.add_cross_reference(
            municipality=req.municipality,
            state=req.state,
            source_section_id=req.source_section_id,
            target_section_id=req.target_section_id,
            relationship_type=req.relationship_type,
            context=req.context,
            raw_citation=req.raw_citation,
        )
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add cross-reference: {e}",
        )


@router.post("/ingest/external-citation", status_code=status.HTTP_201_CREATED)
async def ingest_external_citation(req: ExternalCitationRequest) -> dict[str, str]:
    """Add an external law citation."""
    try:
        await KnowledgeGraphRepository.add_external_citation(
            municipality=req.municipality,
            state=req.state,
            source_section_id=req.source_section_id,
            law_id=req.law_id,
            law_type=req.law_type,
            raw_citation=req.raw_citation,
        )
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add external citation: {e}",
        )


# ---------------------------------------------------------------------------
# Endpoints — Summarization
# ---------------------------------------------------------------------------

@router.post("/summary/update")
async def update_summary(req: UpdateSummaryRequest) -> dict[str, Any]:
    """Update a section's summary."""
    try:
        result = await KnowledgeGraphRepository.update_summary(
            municipality=req.municipality,
            state=req.state,
            section_id=req.section_id,
            summary=req.summary,
            summary_level=req.summary_level,
        )
        return {"status": "ok", "node": result}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update summary: {e}",
        )


@router.post("/summary/sections-for-build", response_model=SectionsForSummarizationResponse)
async def get_sections_for_summarization(req: BuildSummariesRequest) -> SectionsForSummarizationResponse:
    """Get sections organized for bottom-up summarization."""
    try:
        sections = await KnowledgeGraphRepository.get_sections_for_summarization(
            municipality=req.municipality,
            state=req.state,
            scope=req.scope,
        )
        return SectionsForSummarizationResponse(sections=sections)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sections: {e}",
        )


@router.post("/children")
async def get_children(req: SectionIdRequest) -> dict[str, Any]:
    """Get direct children of a section."""
    try:
        children = await KnowledgeGraphRepository.get_children(
            municipality=req.municipality,
            state=req.state,
            section_id=req.section_id,
        )
        return {"children": children}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get children: {e}",
        )


@router.post("/ancestors")
async def get_ancestors(req: SectionIdRequest) -> dict[str, Any]:
    """Get ancestor chain for a section."""
    try:
        ancestors = await KnowledgeGraphRepository.get_ancestors(
            municipality=req.municipality,
            state=req.state,
            section_id=req.section_id,
        )
        return {"ancestors": ancestors}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get ancestors: {e}",
        )


# ---------------------------------------------------------------------------
# Endpoints — Query (read path)
# ---------------------------------------------------------------------------

@router.post("/query/section")
async def query_section(req: SectionIdRequest) -> dict[str, Any]:
    """Get a section's content and summary."""
    try:
        section = await KnowledgeGraphRepository.get_section(
            municipality=req.municipality,
            state=req.state,
            section_id=req.section_id,
        )
        if section is None:
            raise HTTPException(status_code=404, detail="Section not found")
        return {"section": section}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query section: {e}",
        )


@router.post("/query/permissions")
async def query_permissions(req: QueryPermissionsParams) -> dict[str, Any]:
    """Query use permissions with optional filters."""
    try:
        results = await KnowledgeGraphRepository.query_permissions(
            municipality=req.municipality,
            state=req.state,
            district=req.district,
            use=req.use,
            permission_level=req.permission_level,
        )
        return {"permissions": results}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query permissions: {e}",
        )


@router.post("/query/standards")
async def query_standards(req: QueryStandardsParams) -> dict[str, Any]:
    """Query dimensional standards."""
    try:
        results = await KnowledgeGraphRepository.query_standards(
            municipality=req.municipality,
            state=req.state,
            district=req.district,
            standard_type=req.standard_type,
        )
        return {"standards": results}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query standards: {e}",
        )


@router.post("/query/definition")
async def query_definition(req: TermLookupRequest) -> dict[str, Any]:
    """Look up a zoning term definition."""
    try:
        result = await KnowledgeGraphRepository.query_definition(
            municipality=req.municipality,
            state=req.state,
            term=req.term,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Term not found")
        return {"definition": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query definition: {e}",
        )


@router.post("/traverse")
async def traverse_hierarchy(req: TraverseRequest) -> dict[str, Any]:
    """Walk the document tree from a starting point."""
    try:
        results = await KnowledgeGraphRepository.traverse_hierarchy(
            municipality=req.municipality,
            state=req.state,
            start_section=req.start_section,
            direction=req.direction,
            depth=req.depth,
        )
        return {"sections": results}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to traverse hierarchy: {e}",
        )


@router.post("/related")
async def find_related(req: FindRelatedRequest) -> dict[str, Any]:
    """Find cross-referenced sections and citation edges."""
    try:
        results = await KnowledgeGraphRepository.find_related(
            municipality=req.municipality,
            state=req.state,
            section_id=req.section_id,
            relationship_type=req.relationship_type,
        )
        return {"related": results}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find related sections: {e}",
        )


@router.post("/sections-by-level")
async def sections_by_level(req: SectionsByLevelRequest) -> dict[str, Any]:
    """Get all sections at a given level."""
    try:
        results = await KnowledgeGraphRepository.get_sections_by_level(
            municipality=req.municipality,
            state=req.state,
            level=req.level,
        )
        return {"sections": results}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sections by level: {e}",
        )


# ---------------------------------------------------------------------------
# Graph initialization
# ---------------------------------------------------------------------------

@router.post("/init")
async def initialize_graph() -> dict[str, str]:
    """Ensure the AGE graph and labels exist."""
    try:
        await KnowledgeGraphRepository.ensure_graph()
        return {"status": "ok", "message": "Knowledge graph initialized"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize graph: {e}",
        )
