"""Unit tests for Knowledge Graph API endpoints."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from context_service.main import app

client = TestClient(app)


MOCK_SECTION_NODE = {"s": {"section_id": "50-12-101", "title": "Use tables"}}
MOCK_PERMISSIONS = [
    {"district": "R1", "use_name": "Dwelling", "permission_level": "permitted", "conditions": ""},
]


@pytest.mark.asyncio
async def test_ingest_section():
    """Test POST /kg/ingest/section."""
    with (
        patch("context_service.api.knowledge_graph.KnowledgeGraphRepository.get_or_create_municipality", new_callable=AsyncMock) as mock_muni,
        patch("context_service.api.knowledge_graph.KnowledgeGraphRepository.ingest_code_section", new_callable=AsyncMock) as mock_ingest,
    ):
        mock_muni.return_value = {"name": "Detroit", "state": "MI"}
        mock_ingest.return_value = MOCK_SECTION_NODE

        response = client.post("/kg/ingest/section", json={
            "municipality": "Detroit",
            "state": "MI",
            "section_id": "50-12-101",
            "title": "Use tables",
            "content": "Section content.",
            "level": "section",
        })

        assert response.status_code == 201
        assert response.json()["section_id"] == "50-12-101"
        mock_ingest.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_permissions():
    """Test POST /kg/ingest/permissions."""
    with (
        patch("context_service.api.knowledge_graph.KnowledgeGraphRepository.get_or_create_municipality", new_callable=AsyncMock),
        patch("context_service.api.knowledge_graph.KnowledgeGraphRepository.ingest_use_permissions", new_callable=AsyncMock) as mock_ingest,
    ):
        mock_ingest.return_value = 2

        response = client.post("/kg/ingest/permissions", json={
            "municipality": "Detroit",
            "state": "MI",
            "permissions": [
                {"use": "Dwelling", "district": "R1", "level": "permitted"},
                {"use": "Restaurant", "district": "R1", "level": "conditional"},
            ],
        })

        assert response.status_code == 201
        assert response.json()["count"] == 2


@pytest.mark.asyncio
async def test_ingest_standards():
    """Test POST /kg/ingest/standards."""
    with (
        patch("context_service.api.knowledge_graph.KnowledgeGraphRepository.get_or_create_municipality", new_callable=AsyncMock),
        patch("context_service.api.knowledge_graph.KnowledgeGraphRepository.ingest_dimensional_standards", new_callable=AsyncMock) as mock_ingest,
    ):
        mock_ingest.return_value = 1

        response = client.post("/kg/ingest/standards", json={
            "municipality": "Detroit",
            "state": "MI",
            "standards": [
                {"district": "R1", "name": "Min Lot Area", "value": "5000"},
            ],
        })

        assert response.status_code == 201
        assert response.json()["count"] == 1


@pytest.mark.asyncio
async def test_ingest_definitions():
    """Test POST /kg/ingest/definitions."""
    with (
        patch("context_service.api.knowledge_graph.KnowledgeGraphRepository.get_or_create_municipality", new_callable=AsyncMock),
        patch("context_service.api.knowledge_graph.KnowledgeGraphRepository.ingest_definitions", new_callable=AsyncMock) as mock_ingest,
    ):
        mock_ingest.return_value = 1

        response = client.post("/kg/ingest/definitions", json={
            "municipality": "Detroit",
            "state": "MI",
            "definitions": [
                {"term": "ADU", "definition": "Accessory dwelling unit"},
            ],
        })

        assert response.status_code == 201
        assert response.json()["count"] == 1


@pytest.mark.asyncio
async def test_query_permissions():
    """Test POST /kg/query/permissions."""
    with patch("context_service.api.knowledge_graph.KnowledgeGraphRepository.query_permissions", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = MOCK_PERMISSIONS

        response = client.post("/kg/query/permissions", json={
            "municipality": "Detroit",
            "state": "MI",
            "district": "R1",
        })

        assert response.status_code == 200
        assert len(response.json()["permissions"]) == 1


@pytest.mark.asyncio
async def test_query_definition():
    """Test POST /kg/query/definition."""
    with patch("context_service.api.knowledge_graph.KnowledgeGraphRepository.query_definition", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = {"term": "ADU", "definition": "Accessory dwelling unit", "section_ref": ""}

        response = client.post("/kg/query/definition", json={
            "municipality": "Detroit",
            "state": "MI",
            "term": "ADU",
        })

        assert response.status_code == 200
        assert response.json()["definition"]["term"] == "ADU"


@pytest.mark.asyncio
async def test_query_definition_not_found():
    """Test POST /kg/query/definition when term not found."""
    with patch("context_service.api.knowledge_graph.KnowledgeGraphRepository.query_definition", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = None

        response = client.post("/kg/query/definition", json={
            "municipality": "Detroit",
            "state": "MI",
            "term": "nonexistent",
        })

        assert response.status_code == 404


@pytest.mark.asyncio
async def test_traverse_hierarchy():
    """Test POST /kg/traverse."""
    with patch("context_service.api.knowledge_graph.KnowledgeGraphRepository.traverse_hierarchy", new_callable=AsyncMock) as mock_traverse:
        mock_traverse.return_value = [
            {"section_id": "50-12-101", "title": "Use tables", "level": "section", "summary": ""},
        ]

        response = client.post("/kg/traverse", json={
            "municipality": "Detroit",
            "state": "MI",
            "start_section": "50-12",
            "direction": "down",
            "depth": 3,
        })

        assert response.status_code == 200
        assert len(response.json()["sections"]) == 1


@pytest.mark.asyncio
async def test_find_related():
    """Test POST /kg/related."""
    with patch("context_service.api.knowledge_graph.KnowledgeGraphRepository.find_related", new_callable=AsyncMock) as mock_related:
        mock_related.return_value = [
            {"section_id": "50-12-201", "title": "Site plan", "relationship_type": "constrains", "direction": "outgoing"},
        ]

        response = client.post("/kg/related", json={
            "municipality": "Detroit",
            "state": "MI",
            "section_id": "50-12-101",
        })

        assert response.status_code == 200
        assert len(response.json()["related"]) == 1


@pytest.mark.asyncio
async def test_init_graph():
    """Test POST /kg/init."""
    with patch("context_service.api.knowledge_graph.KnowledgeGraphRepository.ensure_graph", new_callable=AsyncMock):
        response = client.post("/kg/init")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_ingest_section_error():
    """Test error handling in POST /kg/ingest/section."""
    with (
        patch("context_service.api.knowledge_graph.KnowledgeGraphRepository.get_or_create_municipality", new_callable=AsyncMock) as mock_muni,
    ):
        mock_muni.side_effect = Exception("DB connection failed")

        response = client.post("/kg/ingest/section", json={
            "municipality": "Detroit",
            "state": "MI",
            "section_id": "50-12-101",
            "title": "Test",
            "content": "Test",
        })

        assert response.status_code == 500
        assert "DB connection failed" in response.json()["detail"]
