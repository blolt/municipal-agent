#!/usr/bin/env python3
"""Municode MCP server — exposes Municode REST API as MCP tools.

Uses the official FastMCP SDK for standard MCP protocol handling
(initialize handshake, tool schema generation, JSON-RPC transport).

Tools:
    municode_get_state_info        — Get state info by abbreviation
    municode_list_municipalities   — List all municipalities in a state
    municode_get_municipality_info — Get municipality details and products
    municode_get_code_structure    — Get table of contents / code structure
    municode_get_code_section      — Get full text of a code section
    municode_search_codes          — Search municipal codes
    municode_get_url               — Get direct URL to municipality's Municode page

Based on the unofficial Municode API:
https://sr.ht/~partytax/unofficial-municode-api-documentation/

API logic adapted from Skatterbrainz/MunicipalMCP (MIT License).
"""

import json

import httpx
from mcp.server.fastmcp import FastMCP

MUNICODE_API_BASE = "https://api.municode.com"
MUNICODE_LIBRARY_BASE = "https://library.municode.com"

mcp = FastMCP("municode")


# ---------------------------------------------------------------------------
# Municode API helpers
# ---------------------------------------------------------------------------

async def _municode_request(method: str, path: str, params: dict | None = None) -> dict | list:
    """Make an async request to the Municode REST API.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: API path (e.g. /States/abbr)
        params: Optional query parameters

    Returns:
        Parsed JSON response

    Raises:
        RuntimeError: If the request fails
    """
    url = f"{MUNICODE_API_BASE}{path}"
    async with httpx.AsyncClient(timeout=30.0, headers={"Accept": "application/json"}) as client:
        response = await client.request(method, url, params=params)

    if response.status_code >= 400:
        raise RuntimeError(
            f"Municode API error {response.status_code}: {response.text}"
        )
    return response.json()


async def _get_client_by_name(municipality_name: str, state_abbr: str) -> dict:
    """Look up a municipality (client) by name and state.

    Returns the client dict. Raises RuntimeError if not found.
    """
    result = await _municode_request(
        "GET", "/Clients/name",
        params={"clientName": municipality_name, "stateAbbr": state_abbr.upper()},
    )
    if not result or not result.get("ClientID"):
        raise RuntimeError(
            f"Municipality '{municipality_name}' not found in {state_abbr.upper()}"
        )
    return result


async def _get_code_product(client_id: int) -> dict:
    """Find the 'code of ordinances' product for a client.

    Returns dict with 'Id' (job_id) and 'ProductID' keys.
    Raises RuntimeError if no code product found.
    """
    products = await _municode_request("GET", f"/ClientContent/{client_id}")
    for product in products:
        if "code" in product.get("ProductName", "").lower():
            return product
    raise RuntimeError("No code of ordinances found for this municipality")


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def municode_get_state_info(state_abbr: str) -> str:
    """Get information about a US state by its abbreviation.

    Args:
        state_abbr: Two-character US state abbreviation (e.g., 'VA', 'TX', 'CA')
    """
    result = await _municode_request(
        "GET", "/States/abbr",
        params={"stateAbbr": state_abbr.upper()},
    )
    return json.dumps(result, indent=2)


@mcp.tool()
async def municode_list_municipalities(state_abbr: str) -> str:
    """List all municipalities in a state that use Municode.

    Args:
        state_abbr: Two-character US state abbreviation (e.g., 'VA', 'TX', 'CA')
    """
    state_abbr = state_abbr.upper()
    clients = await _municode_request(
        "GET", "/Clients/stateAbbr",
        params={"stateAbbr": state_abbr},
    )
    formatted = [
        {
            "name": c.get("ClientName", "Unknown"),
            "id": c.get("ClientID"),
            "city": c.get("City"),
            "zip_code": c.get("ZipCode"),
            "website": c.get("Website"),
        }
        for c in clients
    ]
    return (
        f"Found {len(formatted)} municipalities in {state_abbr}:\n\n"
        + json.dumps(formatted, indent=2)
    )


@mcp.tool()
async def municode_get_municipality_info(municipality_name: str, state_abbr: str) -> str:
    """Get detailed information about a specific municipality including available products.

    Args:
        municipality_name: Name of the city, county, or municipality
        state_abbr: Two-character US state abbreviation
    """
    state_abbr = state_abbr.upper()
    client_info = await _get_client_by_name(municipality_name, state_abbr)
    client_id = client_info["ClientID"]
    client_content = await _municode_request("GET", f"/ClientContent/{client_id}")
    result = {
        "client_info": client_info,
        "available_products": client_content,
    }
    return json.dumps(result, indent=2)


@mcp.tool()
async def municode_get_code_structure(
    municipality_name: str, state_abbr: str, node_id: str = "10121"
) -> str:
    """Get the table of contents structure for a municipality's code of ordinances.

    Args:
        municipality_name: Name of the city, county, or municipality
        state_abbr: Two-character US state abbreviation
        node_id: Optional specific node ID to get children for (defaults to root)
    """
    state_abbr = state_abbr.upper()
    client_info = await _get_client_by_name(municipality_name, state_abbr)
    code_product = await _get_code_product(client_info["ClientID"])

    job_id = code_product["Id"]
    product_id = code_product["ProductID"]

    toc = await _municode_request(
        "GET", "/codesToc/children",
        params={"jobId": job_id, "productId": product_id, "nodeId": node_id},
    )
    return (
        f"Code structure for {municipality_name}, {state_abbr}:\n\n"
        + json.dumps(toc, indent=2)
    )


@mcp.tool()
async def municode_get_code_section(
    municipality_name: str, state_abbr: str, node_id: str
) -> str:
    """Get the full text content of a specific section of municipal code.

    Args:
        municipality_name: Name of the city, county, or municipality
        state_abbr: Two-character US state abbreviation
        node_id: Node ID of the specific code section to retrieve
    """
    state_abbr = state_abbr.upper()
    client_info = await _get_client_by_name(municipality_name, state_abbr)
    code_product = await _get_code_product(client_info["ClientID"])

    job_id = code_product["Id"]
    product_id = code_product["ProductID"]

    content = await _municode_request(
        "GET", "/CodesContent",
        params={"jobId": job_id, "productId": product_id, "nodeId": node_id},
    )
    return (
        f"Content for node {node_id} in {municipality_name}, {state_abbr}:\n\n"
        + json.dumps(content, indent=2)
    )


@mcp.tool()
async def municode_search_codes(
    municipality_name: str,
    state_abbr: str,
    query: str,
    page_size: int = 10,
    page_number: int = 1,
    titles_only: bool = False,
) -> str:
    """Search through municipal codes and ordinances for a specific query.

    Args:
        municipality_name: Name of the city, county, or municipality
        state_abbr: Two-character US state abbreviation
        query: Text to search for in the municipal codes
        page_size: Number of results per page (default: 10)
        page_number: Page number to retrieve (default: 1)
        titles_only: Search only in titles (default: false)
    """
    state_abbr = state_abbr.upper()
    client_info = await _get_client_by_name(municipality_name, state_abbr)
    client_id = client_info["ClientID"]

    search_results = await _municode_request(
        "GET", "/search",
        params={
            "clientId": client_id,
            "searchText": query,
            "pageNum": page_number,
            "pageSize": page_size,
            "titlesOnly": titles_only,
            "isAdvanced": False,
            "isAutocomplete": False,
            "mode": "standard",
            "sort": 0,
            "fragmentSize": 200,
            "contentTypeId": "",
            "stateId": 0,
        },
    )
    return (
        f"Search results for '{query}' in {municipality_name}, {state_abbr}:\n\n"
        + json.dumps(search_results, indent=2)
    )


@mcp.tool()
async def municode_get_url(municipality_name: str, state_abbr: str) -> str:
    """Get the direct URL to a municipality's Municode library page.

    Args:
        municipality_name: Name of the city, county, or municipality
        state_abbr: Two-character US state abbreviation
    """
    state_lower = state_abbr.lower()
    formatted_name = municipality_name.lower().replace(" ", "_").replace(",", "")
    url = f"{MUNICODE_LIBRARY_BASE}/{state_lower}/{formatted_name}/codes/code_of_ordinances"
    return f"Municode Library URL for {municipality_name}, {state_abbr.upper()}:\n{url}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
