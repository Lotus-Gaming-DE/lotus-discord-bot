![Logo von Lotus Gaming](./data/LotusGamingColorless.png)

# Lotus Gaming Discord Bot

Willkommen beim **Lotus Gaming Discord Bot**! Dieser modulare Bot bietet interaktive Quiz-Events, ein Champion-Punktesystem und umfangreiche Warcraft‑Rumble-Abfragen. Alle Funktionen sind komplett auf Slash‑Commands ausgelegt und lassen sich flexibel aktivieren.

## Zielgruppe

- **Moderatoren/Admins**: Verwaltung und Einsatz der Slash‑Commands
- **Entwickler**: Weiterentwicklung des Bots und Pflege der Daten

---

## Inhaltsverzeichnis

- [Übersicht & Module](#übersicht--module)
- [Setup](#setup)
- [Projektstruktur](#projektstruktur)
- [Slash-Commands](#slash-commands)
- [Berechtigungen](#berechtigungen)
- [Technische Konzepte](#technische-konzepte)
- [Tests](#tests)
- [Änderungsprotokoll](#änderungsprotokoll)
- [Kontakt](#kontakt)

---

## Übersicht & Module

| Modul      | Zweck                                                          |
| ---------- | -------------------------------------------------------------- |
| `quiz`     | Automatisierte Fragen pro Spielbereich inkl. Quiz‑Duellen     |
| `champion` | Punkteverwaltung, Ranglisten und automatische Rollenvergaben |
| `wcr`      | Warcraft‑Rumble Filter, Detailabfragen und dynamische Fragen |

---

## Setup

1. Abhängigkeiten installieren
   ```bash
   pip install -r requirements.txt
   ```
2. `.env` im Projektverzeichnis anlegen
   ```env
   bot_key=DEIN_DISCORD_TOKEN
   server_id=DEINE_SERVER_ID
   LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
   ```
3. Bot starten
   ```bash
   python bot.py
   ```

Python ≥3.11 wird empfohlen.

---

## Projektstruktur

```bash
LotusGamingDE/
├─ bot.py                  # Einstiegspunkt
├─ log_setup.py            # Logging-Konfiguration
├─ requirements.txt
├─ cogs/                   # Alle Module
│  ├─ champion/            # Punkte-System
│  ├─ quiz/                # Quiz-Logik & Fragegeneratoren
│  └─ wcr/                 # Warcraft Rumble Features
├─ data/                   # Statische Daten & Medien
│  ├─ champion/roles.json
│  ├─ quiz/questions_de.json
│  └─ wcr/                 # Units, Bilder, Übersetzungen
└─ tests/                  # Pytest-Suite
```

Persistente Dateien wie Punktedatenbank oder Fragehistorie werden zur Laufzeit im Ordner `data/pers/` angelegt.

---

## Slash-Commands

### Champion
```bash
/champion give         # Punkte vergeben
/champion remove       # Punkte abziehen
/champion set          # Punkte festlegen
/champion reset        # Punkte auf 0 setzen
/champion score        # Eigene oder fremde Punkte anzeigen
/champion myhistory    # Eigenen Verlauf einsehen
/champion history      # Verlauf eines Users
/champion leaderboard  # Rangliste
/champion roles        # Rollen-Schwellen
/champion rank         # Rang eines Users
/champion clean        # Entfernt Daten ehemaliger Mitglieder
```

### Quiz
```bash
/quiz ask              # Sofort eine Frage posten
/quiz answer           # Aktive Frage beenden
/quiz status           # Restzeit & Nachrichtenzähler
/quiz disable          # Quiz in diesem Channel deaktivieren
/quiz enable           # Quiz aktivieren (Area, Sprache)
/quiz language         # Sprache des Quiz ändern
/quiz time             # Zeitfenster konfigurieren
/quiz duel             # Quiz-Duell starten (bo3, bo5, dynamic)
/quiz duel             # Quiz-Duell starten (bo3, bo5 oder dynamic)
/quiz threshold        # Nachrichtenschwelle
/quiz reset            # Fragehistorie zurücksetzen
```

`dynamic` passt die Rundenanzahl flexibel an und ist nur in Areas mit generischen
Fragequellen verfügbar (derzeit nur `wcr`).

### Warcraft Rumble
```bash
/wcr name <Mini>       # Details zu einer Einheit
/wcr filter            # Einheiten anhand von Filtern finden
```

Autocomplete und Fuzzy-Matching sind integriert.

## Berechtigungen

Einige Slash-Befehle sind nur für Moderatoren mit dem Recht **Manage Server**
(``manage_guild``) nutzbar. Sie werden dank ``default_permissions`` nur diesen
Nutzern angezeigt. Alle anderen Befehle stehen jedem Mitglied offen.

**Moderatorenbefehle:**

```
/champion give
/champion remove
/champion set
/champion reset
/champion history
/champion clean

/quiz ask
/quiz answer
/quiz status
/quiz disable
/quiz enable
/quiz language
/quiz time
/quiz threshold
/quiz reset
```

---

## Technische Konzepte

- Modularer Aufbau mit Discord Cogs
- Zentrale Datensammlung im `setup_hook`
- Dynamische & statische Quizfragen mit Wiederherstellung nach Neustart
- Nachrichtentracking und automatische Zeitfenster
- Punktesystem mit SQLite und automatischer Rollenvergabe
- Umfangreiche Warcraft‑Rumble Daten und Autocomplete‑Funktionen

---

## Tests

Die Test-Suite basiert auf **pytest**. Installiere vorher unbedingt `discord.py` und alle
weiteren Pakete aus `requirements.txt`, sonst schlagen die Importe fehl.
```bash
pip install -r requirements.txt
pytest -q
```

