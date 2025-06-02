![Logo von Lotus Gaming](./data/LotusGamingColorless.png)

# Lotus Gaming Discord Bot

Willkommen beim **Lotus Gaming Discord Bot**!  
Dieser modulare Discord-Bot wurde für die **Lotus Gaming Community** entwickelt. Er bietet dynamische Quiz-Events, ein Champion-Punktesystem zur Anerkennung aktiver Mitglieder und umfassende Datenabfragen zu Warcraft Rumble.

## Zielgruppe

Diese Dokumentation richtet sich an:
- **Mods/Admins**, die Slash-Commands im Discord verstehen und verwenden wollen.
- **Entwickler**, die zur Weiterentwicklung beitragen möchten.

---

## Inhaltsverzeichnis

- [Übersicht & Module](#übersicht--module)
- [Projektstruktur](#projektstruktur)
- [Slash-Commands](#slash-commands)
- [Technische Konzepte](#technische-konzepte)
- [Änderungsprotokoll](#änderungsprotokoll)
- [Kontakt](#kontakt)

---

## Übersicht & Module

Der Bot ist in folgende Module unterteilt:

| Modul     | Zweck                                               |
|-----------|-----------------------------------------------------|
| `quiz`    | Automatisierte Quizfragen je Spielbereich (z. B. D4, WCR) |
| `champion`| Vergabe & Tracking von Community-Punkten            |
| `wcr`     | WCR-spezifische Filter- & Infoabfragen              |

Jede Funktion ist vollständig über **Slash-Commands** steuerbar.

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
│  │  └─ ...
│  ├─ quiz/
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
│     └─ ...
├─ data/
│  ├─ champion/
│  ├─ quiz/
│  ├─ wcr/
│  ├─ media/
│  └─ pers/
│     ├─ champion/
│     └─ quiz/
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

- Modularer Aufbau mit sauber gekapselten Cogs
- Slash-Command-Gruppierung (`/quiz`, `/wcr`, `/champion`)
- Detailliertes, zustandsorientiertes Logging jeder Veränderung
- Nachrichtenzähler pro Channel für Aktivitätsprüfung
- Dynamische und statische Fragen (z. B. bei WCR)
- Automatische Frageplanung basierend auf Intervall & Aktivität
- Antwortabgabe via Discord-Modal
- Berechtigungsprüfungen für Mod-Only-Befehle
- Persistente Daten (aktive Fragen, Punktestände) liegen in `data/pers/`, getrennt von statischen Inhalten in `data/`.

---

## Änderungsprotokoll (Stand 2025-06-02)

- ✅ **Quiz-Modul vollständig modularisiert**
  - Aufteilung in Scheduler, Closer, Manager, State, Tracker, Generator, Restorer
- ✅ **Slash-Command-Handling in allen Cogs vereinheitlicht**
- ✅ **Logging überarbeitet**
  - Jede Zustandsänderung wird geloggt
  - Automatische Fragenankündigung und Begründung bei Nicht-Stellen
- ✅ **Antwortvalidierung verbessert** (inkl. Fuzzy Matching & Unicode-Normalisierung)
- ✅ **Einführung von `data/pers/`** als persistenter Speicher für aktive Fragen und Punktezähler
- ✅ **Neues Berechtigungssystem für Slash-Commands** (Mod-Only Absicherung)
- ✅ **Alle bestehenden Befehle lauffähig und vollständig implementiert**
- 🔜 **Geplant: Modularisierung und Optimierung des `wcr`-Moduls**

---

## Kontakt

- **Projektleitung & Hauptentwickler**: `gs3rr4`
- **Discord**: [discord.gg/LotusGaming](https://discord.gg/LotusGaming)
- **E-Mail**: [lotusgamingde@gmail.com](mailto:lotusgamingde@gmail.com)

---

Letzter Stand: 2025-06-02  
Verantwortlich für diesen Stand: `gs3rr4`
