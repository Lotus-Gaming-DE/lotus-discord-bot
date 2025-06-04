![Logo von Lotus Gaming](./data/LotusGamingColorless.png)

# Lotus Gaming Discord Bot

Willkommen beim **Lotus Gaming Discord Bot**!
Dieser modulare Discord-Bot wurde speziell für die **Lotus Gaming Community** entwickelt. Er bietet interaktive Quiz-Events, ein Champion-Punktesystem zur Anerkennung aktiver Mitglieder und umfangreiche Abfragen zu Warcraft Rumble.

## Zielgruppe

Diese Dokumentation richtet sich an:

* **Mods/Admins**, die Slash-Commands im Discord verstehen und verwenden wollen.
* **Entwickler**, die zur Weiterentwicklung beitragen möchten.

---

## Inhaltsverzeichnis

* [Übersicht & Module](#übersicht--module)
* [Setup](#setup)
* [Projektstruktur](#projektstruktur)
* [Slash-Commands](#slash-commands)
* [Technische Konzepte](#technische-konzepte)
* [Änderungsprotokoll](#änderungsprotokoll)
* [Kontakt](#kontakt)

---

## Übersicht & Module

Der Bot ist in folgende Module unterteilt:

| Modul      | Zweck                                                     |
| ---------- | --------------------------------------------------------- |
| `quiz`     | Automatisierte Quizfragen je Spielbereich (z. B. D4, WCR) |
| `champion` | Vergabe & Tracking von Community-Punkten                  |
| `wcr`      | WCR-spezifische Filter- & Infoabfragen                    |

Jede Funktion ist vollständig über **Slash-Commands** steuerbar.

---

## Setup

1. Alle Abhängigkeiten installieren:

   ```bash
   pip install -r requirements.txt
   ```

2. Eine `.env`-Datei im Projektverzeichnis anlegen und dort die folgenden
   Umgebungsvariablen definieren:

   ```env
   bot_key=DEIN_DISCORD_TOKEN
   server_id=DEINE_SERVER_ID
   ```

3. Den Bot anschließend mit

   ```bash
   python bot.py
   ```

   starten.

---

## Projektstruktur

```bash
LotusGamingDE/
├─ bot.py
├─ requirements.txt
├─ README.md
├─ cogs/
│  ├─ champion/
│  │  ├─ __init__.py
│  │  ├─ cog.py
│  │  └─ slash_commands.py
│  ├─ quiz/
│  │  ├─ __init__.py
│  │  ├─ cog.py
│  │  ├─ scheduler.py
│  │  ├─ question_generator.py
│  │  ├─ question_closer.py
│  │  ├─ question_manager.py
│  │  ├─ question_restorer.py
│  │  ├─ question_state.py
│  │  ├─ message_tracker.py
│  │  ├─ views.py
│  │  ├─ utils.py
│  │  └─ slash_commands.py
│  └─ wcr/
│     ├─ __init__.py
│     ├─ cog.py
│     ├─ data_loader.py
│     ├─ slash_commands.py
│     └─ helpers.py
├─ data/
│  ├─ champion/
│  │  └─ roles.json
│  ├─ quiz/
│  │  └─ questions_de.json
│  ├─ wcr/
│  │  ├─ units.json
│  │  ├─ pictures.json
│  │  └─ locals/
│  │     ├─ de.json
│  │     └─ en.json
│  ├─ media/
│  │  └─ LotusGaming.png
│  └─ pers/
│     ├─ champion/
│     │  └─ points.db
│     └─ quiz/
│        └─ question_state.json
```

---

## Slash-Commands

### Champion Modul

```bash
/champion give         # Punkte vergeben
/champion remove       # Punkte abziehen
/champion set          # Punkte direkt setzen
/champion reset        # Punkte zurücksetzen
/champion info         # Eigene Punkte anzeigen
/champion history      # Verlauf einzelner User
/champion leaderboard  # Rangliste anzeigen
```

### Quiz Modul

```bash
/quiz ask              # Stelle sofort eine neue Frage
/quiz answer           # Beende aktive Frage und zeige Lösung
/quiz status           # Zeige Status (Restzeit, Aktivität)
/quiz disable          # Quiz in diesem Channel deaktivieren
/quiz enable           # Quiz aktivieren (mit Area und Sprache)
/quiz language         # Sprache für diesen Channel wechseln
/quiz time             # Zeitfenster (z. B. alle 15 Minuten)
/quiz dynamic          # Anzahl dynamischer Fragen anpassen
/quiz threshold        # Nachrichten-Schwelle vor automatischen Fragen
/quiz reset            # Fragehistorie zurücksetzen
```

### WCR Modul

```bash
/wcr name              # Detailabfrage zu einer Mini
/wcr filter            # Finde passende Einheiten nach Filter
```

Autocomplete & Permutationssuche sind integriert.

---

## Technische Konzepte

* Modularer Aufbau mit gekapselten Cogs
* Slash-Command-Gruppierung (`/quiz`, `/wcr`, `/champion`)
* Persistente Daten in `data/pers/` (Fragenstatus, Punkte, etc.)
* Trennung von statischen (z. B. Sprachdateien) und dynamischen Daten
* Dynamische & statische Quizfragen in einem System kombinierbar
* Wiederherstellung & Auto-Close aktiver Fragen bei Neustart
* Detailliertes Logging aller Zustandsänderungen
* Emoji-Export für Role Icons & Leaderboards
* Rollenzuweisung automatisiert auf Basis von Punkteschwellen

---

## Änderungsprotokoll (Stand 2025-06-03)

* ✅ **WCR-Quiz: Dynamische & statische Fragen kombiniert**

  * Über `max_wcr_dynamic_questions` steuerbar
  * Verbesserte Fehlerbehandlung und Logging

* ✅ **Fragen-Wiederherstellung verbessert**

  * Kategorie wird korrekt angezeigt
  * Auto-Close-Methode aus Cog entfernt und zentralisiert

* ✅ **Nachrichtenzählung korrigiert**

  * Doppelte Erhöhung pro Nachricht unterbunden

* ✅ **Champion-Modul aktualisiert**

  * Datenbankpfad zu `data/pers/` verschoben
  * Kein Rollen-Fallback mehr: `roles.json` wird vorausgesetzt

* ✅ **Struktur- und Architekturverbesserungen**

  * Weitere Entkopplung der Cog-Logik
  * `QuestionManager` & `QuestionGenerator` arbeiten isoliert

---

## Kontakt

* **Projektleitung & Hauptentwickler**: `gs3rr4`
* **Discord**: [discord.gg/LotusGaming](https://discord.gg/LotusGaming)
* **E-Mail**: [lotusgamingde@gmail.com](mailto:lotusgamingde@gmail.com)

---

Letzter Stand: 2025-06-03
Verantwortlich für diesen Stand: `gs3rr4`
