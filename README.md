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
4. [Champion-System](#champion-system)
5. [Moderatorenbereich](#moderatorenbereich)
6. [Architektur](#architektur)
7. [Entwicklung](#entwicklung)
8. [FAQ](#faq)
9. [Changelog](#changelog)
10. [Lizenz](#lizenz)
11. [Links](#links)

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
# Basis-URL der WCR-API
WCR_API_URL=https://wcr-api.up.railway.app
# Basis-URL für Bilder (Standard: https://www.method.gg)
WCR_IMAGE_BASE=https://www.method.gg
# Maximales Alter des WCR-Caches in Sekunden (Standard: 86400)
# Maximales Alter des WCR-Caches in Sekunden (0 schaltet den Cache ab)
WCR_CACHE_TTL=86400
# Bei Zertifikatsproblemen kann die Überprüfung für die PTCGP-API deaktiviert werden
PTCGP_SKIP_SSL_VERIFY=0
# Optional: Pfad zur Champion-Datenbank
CHAMPION_DB_PATH=data/pers/champion/points.db
```

Ohne eine gesetzte `WCR_API_URL` wird das WCR-Modul beim Start deaktiviert.

Beim ersten Start werden persistente Daten unter `data/pers/` angelegt (Punktedatenbank, Quiz-Historie etc.).

## Datenstruktur

Die statischen Dateien sind wie folgt organisiert:

- `data/quiz/questions_*.json` enthalten den Fragepool.
- `data/quiz/templates/` hält Textbausteine für dynamische Fragen.
- `data/wcr/units.json` dient lediglich als Testdatenbasis für alle Minis.
- `data/wcr/categories.json` stellt Testdaten für Fraktionen, Typen, Geschwindigkeiten und Traits bereit.
- `data/wcr/stat_labels.json` bietet Testübersetzungen der Statistikbezeichnungen.
 - `data/wcr/faction_meta.json` enthält lokale Angaben zu Fraktionen wie Icon und Farbe und listet Leader-Icons für kombinierte Fraktionen.

Die aktuellen Spieldaten werden beim Start einmalig über die in `WCR_API_URL` definierte API geladen und im Speicher gehalten.

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
Der Parameter `lang` bestimmt ausschließlich die Ausgabesprache; die Namenssuche berücksichtigt alle unterstützten Sprachen.
Alle `/wcr`-Befehle besitzen zusätzlich den Parameter `public`, um die Antwort öffentlich anzuzeigen.

#### Beispiele

```bash
/wcr name Abscheulichkeit lang=de
```
*Embed mit Titel "Abscheulichkeit", Kosten 6 und weiteren Stat-Feldern.*

```bash
/wcr filter cost=6 lang=de
```
*Zeigt eine Auswahlliste mit 8 passenden Minis.*

```bash
/wcr duell Gargoyle "General Drakkisath" lang=de
```
*Beispielausgabe:* `Gargoyle würde General Drakkisath nach 10.9 Sekunden besiegen.`

### `/ptcgp`

| Befehl          | Kurzbeschreibung                              |
|-----------------|------------------------------------------------|
| `/ptcgp update` | Lädt alle Karten neu *(Mod)*                  |
| `/ptcgp stats`  | Zeigt die Anzahl gespeicherter Karten         |
---

## Champion-System

Das Modul verwaltet Punkte und Rollen der Mitglieder. Die Datenbank liegt
standardmäßig unter `data/pers/champion/points.db`. Über die Umgebungsvariable
`CHAMPION_DB_PATH` kannst du einen eigenen Speicherort festlegen.

Die Datei `data/champion/roles.json` definiert alle Champion-Rollen:

```json
[
    {"id": 0, "name": "Emerging Champion", "threshold": 50}
]
```

`id` ist die Rollen-ID (optional), `name` der Anzeigename und `threshold` die
erforderlichen Punkte. Sortiere die Einträge absteigend nach `threshold`.
Um Schwellenwerte anzupassen oder neue Rollen einzufügen, editiere die Datei und
starte den Bot neu.

---

## Moderatorenbereich

Befehle mit dem Hinweis *Mod* sind nur für Nutzer mit dem Recht `Manage Server` sichtbar. Dies wird über `default_permissions` direkt in den Slash-Commands gesteuert.

---

## Architektur

- **Cogs** trennen Funktionsbereiche sauber: `quiz`, `champion`, `wcr`.
- **Zentrale Daten** werden im `setup_hook` geladen (`bot.data`) und allen Cogs bereitgestellt.
- **Quiz-Subsystem** nutzt einen `QuestionGenerator` (statisch & dynamisch), `QuestionStateManager` für Persistenz und einen Scheduler für automatische Fragen. Der nächste geplante Zeitpunkt wird gespeichert, sodass laufende Fenster nach einem Neustart fortgeführt werden können.
- **Champion-System** speichert Punkte in SQLite (Pfad über `CHAMPION_DB_PATH` anpassbar) und vergibt Rollen gemäß `data/champion/roles.json` (Rollen-ID und Schwelle pro Eintrag). Fehlt eine definierte ID, wird keine gleichnamige Rolle verwendet und es erscheint ein Hinweis im Log.
- Punktestände können nicht negativ werden; zu hohe Abzüge setzen sie automatisch auf 0.
- Die Mod-Befehle `give`, `remove` und `set` akzeptieren nur noch positive Werte.
- Beim Entladen des Champion-Cogs wird die Datenbankverbindung sauber geschlossen.
- Beim Entladen wird nun auch auf alle Hintergrund-Tasks gewartet.
  - Die Warteschlange für Rollen-Updates fasst standardmäßig 1000 Einträge. Bei
  Überschreitung wird nun ein ``RuntimeError`` ausgelöst.
- **WCR-Modul** bezieht seine Daten über die in ``WCR_API_URL`` angegebene API und nutzt sie für Autocomplete sowie dynamische Fragen.
  - Bilder werden relativ zu ``WCR_IMAGE_BASE`` aufgel\u00f6st.
  - Die API stellt nur ``units`` und ``categories`` bereit. IDs sind dabei Strings.
  - Beim Abrufen dieser Daten wird ein Timeout von 10 Sekunden verwendet.
  - Wenn deutsche Texte fehlen, greift das Modul automatisch auf die englischen
    Daten zurück.
  - Fehlen die Lokalisierungsdaten komplett (``locals``), wird aus den
    ``units`` ein englischer Fallback erzeugt.
  - Die Fragevorlagen liegen unter `data/quiz/templates/wcr.json`.
  - Geladene Daten werden dauerhaft in `data/pers/wcr_cache.json` zwischengespeichert.
    Über ``WCR_CACHE_TTL`` legst du fest, wie lange dieser Cache gültig bleibt.
    Bei ``0`` wird er bei jedem Start neu aufgebaut.
  - Beim Start erzeugt `_export_emojis` automatisch `data/emojis.json`; diese
    Datei enthält ein einfaches Mapping `{name: syntax}`. Die Emoji-Namen müssen
- Alle Slash-Commands werden **guild-basiert** registriert und nur für die Haupt-Guild synchronisiert.
### Troubleshooting
Bei API-Fehlern prüfe die Variable `WCR_API_URL`. Setze gegebenenfalls `WCR_CACHE_TTL=0` oder lösche `data/pers/wcr_cache.json`, um den Cache zu erneuern.
- Zur Vereinfachung der Registrierung stellt `utils.setup_helpers.register_cog_and_group` eine Hilfsfunktion bereit,
  die nach dem Hinzufügen der Gruppe automatisch `bot.tree.sync` für die Haupt-Guild ausführt.
  Tritt dabei ein Fehler auf, wird er geloggt und erneut geworfen, sodass ein missglückter Start sofort sichtbar ist.
Persistente Daten liegen in `data/pers/` und sollten nicht ins Repository aufgenommen werden.

---

## Entwicklung

```bash
pip install -r requirements.txt  # installiert auch pytest-asyncio
flake8       # Linting
pytest -q    # Test Suite
```

Neue Features benötigen passende Tests. Die Fixtures in `tests/conftest.py` stellen Umgebungsvariablen bereit und bieten `patch_logged_task`, das `create_logged_task` nun global ersetzt. Ebenfalls sorgt `auto_stop_views` dafür, dass in Tests erstellte `discord.ui.View`-Instanzen automatisch gestoppt werden. Das neue Fixture `assert_no_tasks` prüft zudem, ob nach jedem Test noch asyncio-Tasks laufen und schlägt sonst fehl. Zusätzlich stellt `tests/conftest.py` ein sessionweites ``event_loop``-Fixture bereit, damit alle Async-Tests denselben Loop nutzen und am Ende sauber schließen.

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

**Frage:** *Wie kann ich die WCR-Daten manuell aktualisieren?*

**Antwort:** Lösche die Datei `data/pers/wcr_cache.json` oder setze `WCR_CACHE_TTL=0` und starte den Bot neu.

---

## Changelog

Eine detaillierte Liste aller Änderungen findest du im [Changelog](CHANGELOG.md) und im Release-Bereich des [Projekt-Repositorys](https://github.com/LotusGamingDE).
Eine detaillierte Liste aller Änderungen findest du in der Datei `CHANGELOG.md`.

---

## Lizenz

Dieses Projekt steht unter der **MIT License**. Siehe die Datei `LICENSE` im Repository.

---

## Links

- [Lotus Gaming auf Discord](https://discord.gg/)
- [GitHub Repository](https://github.com/LotusGamingDE)
- [Discord.py Dokumentation](https://discordpy.readthedocs.io/)

Für weiterführende Informationen siehe auch die Tests im Ordner `tests/` sowie die einzelnen Cog-Dateien.
