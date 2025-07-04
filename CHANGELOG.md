# Changelog

## [Unreleased]
- Verbessertes Shutdown-Verhalten: ChampionCog schließt die Datenbank, stoppt alle Tasks und wartet auf deren Abschluss.
- Guidelines-Dokument und CLI-Skript `fetch_wcr.py` hinzugefügt; Coverage-Konfiguration über `.coveragerc`.
- Logging rotiert stündlich und schreibt nach `logs/runtime-<YYYY-MM-DD-HH>.json`.
- Abhängigkeit `idna>=3.7` hinzugefügt, um Snyk-Warnung zu beheben.
- Dependabot führt Updates jetzt täglich aus.
- Dependabot-Pull-Requests lösen den vollständigen CI-Workflow mit Linting,
  Tests und Sicherheitsprüfung aus.
- Champion-Mod-Befehle verlangen nun positive Punktwerte.
- Security-Workflow nutzt jetzt `snyk/actions/python@0.4.0` und prüft, ob `SNYK_TOKEN` gesetzt ist.
- GitHub-Workflows beziehen `RAILWAY_PROJECT` und `RAILWAY_SERVICE` nun über
  Repository-Variablen statt Secrets.
- README beschreibt jetzt die Installation von Dev-Abhängigkeiten und das Starten des Bots per `python -m lotus_bot`.
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
- Neue Datei ``.github/dependabot.yml`` automatisiert Updates der
  Python-Abhängigkeiten und GitHub-Actions.

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
- CI: Snyk-Workflow installiert Abhängigkeiten vor dem Scan.
- Behoben: Formatierungsfehler in ``tests/quiz/test_duel.py``.
- Behoben: Snyk-Workflow nutzt nun ``--file=requirements.txt``.
- Behoben: Snyk-Workflow authentifiziert sich nun explizit.
- Behoben: Snyk-Action nutzt nun Tag 0.4.0 im Security-Workflow.
- Behoben: Manuelle Snyk-Authentifizierung entfernt, Token wird über die Setup-Action gesetzt.
- Behoben: Snyk-Workflow ruft ``snyk auth`` mit dem Token auf.
- Behoben: Entfernt erneut den ``snyk auth``-Schritt, da die Setup-Action den
    Token automatisch verwendet.
- README folgt nun der globalen Struktur und `.env.example` dokumentiert alle
  benötigten Variablen.
- CI: Skip Snyk test in forked PRs to prevent missing-secret auth errors.
