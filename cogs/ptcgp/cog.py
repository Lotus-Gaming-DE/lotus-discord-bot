import asyncio
from discord.ext import commands

from log_setup import get_logger, create_logged_task
from .data import PTCGPData
from .api import fetch_all_cards

logger = get_logger(__name__)


class PTCGPCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.data = PTCGPData("data/ptcgp/cards.db")
        self._lock = asyncio.Lock()

    async def update_database(self) -> dict[str, int]:
        """Lädt Kartendaten neu und speichert sie in der Datenbank."""
        async with self._lock:
            try:
                cards_en = await fetch_all_cards("en")
                cards_de = await fetch_all_cards("de")
            except Exception as e:
                logger.error(
                    f"[PTCGP] Fehler beim Laden der API-Daten: {e}", exc_info=True
                )
                raise RuntimeError("Fehler beim Laden der Kartendaten.") from e
            try:
                await self.data.replace_all(cards_en, cards_de)
            except Exception as e:
                logger.error(
                    f"[PTCGP] Fehler beim Speichern in die DB: {e}", exc_info=True
                )
                raise RuntimeError("Fehler beim Speichern der Daten.") from e
            return {"en": len(cards_en), "de": len(cards_de)}

    async def get_card(self, card_id: str) -> dict:
        """Hole eine Karte mit allen Sprachvarianten."""
        return await self.data.get_card(card_id)

    def cog_unload(self):
        create_logged_task(self.data.close(), logger)
