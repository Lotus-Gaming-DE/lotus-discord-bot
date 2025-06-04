# cogs/quiz/message_tracker.py

import discord
import time

from log_setup import get_logger, create_logged_task

logger = get_logger(__name__)


class MessageTracker:
    def __init__(self, bot, on_threshold) -> None:
        """Track message activity in quiz channels."""
        self.bot = bot
        self.on_threshold = on_threshold
        self.message_counter: dict[int, int] = {}
        self.channel_initialized: dict[int, bool] = {}

    async def initialize(self) -> None:
        """Warm up counters based on recent channel history."""
        logger.info("[Tracker] Initialisierung gestartet.")
        await self.bot.wait_until_ready()

        for area, cfg in self.bot.quiz_data.items():
            channel_id = cfg.channel_id
            try:
                start = time.time()
                channel = await self.bot.fetch_channel(channel_id)
                if not isinstance(channel, discord.TextChannel):
                    logger.warning(
                        f"[Tracker] Channel {channel_id} ist kein TextChannel.")
                    continue

                messages = [msg async for msg in channel.history(limit=20)]
                quiz_index = next((i for i, msg in enumerate(messages)
                                   if msg.author.id == self.bot.user.id and msg.embeds and
                                   msg.embeds[0].title.startswith(f"Quiz für {area.upper()}")), None)

                threshold = cfg.activity_threshold
                if quiz_index is not None:
                    count = len([
                        m for m in messages[:quiz_index] if not m.author.bot
                    ])
                    self.message_counter[channel.id] = count
                else:
                    self.message_counter[channel.id] = threshold

                self.channel_initialized[channel.id] = True
                logger.info(
                    f"[Tracker] Initialisiert: '{area}' (Channel {channel.id}) – Zähler: {self.message_counter[channel.id]} ({round(time.time()-start, 2)}s)")

            except Exception as e:
                logger.error(
                    f"[Tracker] Fehler bei Initialisierung von '{area}' (Channel-ID {channel_id}): {e}", exc_info=True)

    def register_message(self, message: discord.Message) -> str | None:
        """Count a message and trigger a question if threshold is reached."""
        if message.author.bot:
            return None

        cid = message.channel.id
        before = self.message_counter.get(cid, 0)
        self.message_counter[cid] = after = before + 1

        area = self._find_area_for_channel(cid)
        if area:
            logger.info(
                f"[Tracker] Nachrichtenzähler für '{area}' (Channel {cid}): {before} → {after}"
            )

        if cid in self.bot.quiz_cog.awaiting_activity:
            cfg_obj = self.bot.quiz_data.get(area) if area else None
            threshold = cfg_obj.activity_threshold if cfg_obj else 10
            if after >= threshold:
                if area is None:
                    area, _ = self.bot.quiz_cog.awaiting_activity[cid]
                logger.info(
                    f"[Tracker] Aktivität erreicht in '{area}' ({after}/{threshold}) – Frage wird gestellt."
                )
                create_logged_task(
                    self.on_threshold(
                        area, self.bot.quiz_cog.awaiting_activity[cid][1]
                    ),
                    logger
                )

        return area

    def _find_area_for_channel(self, channel_id: int) -> str | None:
        """Return the quiz area configured for a Discord channel."""
        for area, cfg in self.bot.quiz_data.items():
            if cfg.channel_id == channel_id:
                return area
        return None

    def get(self, channel_id: int) -> int:
        """Return the current counter value for a channel."""
        return self.message_counter.get(channel_id, 0)

    def is_initialized(self, channel_id: int) -> bool:
        """Check whether a channel has been initialized."""
        return self.channel_initialized.get(channel_id, False)

    def set_initialized(self, channel_id: int) -> None:
        """Mark a channel as initialized."""
        self.channel_initialized[channel_id] = True

    def reset(self, channel_id: int) -> None:
        """Reset the counter for a channel."""
        self.message_counter[channel_id] = 0
