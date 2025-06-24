# Changelog

## [Unreleased]
- Verbessertes Shutdown-Verhalten: ChampionCog schließt jetzt zuerst die Datenbank und stoppt danach alle Tasks.
- ChampionCog.update_user_score loggt jetzt Datenbankfehler und wirft einen
  ``RuntimeError`` bei Fehlschlagen des Datenbankzugriffs.
- Neues JSON-Cache-System für WCR-Daten (``WCR_CACHE_TTL`` konfiguriert die
  Gültigkeitsdauer).
- Refaktor: `cmd_duel` nutzt nun `_compute_duel_outcome` und die neue
  `DuelOutcome`-Dataclass.
- ChampionData.add_delta begrenzt Punktestände auf mindestens 0 und protokolliert Vorher- und Nachher-Wert.
- WCRCog fällt nun auf englische Texte zurück, wenn ``locals`` fehlen.
- Abhängigkeiten aktualisiert: ``discord.py`` 2.5.2, ``Unidecode`` 1.4.0,
  ``aiosqlite`` 0.21.0, ``python-dotenv`` 1.1.1, ``pytest-asyncio`` 1.0.0 und
  ``aiohttp`` 3.12.13.
- Refaktor: `cmd_duel` nutzt nun `_compute_duel_outcome` und die neue `DuelOutcome`-Dataclass.
 - ChampionCog besitzt nun eine begrenzte Update-Warteschlange (1000 Einträge);
    beim Füllen wird nun ein ``RuntimeError`` ausgelöst.

- Bereinigt: `cogs/champion/__init__.py` verwendet nun `commands.Bot` und entfernt den Import von `discord`.
- Dokumentation erweitert: Beispiele für `/wcr`-Befehle und Hinweise zum neuen WCR-Cache.
