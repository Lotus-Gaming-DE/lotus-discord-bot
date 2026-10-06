from __future__ import annotations

import discord
from discord.ext import commands

from lotus_bot.log_setup import get_logger
from lotus_bot.utils.managed_cog import ManagedTaskCog

from .data import CommunityData
from .panel_view import ServerInfoLayoutView

logger = get_logger(__name__)

PANEL_CHANNEL_ID = 1053232522496061471


class CommunityCog(ManagedTaskCog):
    """Verwaltet das serverweite Info-Panel im infos-und-regeln Channel."""

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot
        self.data = CommunityData("data/pers/community/community.db")
        self.create_task(self._startup())

    async def _startup(self) -> None:
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(PANEL_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            logger.warning(
                "[CommunityCog] Panel-Channel %s nicht gefunden.", PANEL_CHANNEL_ID
            )
            return
        await self._remove_misplaced_forever_panel(channel)
        try:
            await self.publish_panel(channel)
        except Exception as exc:
            logger.error(
                "[CommunityCog] Auto-Publish fehlgeschlagen: %s", exc, exc_info=True
            )

    async def publish_panel(self, channel: discord.TextChannel) -> None:
        """Postet oder editiert das Info-Panel im angegebenen Channel."""
        view = ServerInfoLayoutView(self.bot.data.get("emojis", {}))
        message_id_value = await self.data.get_setting("panel_message_id")
        if message_id_value:
            try:
                message = await channel.fetch_message(int(message_id_value))
                await message.edit(content=None, view=view)
                logger.info(
                    "[CommunityCog] Panel aktualisiert (Message %s).", message.id
                )
                return
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                logger.info(
                    "[CommunityCog] Bestehende Panel-Message nicht editierbar, erstelle neu."
                )

        message = await channel.send(view=view)
        await self.data.set_setting("panel_message_id", str(message.id))
        logger.info("[CommunityCog] Panel erstellt (Message %s).", message.id)

    async def _remove_misplaced_forever_panel(
        self, channel: discord.TextChannel
    ) -> None:
        """Einmalig: löscht das versehentlich hier gepostete Forever-Rollenpanel.

        Die Forever-Auswahl lebt jetzt im WoW-Hub (wow-info). Kann nach dem
        nächsten Deploy samt Setting ``forever_panel_message_id`` entfernt werden.
        """
        key = "forever_panel_message_id"
        message_id_value = await self.data.get_setting(key)
        if not message_id_value:
            return
        try:
            message = await channel.fetch_message(int(message_id_value))
            await message.delete()
            logger.info("[CommunityCog] Altes Forever-Panel gelöscht.")
        except discord.NotFound:
            pass
        except (discord.Forbidden, discord.HTTPException) as exc:
            logger.warning("[CommunityCog] Altes Forever-Panel nicht löschbar: %s", exc)
            return
        await self.data.set_setting(key, "")

    def cog_unload(self) -> None:
        super().cog_unload()
