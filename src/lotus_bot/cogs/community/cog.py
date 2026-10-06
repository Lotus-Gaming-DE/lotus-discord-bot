from __future__ import annotations

import discord
from discord.ext import commands

from lotus_bot.log_setup import get_logger
from lotus_bot.utils.managed_cog import ManagedTaskCog

from .data import CommunityData
from .forever_view import ForeverRolesLayoutView
from .panel_view import ServerInfoLayoutView

logger = get_logger(__name__)

PANEL_CHANNEL_ID = 1053232522496061471


class CommunityCog(ManagedTaskCog):
    """Verwaltet das serverweite Info-Panel im infos-und-regeln Channel."""

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot
        self.data = CommunityData("data/pers/community/community.db")
        # Persistente Buttons müssen nach einem Neustart wieder registriert sein.
        bot.add_view(ForeverRolesLayoutView(bot.data.get("emojis", {})))
        self.create_task(self._startup())

    async def _startup(self) -> None:
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(PANEL_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            logger.warning(
                "[CommunityCog] Panel-Channel %s nicht gefunden.", PANEL_CHANNEL_ID
            )
            return
        try:
            await self.publish_panel(channel)
        except Exception as exc:
            logger.error(
                "[CommunityCog] Auto-Publish fehlgeschlagen: %s", exc, exc_info=True
            )
        try:
            await self.publish_forever_panel(channel)
        except Exception as exc:
            logger.error(
                "[CommunityCog] Forever-Panel fehlgeschlagen: %s", exc, exc_info=True
            )

    async def publish_panel(self, channel: discord.TextChannel) -> None:
        """Postet oder editiert das Info-Panel im angegebenen Channel."""
        view = ServerInfoLayoutView(self.bot.data.get("emojis", {}))
        await self._publish(channel, "panel_message_id", view)

    async def publish_forever_panel(self, channel: discord.TextChannel) -> None:
        """Postet oder editiert das WoW-Forever-Rollenpanel (zweite Nachricht)."""
        view = ForeverRolesLayoutView(self.bot.data.get("emojis", {}))
        await self._publish(channel, "forever_panel_message_id", view)

    async def _publish(
        self,
        channel: discord.TextChannel,
        setting_key: str,
        view: discord.ui.LayoutView,
    ) -> None:
        message_id_value = await self.data.get_setting(setting_key)
        if message_id_value:
            try:
                message = await channel.fetch_message(int(message_id_value))
                await message.edit(content=None, view=view)
                logger.info(
                    "[CommunityCog] %s aktualisiert (Message %s).",
                    setting_key,
                    message.id,
                )
                return
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                logger.info(
                    "[CommunityCog] %s nicht editierbar, erstelle neu.", setting_key
                )

        # Rollen-Erwähnungen im Panel dürfen niemanden anpingen.
        message = await channel.send(
            view=view, allowed_mentions=discord.AllowedMentions.none()
        )
        await self.data.set_setting(setting_key, str(message.id))
        logger.info("[CommunityCog] %s erstellt (Message %s).", setting_key, message.id)

    def cog_unload(self) -> None:
        super().cog_unload()
