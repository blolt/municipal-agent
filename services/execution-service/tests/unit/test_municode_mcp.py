"""Tests for the Municode MCP server (FastMCP)."""

import json
from unittest.mock import patch, call, AsyncMock

import pytest

from mcp_servers.municode_server import (
    municode_get_state_info,
    municode_list_municipalities,
    municode_get_municipality_info,
    municode_get_code_structure,
    municode_get_code_section,
    municode_search_codes,
    municode_get_url,
)


# ---------------------------------------------------------------------------
# Fixtures — reusable mock data
# ---------------------------------------------------------------------------

MOCK_CLIENT_INFO = {
    "ClientID": 12345,
    "ClientName": "Norfolk",
    "City": "Norfolk",
    "ZipCode": "23501",
    "Website": "https://www.norfolk.gov",
}

MOCK_PRODUCTS = [
    {
        "Id": 100,
        "ProductID": 200,
        "ProductName": "Code of Ordinances",
    },
    {
        "Id": 101,
        "ProductID": 201,
        "ProductName": "Charter",
    },
]

MOCK_TOC = [
    {"NodeId": "1001", "Heading": "Chapter 1 - GENERAL PROVISIONS", "HasChildren": True},
    {"NodeId": "1002", "Heading": "Chapter 2 - ADMINISTRATION", "HasChildren": True},
]

MOCK_CONTENT = {
    "NodeId": "1001",
    "Heading": "Chapter 1 - GENERAL PROVISIONS",
    "BodyHtml": "<p>Section content here...</p>",
}

MOCK_SEARCH_RESULTS = {
    "totalCount": 42,
    "results": [
        {"title": "Sec. 12-1. Zoning districts.", "snippet": "...zoning..."},
    ],
}

MOCK_STATE_INFO = {
    "StateID": 47,
    "StateName": "Virginia",
    "StateAbbr": "VA",
}

MOCK_MUNICIPALITIES = [
    {
        "ClientName": "Norfolk",
        "ClientID": 12345,
        "City": "Norfolk",
        "ZipCode": "23501",
        "Website": "https://www.norfolk.gov",
    },
    {
        "ClientName": "Richmond",
        "ClientID": 12346,
        "City": "Richmond",
        "ZipCode": "23219",
        "Website": "https://www.rva.gov",
    },
]


# ---------------------------------------------------------------------------
# municode_get_state_info
# ---------------------------------------------------------------------------

class TestGetStateInfo:
    """Tests for municode_get_state_info tool."""

    @patch("mcp_servers.municode_server._municode_request", new_callable=AsyncMock)
    async def test_get_state_info_success(self, mock_request):
        """Returns state info JSON."""
        mock_request.return_value = MOCK_STATE_INFO

        result = await municode_get_state_info(state_abbr="va")

        mock_request.assert_called_once_with(
            "GET", "/States/abbr",
            params={"stateAbbr": "VA"},
        )
        parsed = json.loads(result)
        assert parsed["StateName"] == "Virginia"

    @patch("mcp_servers.municode_server._municode_request", new_callable=AsyncMock)
    async def test_get_state_info_uppercases_abbr(self, mock_request):
        """State abbreviation is uppercased before API call."""
        mock_request.return_value = MOCK_STATE_INFO

        await municode_get_state_info(state_abbr="va")

        # Verify uppercased
        call_params = mock_request.call_args[1]["params"]
        assert call_params["stateAbbr"] == "VA"


# ---------------------------------------------------------------------------
# municode_list_municipalities
# ---------------------------------------------------------------------------

class TestListMunicipalities:
    """Tests for municode_list_municipalities tool."""

    @patch("mcp_servers.municode_server._municode_request", new_callable=AsyncMock)
    async def test_list_municipalities_success(self, mock_request):
        """Returns formatted list of municipalities."""
        mock_request.return_value = MOCK_MUNICIPALITIES

        result = await municode_list_municipalities(state_abbr="VA")

        mock_request.assert_called_once_with(
            "GET", "/Clients/stateAbbr",
            params={"stateAbbr": "VA"},
        )
        assert "Found 2 municipalities in VA" in result
        assert "Norfolk" in result
        assert "Richmond" in result

    @patch("mcp_servers.municode_server._municode_request", new_callable=AsyncMock)
    async def test_list_municipalities_api_error(self, mock_request):
        """API error raises RuntimeError."""
        mock_request.side_effect = RuntimeError("Municode API error 500: Internal Server Error")

        with pytest.raises(RuntimeError, match="500"):
            await municode_list_municipalities(state_abbr="ZZ")


# ---------------------------------------------------------------------------
# municode_get_municipality_info
# ---------------------------------------------------------------------------

class TestGetMunicipalityInfo:
    """Tests for municode_get_municipality_info tool."""

    @patch("mcp_servers.municode_server._municode_request", new_callable=AsyncMock)
    async def test_get_municipality_info_success(self, mock_request):
        """Returns client info + products via two API calls."""
        mock_request.side_effect = [MOCK_CLIENT_INFO, MOCK_PRODUCTS]

        result = await municode_get_municipality_info(
            municipality_name="Norfolk", state_abbr="VA"
        )

        assert mock_request.call_count == 2
        # First call: client lookup
        mock_request.assert_any_call(
            "GET", "/Clients/name",
            params={"clientName": "Norfolk", "stateAbbr": "VA"},
        )
        # Second call: client content
        mock_request.assert_any_call("GET", "/ClientContent/12345")

        parsed = json.loads(result)
        assert parsed["client_info"]["ClientID"] == 12345
        assert len(parsed["available_products"]) == 2

    @patch("mcp_servers.municode_server._municode_request", new_callable=AsyncMock)
    async def test_get_municipality_info_not_found(self, mock_request):
        """Municipality not found raises error."""
        mock_request.return_value = {"ClientID": None}

        with pytest.raises(RuntimeError, match="not found"):
            await municode_get_municipality_info(
                municipality_name="Fakeville", state_abbr="VA"
            )


# ---------------------------------------------------------------------------
# municode_get_code_structure
# ---------------------------------------------------------------------------

class TestGetCodeStructure:
    """Tests for municode_get_code_structure tool."""

    @patch("mcp_servers.municode_server._municode_request", new_callable=AsyncMock)
    async def test_get_code_structure_success(self, mock_request):
        """Multi-step flow: client lookup -> products -> TOC."""
        mock_request.side_effect = [MOCK_CLIENT_INFO, MOCK_PRODUCTS, MOCK_TOC]

        result = await municode_get_code_structure(
            municipality_name="Norfolk", state_abbr="VA"
        )

        assert mock_request.call_count == 3
        # Third call should be TOC with default root node
        toc_call = mock_request.call_args_list[2]
        assert toc_call == call(
            "GET", "/codesToc/children",
            params={"jobId": 100, "productId": 200, "nodeId": "10121"},
        )

        assert "Code structure for Norfolk, VA" in result
        assert "GENERAL PROVISIONS" in result

    @patch("mcp_servers.municode_server._municode_request", new_callable=AsyncMock)
    async def test_get_code_structure_custom_node(self, mock_request):
        """Supports custom node_id parameter."""
        mock_request.side_effect = [MOCK_CLIENT_INFO, MOCK_PRODUCTS, MOCK_TOC]

        await municode_get_code_structure(
            municipality_name="Norfolk", state_abbr="VA", node_id="5555"
        )

        toc_call = mock_request.call_args_list[2]
        assert toc_call[1]["params"]["nodeId"] == "5555"

    @patch("mcp_servers.municode_server._municode_request", new_callable=AsyncMock)
    async def test_get_code_structure_no_code_product(self, mock_request):
        """Error when municipality has no code of ordinances product."""
        no_code_products = [{"Id": 101, "ProductID": 201, "ProductName": "Charter"}]
        mock_request.side_effect = [MOCK_CLIENT_INFO, no_code_products]

        with pytest.raises(RuntimeError, match="No code of ordinances"):
            await municode_get_code_structure(
                municipality_name="Norfolk", state_abbr="VA"
            )


# ---------------------------------------------------------------------------
# municode_get_code_section
# ---------------------------------------------------------------------------

class TestGetCodeSection:
    """Tests for municode_get_code_section tool."""

    @patch("mcp_servers.municode_server._municode_request", new_callable=AsyncMock)
    async def test_get_code_section_success(self, mock_request):
        """Multi-step flow: client -> products -> content."""
        mock_request.side_effect = [MOCK_CLIENT_INFO, MOCK_PRODUCTS, MOCK_CONTENT]

        result = await municode_get_code_section(
            municipality_name="Norfolk", state_abbr="VA", node_id="1001"
        )

        assert mock_request.call_count == 3
        content_call = mock_request.call_args_list[2]
        assert content_call == call(
            "GET", "/CodesContent",
            params={"jobId": 100, "productId": 200, "nodeId": "1001"},
        )

        assert "Content for node 1001" in result
        assert "GENERAL PROVISIONS" in result

    @patch("mcp_servers.municode_server._municode_request", new_callable=AsyncMock)
    async def test_get_code_section_municipality_not_found(self, mock_request):
        """Error when municipality not found."""
        mock_request.return_value = {"ClientID": None}

        with pytest.raises(RuntimeError, match="not found"):
            await municode_get_code_section(
                municipality_name="Fakeville", state_abbr="VA", node_id="1001"
            )


# ---------------------------------------------------------------------------
# municode_search_codes
# ---------------------------------------------------------------------------

class TestSearchCodes:
    """Tests for municode_search_codes tool."""

    @patch("mcp_servers.municode_server._municode_request", new_callable=AsyncMock)
    async def test_search_codes_success(self, mock_request):
        """Search flow: client lookup -> search."""
        mock_request.side_effect = [MOCK_CLIENT_INFO, MOCK_SEARCH_RESULTS]

        result = await municode_search_codes(
            municipality_name="Norfolk", state_abbr="VA", query="zoning"
        )

        assert mock_request.call_count == 2
        search_call = mock_request.call_args_list[1]
        assert search_call[1]["params"]["clientId"] == 12345
        assert search_call[1]["params"]["searchText"] == "zoning"
        assert search_call[1]["params"]["pageSize"] == 10  # default
        assert search_call[1]["params"]["pageNum"] == 1  # default

        assert "Search results for 'zoning'" in result
        assert "totalCount" in result

    @patch("mcp_servers.municode_server._municode_request", new_callable=AsyncMock)
    async def test_search_codes_custom_pagination(self, mock_request):
        """Custom page_size and page_number are passed through."""
        mock_request.side_effect = [MOCK_CLIENT_INFO, MOCK_SEARCH_RESULTS]

        await municode_search_codes(
            municipality_name="Norfolk",
            state_abbr="VA",
            query="parking",
            page_size=25,
            page_number=3,
            titles_only=True,
        )

        search_call = mock_request.call_args_list[1]
        assert search_call[1]["params"]["pageSize"] == 25
        assert search_call[1]["params"]["pageNum"] == 3
        assert search_call[1]["params"]["titlesOnly"] is True


# ---------------------------------------------------------------------------
# municode_get_url
# ---------------------------------------------------------------------------

class TestGetUrl:
    """Tests for municode_get_url tool."""

    async def test_get_url_formats_correctly(self):
        """URL is built from municipality name and state (no API call)."""
        result = await municode_get_url(municipality_name="Norfolk", state_abbr="VA")

        assert "https://library.municode.com/va/norfolk/codes/code_of_ordinances" in result

    async def test_get_url_handles_spaces(self):
        """Municipality names with spaces are converted to underscores."""
        result = await municode_get_url(
            municipality_name="Virginia Beach", state_abbr="VA"
        )

        assert "virginia_beach" in result

    async def test_get_url_handles_commas(self):
        """Commas are stripped from municipality names."""
        result = await municode_get_url(
            municipality_name="Roanoke, City of", state_abbr="VA"
        )

        assert "roanoke_city_of" in result
        assert "," not in result.split("municode.com/")[1]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    """Tests for general error handling."""

    @patch("mcp_servers.municode_server._municode_request", new_callable=AsyncMock)
    async def test_api_error_raises(self, mock_request):
        """API error is raised as RuntimeError."""
        mock_request.side_effect = RuntimeError("Municode API error 404: Not Found")

        with pytest.raises(RuntimeError, match="404"):
            await municode_get_state_info(state_abbr="VA")

    @patch("mcp_servers.municode_server._municode_request", new_callable=AsyncMock)
    async def test_unexpected_exception_raises(self, mock_request):
        """Non-RuntimeError exceptions propagate."""
        mock_request.side_effect = ConnectionError("DNS resolution failed")

        with pytest.raises(ConnectionError, match="DNS resolution failed"):
            await municode_get_state_info(state_abbr="VA")
