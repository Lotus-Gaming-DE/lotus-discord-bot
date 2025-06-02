
![Logo von Lotus Gaming](./data/LotusGamingColorless.png)

# Lotus Gaming Discord Bot

Willkommen zum **Lotus Gaming Discord Bot** Projekt! Dieser Bot wurde entwickelt, um das Spielerlebnis innerhalb unserer Community zu verbessern, indem er nützliche Funktionen und Interaktionen rund um unsere Lieblingsspiele bereitstellt. Der Bot ist modular aufgebaut, was eine einfache Erweiterung und Wartung verschiedener Funktionen ermöglicht.

## Übersicht

Der **Lotus Gaming Bot** ist aktuell in drei Hauptmodule unterteilt:
- **Champion Modul**: Verwaltung und Tracking von Champion-Punkten.
- **Quiz Modul**: Interaktives Quiz zu verschiedenen Spielebereichen (z.B. WCR, D4, PTCGP).
- **WCR Modul**: Datenbank-Integration und Befehle für Warcraft Rumble.

Der Bot läuft ausschließlich auf unserem Discord-Server und benötigt keine Installation auf anderen Systemen.

## Dateistruktur

```
LotusGamingDE/
├─ bot.py
├─ README.md
├─ requirements.txt
├─ cogs/
│  ├─ champion/
│  │  ├─ __init__.py
│  │  ├─ cog.py
│  │  └─ slash_commands.py
│  ├─ quiz/
│  │  ├─ __init__.py
│  │  ├─ cog.py
│  │  ├─ data_loader.py
│  │  ├─ question_generator.py
│  │  ├─ slash_commands.py
│  │  ├─ utils.py
│  │  ├─ views.py
│  │  └─ wcr_question_provider.py
│  └─ wcr/
│     ├─ __init__.py
│     ├─ cog.py
│     ├─ data_loader.py
│     ├─ helpers.py
│     ├─ slash_commands.py
│     └─ views.py
└─ data/
   ├─ champion/
   │  ├─ points.db
   │  └─ roles.json
   ├─ media/
   │  └─ LotusGamingColorless.png
   ├─ quiz/
   │  ├─ asked_questions.json
   │  ├─ questions_de.json
   │  ├─ questions_en.json
   │  └─ scores.json
   └─ wcr/
      ├─ locals/
      │  └─ (Sprachdateien JSON)
      ├─ pictures.json
      └─ units.json
```

### Kurzbeschreibung der Ordner

- **bot.py**: Einstiegspunkt und Initialisierung des Bots.
- **requirements.txt**: Liste der Python-Abhängigkeiten.
- **README.md**: Diese Datei, Überblick über das Projekt.

- **cogs/champion/**: 
  - `__init__.py`: Registriert das Champion-Modul und die Slash-Command-Gruppe.
  - `cog.py`: Enthält die Kern-Logik für Champion-Punkteverwaltung (Datenbank, Rollen-Logik).
  - `slash_commands.py`: Definiert alle Slash-Commands (`/champion give`, `/champion remove`, `/champion set`, `/champion info`, `/champion history`, `/champion leaderboard`).

- **cogs/quiz/**:
  - `__init__.py`: Initialisiert das Quiz-Modul, lädt Daten, startet Scheduler-Tasks und registriert `/quiz`-Slash-Gruppe.
  - `cog.py`: Kern-Logik des Quiz (Fragen-Erstellung, Scheduling, Antwort-Handling).
  - `data_loader.py`: Lädt und speichert Quiz-Fragen, Scores und bearbeitete Fragen.
  - `question_generator.py`: Erzeugt neue Fragen, kombiniert statische und dynamische Provider (z.B. WCR-Fragen).
  - `slash_commands.py`: Definiert alle `/quiz`-Slash-Commands (z.B. `ask`, `answer`, `status`, `disable`, `enable`, `time`, `language`).
  - `utils.py`: Hilfsfunktionen (z.B. Antwortprüfung).
  - `views.py`: Discord-UI-Komponenten (Buttons, Modals) für das Quiz.
  - `wcr_question_provider.py`: Dynamischer Fragen-Provider für WCR basierend auf API-/Datenbank-Abfragen.

- **cogs/wcr/**:
  - `__init__.py`: Initialisiert das WCR-Modul und registriert `/wcr`-Slash-Gruppe.
  - `cog.py`: Kern-Logik für Datenverarbeitung, Caching und Interaktionen.
  - `data_loader.py`: Lädt WCR-Daten (Einheiten, Bilder, Sprachdateien).
  - `helpers.py`: Unterstützende Funktionen (z.B. Permutationssuche, Normalisierung).
  - `slash_commands.py`: Definiert alle `/wcr`-Slash-Commands (z.B. `filter`, `name`).
  - `views.py`: Discord-UI-Komponenten für WCR (z.B. interaktive Auswahl).

- **data/**:
  - **champion/**: Speichert die SQLite-Datenbank (`points.db`) und Rollen-Konfiguration (`roles.json`).
  - **media/**: Enthält Assets wie das Lotus Gaming Logo.
  - **quiz/**: Statistische Quiz-Daten, bearbeitete Fragen und Scores in JSON-Dateien.
  - **wcr/**: Statische WCR-Daten in JSON (Einheiten, Bilder, lokale Texte).

## Funktionen im Überblick

### Champion Modul

- `/champion give <user> <punkte> <grund>`: Gibt einem User Champion-Punkte (nur Mods/Admins).
- `/champion remove <user> <punkte> <grund>`: Entfernt Punkte von einem User (nur Mods/Admins).
- `/champion set <user> <punkte> <grund>`: Setzt den Punktestand eines Users (nur Mods/Admins).
- `/champion reset <user>`: Setzt die Punkte eines Users auf 0 (nur Mods/Admins).
- `/champion info`: Zeigt deine aktuellen Punkte an.
- `/champion history <user>`: Zeigt die letzten 10 Punkt-Änderungen eines Users.
- `/champion leaderboard [page]`: Zeigt Top 10-Ranking (10 Einträge pro Seite).

### Quiz Modul

- `/quiz ask`: Sofortige Quizfrage im aktuellen Channel. Frage bleibt bis zum Ende des Zeitfensters aktiv oder bis sie beantwortet wird.
- `/quiz answer`: Zeigt die richtige Antwort und beendet die aktuelle Frage (Mod-Befehl).
- `/quiz status`: Zeigt Status (Restzeit & Nachrichten-Zähler) der aktuellen Frage an.
- `/quiz time <minutes>`: Setzt das Zeitfenster (1–120 Minuten) für dieses Quiz (pro Channel).
- `/quiz language <de|en>`: Ändert Sprache für die Quiz-Fragen dieses Channels.
- `/quiz disable`: Deaktiviert Quiz für diesen Channel (Fragen werden nicht mehr automatisch gestellt).
- `/quiz enable <area_name> [lang]`: Aktiviert Quiz in diesem Channel für eine bestimmte Area (z.B. `d4`, `wcr`) und Sprache (de oder en).
- **Automatisches Scheduling**: Der Bot prüft in einem definierten Zeitfenster (Standard 15 Minuten), ob genügend Activity (≥10 Nachrichten) vorhanden ist, um eine Frage zu posten. Andernfalls wird die Frage verschoben.

### WCR Modul

- `/wcr filter [cost] [speed] [faction] [type] [trait] [lang]`: Filtert Minis basierend auf Kosten, Geschwindigkeit, Fraktion, Typ, Merkmal und Sprache (de/en). Liefert interaktive Auswahl.
- `/wcr name <name> [lang]`: Zeigt Details zu einem Mini anhand des Namens. Unterstützt Autocomplete und Permutationssuche. Liefert Embed mit Statistiken, Talenten, Merkmalen und Medien (Bilder).
- **Autocomplete**: Vorschläge in den Slash-Commands für Werte (cost, speed, faction, type, trait) basierend auf geladenen WCR-Daten.
- **Mehrsprachigkeit**: Standardmäßig Deutsch, kann mit optionalem `lang`-Parameter auf Englisch umgestellt werden.

## Kontakt

Für Fragen oder Feedback erreichst du uns über unseren Discord-Server:

- **Discord Server**: [Lotus Gaming](https://discord.gg/LotusGaming)
- **Discord Benutzer**: gs3rr4 (Discord User ID: 163375118096007168)
- **E-Mail**: [lotusgamingde@gmail.com](mailto:lotusgamingde@gmail.com)

---

