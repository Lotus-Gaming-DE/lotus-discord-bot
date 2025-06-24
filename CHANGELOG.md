# Changelog

## [Unreleased]
- Verbessertes Shutdown-Verhalten: ChampionCog schließt jetzt zuerst die Datenbank und stoppt danach alle Tasks.
## Unreleased
- Refaktor: `cmd_duel` nutzt nun `_compute_duel_outcome` und die neue `DuelOutcome`-Dataclass.
- ChampionCog besitzt nun eine begrenzte Update-Warteschlange (1000 Einträge);
  beim Füllen wird ein ``QueueFull``-Fehler geloggt.

