import asyncio
from discord.ext import commands

from lotusbot.log_setup import get_logger
from lotusbot.utils.managed_cog import ManagedTaskCog
from .data import PTCGPData
from .api import fetch_all_cards

logger = get_logger(__name__)


class PTCGPCog(ManagedTaskCog):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot
        self.data = PTCGPData("data/pers/ptcgp/cards.db")
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

    async def cog_unload(self) -> None:
        await self.data.close()
        super().cog_unload()
        await self.wait_closed()
