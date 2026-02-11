"""Discord Gateway handler for receiving bot messages.

Uses discord.py to maintain a persistent WebSocket connection to Discord,
receiving all messages and forwarding them to the Orchestrator Service.

Response delivery is handled by the Orchestrator via Discord MCP tools —
this handler is a thin inbound-only listener.
"""

import asyncio

import discord

from src.core.logging import get_logger
from src.events import EventSource, InternalEvent, RoutingContext
from src.core.gateway_client import GatewayClient

logger = get_logger(__name__)


class DiscordGatewayHandler(discord.Client):
    """Discord Gateway client that normalizes events and forwards to Orchestrator.

    This client maintains a persistent WebSocket connection to Discord
    and receives real-time events (messages, reactions, etc.).
    Response delivery is handled by the Orchestrator via Discord MCP tools.
    """

    def __init__(
        self,
        gateway_client: GatewayClient,
        **kwargs,
    ):
        """Initialize the Discord Gateway handler.

        Args:
            gateway_client: Client for sending events to Orchestrator Service
            **kwargs: Additional arguments passed to discord.Client
        """
        # Configure intents - what events we want to receive
        intents = discord.Intents.default()
        intents.message_content = True  # Required to read message text
        intents.guild_messages = True  # Messages in servers
        intents.dm_messages = True  # Direct messages to bot

        super().__init__(intents=intents, **kwargs)

        self.gateway_client = gateway_client

    async def on_ready(self) -> None:
        """Called when the bot has connected to Discord."""
        logger.info(
            "Discord bot connected",
            user=str(self.user),
            user_id=str(self.user.id) if self.user else None,
            guild_count=len(self.guilds),
        )

        # Log connected guilds
        for guild in self.guilds:
            logger.info(
                "Connected to guild",
                guild_name=guild.name,
                guild_id=str(guild.id),
                member_count=guild.member_count,
            )

    async def on_message(self, message: discord.Message) -> None:
        """Handle incoming messages.

        Normalizes to InternalEvent and fires-and-forgets to the Orchestrator.
        Response delivery is handled by the Orchestrator via Discord MCP tools.

        Args:
            message: Discord message object
        """
        # Ignore messages from bots (including ourselves)
        if message.author.bot:
            return

        logger.debug(
            "Received message",
            message_id=str(message.id),
            channel_id=str(message.channel.id),
            author=str(message.author),
            content_preview=message.content[:50] if message.content else "",
        )

        try:
            # Normalize to InternalEvent
            event = self._normalize_message(message)

            # Fire-and-forget to Orchestrator — response delivery is via MCP tools
            asyncio.create_task(
                self._forward_event(event),
                name=f"forward-{event.correlation_id}",
            )

        except Exception as e:
            logger.error(
                "Failed to process Discord message",
                message_id=str(message.id),
                error=str(e),
                exc_info=True,
            )

    async def _forward_event(self, event: InternalEvent) -> None:
        """Forward an event to the Orchestrator (background task).

        Args:
            event: The normalized InternalEvent to forward
        """
        try:
            await self.gateway_client.send_event(event)
            logger.info(
                "Event forwarded to Orchestrator",
                correlation_id=event.correlation_id,
            )
        except Exception as e:
            logger.error(
                "Failed to forward event to Orchestrator",
                correlation_id=event.correlation_id,
                error=str(e),
                exc_info=True,
            )

    async def on_message_edit(
        self, before: discord.Message, after: discord.Message
    ) -> None:
        """Handle message edits.

        Args:
            before: Message before edit
            after: Message after edit
        """
        # Ignore bot edits
        if after.author.bot:
            return

        # Only process if content actually changed
        if before.content == after.content:
            return

        logger.debug(
            "Received message edit",
            message_id=str(after.id),
            channel_id=str(after.channel.id),
        )

        # Could publish as a special "edit" event type
        # For now, we'll skip edits in MVP

    async def on_reaction_add(
        self, reaction: discord.Reaction, user: discord.User | discord.Member
    ) -> None:
        """Handle reaction additions.

        Args:
            reaction: The reaction that was added
            user: The user who added the reaction
        """
        # Ignore bot reactions
        if user.bot:
            return

        logger.debug(
            "Received reaction",
            message_id=str(reaction.message.id),
            emoji=str(reaction.emoji),
            user=str(user),
        )

        # Could publish reactions as events
        # For now, we'll skip reactions in MVP

    def _normalize_message(self, message: discord.Message) -> InternalEvent:
        """Normalize a Discord message to InternalEvent.

        Args:
            message: Discord message object

        Returns:
            Normalized InternalEvent
        """
        # Build routing context
        routing = RoutingContext(
            reply_channel_id=str(message.channel.id),
            reply_thread_id=(
                str(message.thread.id) if hasattr(message, "thread") and message.thread else None
            ),
            reply_metadata={
                "guild_id": str(message.guild.id) if message.guild else None,
                "message_id": str(message.id),
            },
        )

        # Extract attachments
        attachments = [
            {
                "id": str(a.id),
                "filename": a.filename,
                "url": a.url,
                "content_type": a.content_type,
                "size": a.size,
            }
            for a in message.attachments
        ]

        # Build metadata — include source for Orchestrator fallback detection
        metadata = {
            "source": "discord",
            "guild_id": str(message.guild.id) if message.guild else None,
            "guild_name": message.guild.name if message.guild else None,
            "channel_name": getattr(message.channel, "name", "DM"),
            "is_dm": isinstance(message.channel, discord.DMChannel),
            "mentions": [str(u.id) for u in message.mentions],
            "reference": (
                str(message.reference.message_id) if message.reference else None
            ),
        }

        return InternalEvent(
            source=EventSource.DISCORD,
            source_event_id=str(message.id),
            source_channel_id=str(message.channel.id),
            source_user_id=str(message.author.id),
            source_user_name=message.author.display_name,
            content=message.content,
            attachments=attachments,
            routing=routing,
            metadata=metadata,
            raw_payload=None,  # Don't store raw payload to save space
        )


def create_discord_handler(
    bot_token: str,
    gateway_client: GatewayClient,
) -> DiscordGatewayHandler:
    """Factory function to create a Discord Gateway handler.

    Args:
        bot_token: Discord bot token
        gateway_client: Gateway client instance

    Returns:
        Configured DiscordGatewayHandler
    """
    handler = DiscordGatewayHandler(
        gateway_client=gateway_client,
    )
    return handler


async def run_discord_bot(
    bot_token: str,
    gateway_client: GatewayClient,
) -> None:
    """Run the Discord bot.

    Args:
        bot_token: Discord bot token
        gateway_client: Gateway client instance
    """
    handler = create_discord_handler(
        bot_token=bot_token,
        gateway_client=gateway_client,
    )

    logger.info("Starting Discord bot...")
    await handler.start(bot_token)
