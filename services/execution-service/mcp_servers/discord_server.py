#!/usr/bin/env python3
"""Discord MCP server — exposes Discord REST API actions as MCP tools.

Uses the official FastMCP SDK for standard MCP protocol handling
(initialize handshake, tool schema generation, JSON-RPC transport).
Communicates with the Discord REST API via httpx — no WebSocket gateway.

Tools:
    discord_send_message  — Send a message to a channel
    discord_edit_message  — Edit an existing message
    discord_add_reaction  — Add a reaction to a message

Requires DISCORD_BOT_TOKEN in the environment (inherited from the
Execution Service via SubprocessRuntime).
"""

import json
import os
import urllib.parse

import httpx
from mcp.server.fastmcp import FastMCP

DISCORD_API = "https://discord.com/api/v10"
BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")

mcp = FastMCP("discord")


def _headers() -> dict[str, str]:
    """Build Discord API request headers."""
    return {
        "Authorization": f"Bot {BOT_TOKEN}",
        "Content-Type": "application/json",
    }


async def _discord_request(method: str, path: str, json_body: dict | None = None) -> dict:
    """Make an async request to the Discord REST API.

    Args:
        method: HTTP method (GET, POST, PATCH, PUT, DELETE)
        path: API path (e.g. /channels/{id}/messages)
        json_body: Optional JSON body for POST/PATCH/PUT

    Returns:
        Response JSON (or empty dict for 204 No Content)

    Raises:
        RuntimeError: If the request fails
    """
    if not BOT_TOKEN:
        raise RuntimeError("DISCORD_BOT_TOKEN is not set")

    url = f"{DISCORD_API}{path}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.request(method, url, headers=_headers(), json=json_body)

    if response.status_code == 204:
        return {}
    if response.status_code >= 400:
        raise RuntimeError(
            f"Discord API error {response.status_code}: {response.text}"
        )
    return response.json()


@mcp.tool()
async def discord_send_message(channel_id: str, content: str) -> str:
    """Send a message to a Discord channel. Returns the created message object including its ID.

    Args:
        channel_id: The Discord channel ID to send the message to
        content: The message text content (up to 2000 characters)
    """
    result = await _discord_request(
        "POST",
        f"/channels/{channel_id}/messages",
        {"content": content},
    )
    return json.dumps({"message_id": result.get("id"), "channel_id": channel_id})


@mcp.tool()
async def discord_edit_message(channel_id: str, message_id: str, content: str) -> str:
    """Edit an existing Discord message. The bot can only edit its own messages.

    Args:
        channel_id: The Discord channel ID containing the message
        message_id: The ID of the message to edit
        content: The new message text content (up to 2000 characters)
    """
    await _discord_request(
        "PATCH",
        f"/channels/{channel_id}/messages/{message_id}",
        {"content": content},
    )
    return "Message edited successfully"


@mcp.tool()
async def discord_add_reaction(channel_id: str, message_id: str, emoji: str) -> str:
    """Add an emoji reaction to a Discord message.

    Args:
        channel_id: The Discord channel ID containing the message
        message_id: The ID of the message to react to
        emoji: The emoji to add (Unicode emoji or custom format 'name:id')
    """
    emoji_encoded = urllib.parse.quote(emoji)
    await _discord_request(
        "PUT",
        f"/channels/{channel_id}/messages/{message_id}/reactions/{emoji_encoded}/@me",
    )
    return "Reaction added successfully"


if __name__ == "__main__":
    mcp.run(transport="stdio")
