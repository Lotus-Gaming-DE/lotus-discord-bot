import os
import json
import aiosqlite

from log_setup import get_logger

logger = get_logger(__name__)


class PTCGPData:
    """Verwaltet die SQLite-Datenbank für Pokémon TCG Pocket Karten."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db: aiosqlite.Connection | None = None
        self._init_done = False

    async def _get_db(self) -> aiosqlite.Connection:
        if self.db is None:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self.db = await aiosqlite.connect(self.db_path)
            await self.db.execute("PRAGMA journal_mode=WAL")
        return self.db

    async def init_db(self):
        if self._init_done:
            return
        db = await self._get_db()
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS cards (
                id TEXT NOT NULL,
                lang TEXT NOT NULL,
                name TEXT,
                hp TEXT,
                types TEXT,
                image TEXT,
                attacks TEXT,
                rarity TEXT,
                set_name TEXT,
                PRIMARY KEY(id, lang)
            );
            """
        )
        await db.commit()
        self._init_done = True
        logger.info("[PTCGPData] SQLite-Datenbank initialisiert.")

    async def close(self) -> None:
        if self.db is not None:
            await self.db.close()
            self.db = None
            self._init_done = False

    async def replace_all(self, cards_en: list[dict], cards_de: list[dict]):
        """Überschreibt die Datenbank mit den angegebenen Karten."""
        await self.init_db()
        db = await self._get_db()
        await db.execute("DELETE FROM cards")
        for card in cards_en:
            await self._insert_card(db, card, "en")
        for card in cards_de:
            await self._insert_card(db, card, "de")
        await db.commit()

    async def _insert_card(self, db: aiosqlite.Connection, card: dict, lang: str):
        await db.execute(
            """
            INSERT INTO cards(id, lang, name, hp, types, image, attacks, rarity, set_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                card.get("id"),
                lang,
                card.get("name"),
                str(card.get("hp", "")),
                json.dumps(card.get("types", []), ensure_ascii=False),
                card.get("image", ""),
                json.dumps(card.get("attacks", []), ensure_ascii=False),
                card.get("rarity", ""),
                (
                    card.get("set", {}).get("name")
                    if isinstance(card.get("set"), dict)
                    else card.get("set")
                ),
            ),
        )

    async def get_card(self, card_id: str) -> dict:
        """Liefert eine Karte mit allen verfügbaren Sprachen."""
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            "SELECT lang, name, hp, types, image, attacks, rarity, set_name FROM cards WHERE id = ?",
            (card_id,),
        )
        rows = await cur.fetchall()
        result = {}
        for row in rows:
            lang, name, hp, types, image, attacks, rarity, set_name = row
            result[lang] = {
                "id": card_id,
                "name": name,
                "hp": hp,
                "types": json.loads(types) if types else [],
                "image": image,
                "attacks": json.loads(attacks) if attacks else [],
                "rarity": rarity,
                "set": set_name,
            }
        return result

    async def count_cards(self) -> dict[str, int]:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute("SELECT lang, COUNT(*) FROM cards GROUP BY lang")
        rows = await cur.fetchall()
        return {row[0]: row[1] for row in rows}
