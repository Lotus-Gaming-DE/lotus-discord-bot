# Entwickler-Richtlinien

- Verwende ausschließlich **guild-basierte Slash-Befehle**. Registriere Befehlsgruppen immer mit `bot.tree.add_command(..., guild=bot.main_guild)` und synchronisiere sie mit `await bot.tree.sync(guild=bot.main_guild)`.
- Registriere keine globalen Slash-Befehle. Entferne alte globale Befehle mit `self.tree.clear_commands(guild=None)`.
- Der Bot läuft ausschließlich auf einem **deutschsprachigen Discord-Server**. Alle für Nutzer sichtbaren Texte und Dokumentation sind grundsätzlich auf Deutsch zu verfassen. Unterstützung für weitere Sprachen ist optional und muss explizit genehmigt werden.
- Der Bot wird auf **Railway** gehostet. Umgebungsvariablen wie `bot_key` und `server_id` werden dort bereitgestellt.
- Persistente Daten liegen in `data/pers/` und dürfen nicht committet werden.
- Wenn neue Umgebungsvariablen benötigt werden, passe `.env.example` entsprechend an und dokumentiere sie.
- Bei Änderungen oder neuen Features aktualisiere die Tests und halte die `README.md` aktuell.

## Tests & CI

- Im CI-Workflow (`.github/workflows/tests.yml`) werden automatisch `black .` (Formatierung), `flake8` (Linting) und `pytest` (Tests) bei jedem Push und Pull Request ausgeführt.
- Unittests laufen lokal ohne Railway-Umgebungsvariablen. Simuliere diese mit `monkeypatch.setenv`, wie in `tests/conftest.py` gezeigt.
- Nutze das Fixture `patch_logged_task`, um für Tests `create_logged_task` zu ersetzen, statt eigene Patch-Logik zu duplizieren.
- Implementiere `cog_unload()` in jedem Cog, das Hintergrund-Tasks oder Loops startet. Alle gestarteten Tasks müssen dort erfasst und wieder gestoppt werden.
- Tests müssen `cog.cog_unload()` (oder alternativ den Bot) aufrufen, um alle Tasks zu beenden und die Event-Loop sauber zu schließen.

## Codex-Workflow für Python

- **Einrückung:** Verwende ausschließlich **4 Leerzeichen** pro Einrückungsebene. Niemals Tabs oder gemischte Einrückung!
- **Zeilenenden:** Speichere alle Dateien mit **LF (`\n`)**-Zeilenende, niemals CRLF.
- **Unsichtbare Zeichen:** Entferne vor jedem Commit unsichtbare oder nicht-standardisierte Zeichen (z. B. Non-breaking Spaces).
- **Formatierung:** Führe nach jeder Änderung `black .` aus, um alle Python-Dateien automatisch zu formatieren.
- **Syntax & Linting:**
  - Prüfe alle Python-Dateien mit `python -m py_compile <file>`.
  - Lint den gesamten Code mit `flake8 .` und führe Tests mit `pytest` aus, bevor du committest oder einen PR erstellst.
- **Fehlerbehandlung:**
  - Wenn `flake8` einen Fehler wie `E999` (z. B. `IndentationError: unexpected indent`) meldet, prüfe die betroffene Datei auf gemischte Einrückung, unsichtbare Zeichen oder fehlerhafte Zeilenenden.
  - Führe anschließend erneut `black .` und `flake8 .` aus, bis alle Fehler behoben und alle Prüfungen bestanden sind.
- **CI-Priorität:** Alle Formatierungs- und Linting-Schritte werden zusätzlich automatisch im CI ausgeführt. Lokale Prüfung wird dringend empfohlen, ist aber nicht zwingend, solange der CI-Workflow durchläuft.
