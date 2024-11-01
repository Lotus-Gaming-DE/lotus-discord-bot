![Logo von Lotus Gaming](/data/LotusGamingColorless.png)
# Lotus Gaming Discord Bot!


Willkommen zum **Lotus Gaming Discord Bot** Projekt! Dieser Bot wurde entwickelt, um das Spielerlebnis innerhalb unserer Community zu verbessern, indem er nützliche Funktionen und Interaktionen rund um unsere Lieblingsspiele bereitstellt. Der Bot ist modular aufgebaut, was eine einfache Erweiterung und Wartung verschiedener Funktionen ermöglicht.

## Inhaltsverzeichnis

- [Übersicht](#übersicht)
- [Funktionen](#funktionen)
  - [Warcraft Rumble (WCR) Modul](#warcraft-rumble-wcr-modul)
- [Nutzung](#nutzung)
- [Befehle](#befehle)
  - [/filter](#/filter)
  - [/name](#/name)
- [Kontakt](#kontakt)
- [Empfohlene Bilder](#empfohlene-bilder)

## Übersicht

Der Bot konzentriert sich derzeit darauf, detaillierte Informationen und Tools für **Warcraft Rumble (WCR)** Spieler bereitzustellen. Er ist live und wird aktiv auf unserem Discord-Server genutzt: [discord.gg/LotusGaming](https://discord.gg/LotusGaming).

## Funktionen

### Warcraft Rumble (WCR) Modul

Das **WCR-Modul** bietet eine Reihe von Befehlen, die Spielern helfen, Spieldaten effizient abzurufen:

- **Filtern von Minis**: Mit dem Befehl `/filter` kannst du Minis basierend auf spezifischen Kriterien wie Kosten, Geschwindigkeit, Fraktion, Typ, Merkmal und Sprache suchen.
- **Detaillierte Informationen zu Minis**: Der Befehl `/name` liefert umfassende Details zu einem bestimmten Mini, einschließlich Statistiken, Talenten, Merkmalen und Bildern.
- **Autocomplete-Unterstützung**: Befehle bieten Autocomplete-Vorschläge, um die Eingabe schneller und präziser zu gestalten.
- **Mehrsprachige Unterstützung**: Das Modul unterstützt mehrere Sprachen, derzeit Deutsch (`de`) und Englisch (`en`), um einer vielfältigen Nutzerbasis gerecht zu werden. Deutsch ist die Standardsprache.
- **Permutationssuche**: Du kannst Minis auch dann finden, wenn du ihren Namen nicht exakt kennst. Der Bot erkennt Permutationen und findet Minis auch in anderen Sprachen.

**Hinweis:** Nach der Auswahl eines Minis im Popup erhältst du ein Embed mit den detaillierten Informationen zum Mini.

## Nutzung

### Befehle

#### `/filter`

Filtere Minis basierend auf verschiedenen Kriterien.

**Verwendung:**

```bash
/filter cost:<Wert> speed:<Wert> faction:<Wert> type:<Wert> trait:<Wert> lang:<Wert>
```

**Parameter:**

- `cost` (optional): Die Kosten des Minis.
- `speed` (optional): Die Geschwindigkeitskategorie des Minis.
- `faction` (optional): Die Fraktion, zu der das Mini gehört.
- `type` (optional): Der Typ des Minis (z.B. Truppe, Held).
- `trait` (optional): Spezifische Merkmale des Minis.
- `lang` (optional): Sprache für die Antwort (`de` oder `en`). Standard ist `de`.

**Beispiel:**

```bash
/filter faction:Allianz type:Fernkämpfer lang:de
```

Dieser Befehl liefert eine Liste von Fernkämpfer-Minis aus der Fraktion Allianz, angezeigt auf Deutsch.

**Ablauf:**

1. Nach Eingabe des Befehls erscheint ein Popup mit einer Liste der gefilterten Minis.
2. Nach Auswahl eines Minis erhältst du ein Embed mit den detaillierten Informationen zum Mini.

#### `/name`

Erhalte detaillierte Informationen zu einem spezifischen Mini anhand des Namens oder der ID.

**Verwendung:**

```bash
/name name:<mini_name_or_id> lang:<Wert>
```

**Parameter:**

- `name`: Der Name oder die ID des Minis. Dank der Permutationssuche kannst du Minis auch finden, wenn du den Namen nicht exakt kennst.
- `lang` (optional): Sprache für die Antwort (`de` oder `en`). Standard ist `de`.

**Beispiel:**

```bash
/name name:"S.A.F.E. Pilot" lang:de
```

Dieser Befehl zeigt detaillierte Informationen zum Mini "S.A.F.E. Pilot" auf Deutsch an.

**Hinweis zu Permutationen:**

Du kannst Teile des Namens oder verschiedene Wortreihenfolgen verwenden, und der Bot versucht, das passende Mini zu finden.  
**Beispiel:** Selbst wenn du "Pilot S.A.F.E." eingibst, wird der Bot das richtige Mini finden.

## Kontakt

Für weitere Informationen oder wenn du Fragen hast, kannst du dich gerne melden:

- **Discord Server**: [Lotus Gaming](https://discord.gg/LotusGaming)
- **Discord Benutzer**: gs3rr4 (Discord User ID: 163375118096007168)
- **E-Mail**: [lotusgamingde@gmail.com](mailto:lotusgamingde@gmail.com)

Wir freuen uns auf deine Teilnahme und dein Feedback!
