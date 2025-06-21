![Lotus Gaming Logo](./data/LotusGamingColorless.png)

# Lotus Gaming Discord Bot

Der **Lotus Gaming Bot** bringt interaktive Quiz-Events, ein Punktesystem mit automatischen Rollen und hilfreiche Warcraft‑Rumble Abfragen auf deinen Discord-Server. Alle Funktionen stehen ausschließlich als Slash‑Commands zur Verfügung und können pro Channel flexibel aktiviert werden.

## Zielgruppen

- **Mitglieder** – spielen und Punkte sammeln
- **Moderatoren** – Channel konfigurieren, Quiz verwalten
- **Entwickler** – neue Features beisteuern oder anpassen

## Inhaltsverzeichnis

1. [Schnellstart](#schnellstart)
2. [Features](#features)
3. [Slash-Commands](#slash-commands)
4. [Moderatorenbereich](#moderatorenbereich)
5. [Architektur](#architektur)
6. [Entwicklung](#entwicklung)
7. [FAQ](#faq)
8. [Changelog](#changelog)
9. [Lizenz](#lizenz)
10. [Links](#links)

---

## Schnellstart

Voraussetzung ist Python ≥3.11. Der Bot läuft vorzugsweise auf [Railway](https://railway.app) und bezieht dort seine Umgebungsvariablen.

```bash
pip install -r requirements.txt
cp .env.example .env  # Bot-Token und Server-ID eintragen
python bot.py
```

Die wichtigsten Variablen aus `.env`:

```env
bot_key=DISCORD_BOT_TOKEN
server_id=DEINE_GUILD_ID
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
# Bei Zertifikatsproblemen kann die Überprüfung für die PTCGP-API deaktiviert werden
PTCGP_SKIP_SSL_VERIFY=0
```

Beim ersten Start werden persistente Daten unter `data/pers/` angelegt (Punktedatenbank, Quiz-Historie etc.).

## Datenstruktur

Die statischen Dateien sind wie folgt organisiert:

- `data/quiz/questions_*.json` enthalten den Fragepool.
- `data/quiz/templates/` hält Textbausteine für dynamische Fragen.
- `data/wcr/units.json` speichert alle Minis inklusive Werte und lokalisierter Texte.
- `data/wcr/categories.json` definiert Fraktionen, Typen, Geschwindigkeiten und Traits.
- `data/wcr/stat_labels.json` bietet Übersetzungen der Statistikbezeichnungen.
- `data/wcr/pictures.json` ordnet Einheiten zugehörige Icons zu.

---

## Features

| Modul       | Beschreibung                                                            |
|-------------|-------------------------------------------------------------------------|
| **Quiz**    | Automatische und manuelle Fragen für verschiedene Spielebereiche, inkl. Quiz-Duelle |
| **Champion**| Punktesystem mit Ranglisten und automatischen Rollen                    |
| **WCR**     | Warcraft Rumble: Detailabfragen und Filtersuche mit Autocomplete        |
| **PTCGP**   | Verwaltung von Pokémon TCG Pocket Karten                               |

---

## Slash-Commands

### `/champion`

| Befehl                | Kurzbeschreibung                                   |
|-----------------------|----------------------------------------------------|
| `/champion give`      | Punkte vergeben *(Mod)*                            |
| `/champion remove`    | Punkte abziehen *(Mod)*                            |
| `/champion set`       | Punktestand festlegen *(Mod)*                      |
| `/champion reset`     | Punkte auf 0 setzen *(Mod)*                         |
| `/champion score`     | Eigene oder fremde Punkte anzeigen                 |
| `/champion myhistory` | Eigenen Punkteverlauf anzeigen                     |
| `/champion history`   | Verlauf eines Nutzers anzeigen *(Mod)*            |
| `/champion leaderboard` | Topliste nach Champion-Rolle                      |
| `/champion roles`     | Alle Rollen und ihre Punktschwellen                |
| `/champion rank`      | Rang eines Nutzers in der Bestenliste              |
| `/champion clean`     | Entfernt Daten ausgeschiedener Mitglieder *(Mod)*  |

### `/quiz`

| Befehl                | Kurzbeschreibung                                                     |
|-----------------------|--------------------------------------------------------------------|
| `/quiz enable`        | Quiz in diesem Channel aktivieren (Area & Sprache festlegen) *(Mod)*|
| `/quiz disable`       | Quiz in diesem Channel deaktivieren *(Mod)*                         |
| `/quiz ask`           | Sofort eine Frage posten *(Mod)*                                    |
| `/quiz answer`        | Aktive Frage beenden und Lösung zeigen *(Mod)*                      |
| `/quiz status`        | Restzeit und Nachrichtenzähler anzeigen *(Mod)*                     |
| `/quiz language`      | Sprache des Quiz setzen *(Mod)*                                     |
| `/quiz time`          | Zeitfenster für automatische Fragen setzen *(Mod)*                  |
| `/quiz threshold`     | Nachrichten-Schwelle für Auto-Fragen *(Mod)*                       |
| `/quiz reset`         | Fragehistorie für diesen Channel löschen *(Mod)*                    |
| `/quiz duel`          | Starte ein Quiz-Duell (Best‑of‑X oder dynamic, optionaler Timeout). Nach jeder Runde werden Lösung, Antworten und Reaktionszeiten angezeigt |
| `/quiz duelstats`     | Eigene oder fremde Duell-Bilanz anzeigen |
| `/quiz stats`         | Anzahl deiner (oder fremder) richtigen Antworten anzeigen |
| `/quiz duelleaderboard` | Rangliste der meisten Duell-Siege |

Der Modus `dynamic` passt die Rundenzahl automatisch an und steht nur in Areas mit dynamischen Fragen (momentan `wcr`) zur Verfügung.

### `/wcr`

| Befehl              | Kurzbeschreibung                                                    |
|---------------------|---------------------------------------------------------------------|
| `/wcr name`         | Details und Statistiken zu einer Einheit (mehrsprachig)             |
| `/wcr filter`       | Minis über diverse Filter finden (Kosten, Fraktion, Traits ...)      |
| `/wcr duell`        | Simuliert ein Duell zweier Minis (Level optional) und zeigt eine detaillierte Berechnung inkl. Trait-Effekten an |

Wird kein Level angegeben, verwendet der Bot die Basiswerte (Level 1).

Autocomplete und Fuzzy-Matching erleichtern die Eingabe.
Alle `/wcr`-Befehle besitzen zusätzlich den Parameter `public`, um die Antwort öffentlich anzuzeigen.

### `/ptcgp`

| Befehl          | Kurzbeschreibung                              |
|-----------------|------------------------------------------------|
| `/ptcgp update` | Lädt alle Karten neu *(Mod)*                  |
| `/ptcgp stats`  | Zeigt die Anzahl gespeicherter Karten         |
---

## Moderatorenbereich

Befehle mit dem Hinweis *Mod* sind nur für Nutzer mit dem Recht `Manage Server` sichtbar. Dies wird über `default_permissions` direkt in den Slash-Commands gesteuert.

---

## Architektur

- **Cogs** trennen Funktionsbereiche sauber: `quiz`, `champion`, `wcr`.
- **Zentrale Daten** werden im `setup_hook` geladen (`bot.data`) und allen Cogs bereitgestellt.
- **Quiz-Subsystem** nutzt einen `QuestionGenerator` (statisch & dynamisch), `QuestionStateManager` für Persistenz und einen Scheduler für automatische Fragen. Der nächste geplante Zeitpunkt wird gespeichert, sodass laufende Fenster nach einem Neustart fortgeführt werden können.
- **Champion-System** speichert Punkte in SQLite und vergibt Rollen gemäß `data/champion/roles.json` (Rollen-ID und Schwelle pro Eintrag).
- Beim Entladen des Champion-Cogs wird die Datenbankverbindung sauber geschlossen.
- **WCR-Modul** verarbeitet die Daten unter `data/wcr/` und nutzt sie für Autocomplete sowie dynamische Fragen.  
  - `units.json` enthält alle Minis samt Werten und mehrsprachigen Texten.  
  - `categories.json` definiert Fraktionen, Typen, Geschwindigkeiten und Traits.  
  - `stat_labels.json` übersetzt die Statistik-Bezeichnungen.  
  - `pictures.json` ordnet jedem Mini ein Icon zu.  
  - Die Fragevorlagen liegen unter `data/quiz/templates/wcr.json`.
- Alle Slash-Commands werden **guild-basiert** registriert und nur für die Haupt-Guild synchronisiert.

Persistente Daten liegen in `data/pers/` und sollten nicht ins Repository aufgenommen werden.

---

## Entwicklung

```bash
pip install -r requirements.txt  # installiert auch pytest-asyncio
flake8       # Linting
pytest -q    # Test Suite
```

Neue Features benötigen passende Tests. Die Fixtures in `tests/conftest.py` stellen Umgebungsvariablen bereit und bieten `patch_logged_task`, das `create_logged_task` nun global ersetzt. Ebenfalls sorgt `auto_stop_views` dafür, dass in Tests erstellte `discord.ui.View`-Instanzen automatisch gestoppt werden. Das neue Fixture `assert_no_tasks` prüft zudem, ob nach jedem Test noch asyncio-Tasks laufen und schlägt sonst fehl.

Pull Requests sind willkommen! Bitte halte dich an den bestehenden Codestyle (PEP8, formatiert mit *Black*) und prüfe vor dem Commit, dass `flake8` und `pytest` grün sind.

---

## FAQ

**Frage:** *Kann ich den Bot auch auf meinem eigenen Server hosten?*

**Antwort:** Ja. Trage in `.env` dein Bot-Token (`bot_key`) und die Server-ID (`server_id`) ein und starte `python bot.py`.

**Frage:** *Wie richte ich ein Quiz nur für bestimmte Channels ein?*

**Antwort:** Nutze `/quiz enable` im jeweiligen Channel. Mit `/quiz disable` kannst du es wieder abschalten.

**Frage:** *Wie erweitere ich den Fragenpool?*

**Antwort:** Bearbeite die Dateien unter `data/quiz/questions_de.json` bzw. `questions_en.json`. Füge eigene Fragen mit eindeutiger ID hinzu und starte den Bot neu.

**Frage:** *Wo passe ich Vorlagen für WCR-Fragen an?*

**Antwort:** Die Texte für dynamische Fragen findest du in `data/quiz/templates/wcr.json`.

---

## Changelog

Eine detaillierte Liste aller Änderungen findest du im [Projekt-Repository](https://github.com/LotusGamingDE) im Release-Bereich.

---

## Lizenz

Dieses Projekt steht unter der **MIT License**. Siehe die Datei `LICENSE` im Repository.

---

## Links

- [Lotus Gaming auf Discord](https://discord.gg/)
- [GitHub Repository](https://github.com/LotusGamingDE)
- [Discord.py Dokumentation](https://discordpy.readthedocs.io/)

Für weiterführende Informationen siehe auch die Tests im Ordner `tests/` sowie die einzelnen Cog-Dateien.
