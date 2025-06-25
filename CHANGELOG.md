# Changelog

## [Unreleased]
- Verbessertes Shutdown-Verhalten: ChampionCog schließt die Datenbank, stoppt alle Tasks und wartet auf deren Abschluss.
- Champion-Mod-Befehle verlangen nun positive Punktwerte.
- WCR-Cog aufgeteilt: Namensauflösung und Embed-Aufbau sind nun in eigenen Modulen. Fehlerbehandlung und Tests wurden erweitert.
- ChampionCog.update_user_score loggt jetzt Datenbankfehler und wirft einen
  ``RuntimeError`` bei Fehlschlagen des Datenbankzugriffs.
- Neues JSON-Cache-System für WCR-Daten (``WCR_CACHE_TTL`` konfiguriert die
  Gültigkeitsdauer).
- Refaktor: `cmd_duel` nutzt nun `_compute_duel_outcome` und die neue
- ChampionData.add_delta begrenzt Punktestände auf mindestens 0 und protokolliert Vorher- und Nachher-Wert.
- WCRCog fällt nun auf englische Texte zurück, wenn ``locals`` fehlen.
- Abhängigkeiten aktualisiert: ``discord.py`` 2.5.2, ``Unidecode`` 1.4.0,
  ``aiosqlite`` 0.21.0, ``python-dotenv`` 1.1.1, ``pytest-asyncio`` 1.0.0 und
  ``aiohttp`` 3.12.13.
 - ChampionCog besitzt nun eine begrenzte Update-Warteschlange (1000 Einträge);
    beim Füllen wird nun ein ``RuntimeError`` ausgelöst.

- Bereinigt: `cogs/champion/__init__.py` verwendet nun `commands.Bot` und entfernt den Import von `discord`.
- Dokumentation erweitert: Beispiele für `/wcr`-Befehle und Hinweise zum neuen WCR-Cache.
- ``create_logged_task`` ignoriert nun ``asyncio.CancelledError``.
- ``QuizCog.cog_unload`` löscht das Attribut ``quiz_cog`` am Bot.
- Tests verwenden ein sessionweites ``event_loop``-Fixture.
- Neue Tests für ``QuestionManager.ask_question`` und ``QuestionRestorer.repost_question``.
- Logging nutzt jetzt ``structlog`` und schreibt JSON-Dateien unter ``logs/bot.json``.
- Pre-commit Hooks mit ``black``, ``flake8``, ``ruff`` und mehr.
- Neue GitHub-Action ``security.yml`` führt ``pip-audit`` aus.
- Projektstruktur auf ``src``-Layout umgestellt; Imports und Tests angepasst.
- Neues ``requirements-dev.txt`` und ``pip-audit`` in Pre-commit.
- CI speichert Railway-Logs und führt einen Snyk-Scan aus.
- Behoben: Formatierungsfehler in ``tests/quiz/test_duel.py``.
- Behoben: Snyk-Workflow nutzt nun ``--file=requirements.txt``.
- Behoben: Snyk-Workflow authentifiziert sich nun explizit.
- Behoben: Snyk-Action nutzt nun Tag 0.4.0 im Security-Workflow.
