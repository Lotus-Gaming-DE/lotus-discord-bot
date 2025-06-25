import aiohttp
import os

from lotus_bot.log_setup import get_logger

logger = get_logger(__name__)


async def fetch_all_cards(language: str) -> list[dict]:
    """Lade alle Karten für die angegebene Sprache über die REST-API."""
    cards: list[dict] = []
    ssl_disabled = os.getenv("PTCGP_SKIP_SSL_VERIFY") == "1"
    async with aiohttp.ClientSession() as session:
        page = 1
        while True:
            url = f"https://api.tcgdex.dev/v2/tcg-pocket/{language}/cards?page={page}"
            async with session.get(url, ssl=False if ssl_disabled else None) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status} beim Laden von {url}")
                data = await resp.json()
                if isinstance(data, dict) and "data" in data:
                    items = data.get("data")
                else:
                    items = data
                if not items:
                    break
                cards.extend(items)
                page += 1
    logger.info(f"[PTCGP API] Geladene Karten {language}: {len(cards)}")
    return cards
