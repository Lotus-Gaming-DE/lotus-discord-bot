"""Regeln für die WoW-Forever-Gilden, ohne Discord und ohne Datenbank.

Der Claim ist der Battle.net-Login in Lotus Link. Punkte gibt es nur für
Fortschritt nach dem Verbinden: Beim ersten Sehen merkt sich der Bot die Stufe
(Ausgangsstand), Meilensteine bis dahin zählen nicht.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from .registry import GuildMember, LinkedCharacter


@dataclass(frozen=True)
class RankLayout:
    """Bedeutung der Rang-Nummern einer Gilde (0 = Gildenmeister).

    Die Blizzard-API liefert nur die Nummer. ``member`` und alles darüber ist
    ein Main-Platz, ``twink`` und alles darüber muss verbunden sein, ``initiate``
    ist die Probezeit.
    """

    names: dict[int, str]
    member: int
    twink: int
    initiate: int
    bank: int | None = None
    officer_twink: int | None = None


# Crimson Lotus laut Gilden-Einstellungen (Screenshot von Gerrit, 9.11.2026).
# Im Spiel heißen sie „Rank 1“ bis „Rank 7“, die API zählt ab 0.
CRIMSON_LAYOUT = RankLayout(
    names={
        0: "Guild Master",
        1: "Officer",
        2: "Officer Twink",
        3: "Veteran",
        4: "Member",
        5: "Twink",
        6: "Initiate",
    },
    member=4,
    twink=5,
    initiate=6,
    officer_twink=2,
)


@dataclass(frozen=True)
class ForeverGuild:
    slug: str
    name: str
    # Discord-Rolle der Gilde. Der Bot vergibt sie an jeden, der einen Char
    # dieser Gilde per Battle.net verbunden hat, und nimmt sie sonst wieder weg.
    role_id: int
    # Farbmarke wie auf www.LotusGaming.de (Menüpunkte: Silent rosa, Crimson rot,
    # Golden blau), damit die Leitungen ihre Meldungen schnell finden.
    icon: str
    # ``None``: Ränge noch nicht abgestimmt. Dann gibt es für diese Gilde keinen
    # Sync-Report, denn ohne Bedeutung der Nummern wäre er falsch.
    layout: RankLayout | None = None
    # Eigene Kanäle der Gilde (Gerrit 23.11.2026). ``None``: der gemeinsame
    # Kanal (#wow-logs bzw. der Daily-Report-Kanal aus den WoW-Einstellungen).
    log_channel_id: int | None = None
    daily_channel_id: int | None = None

    def rank_name(self, rank: int) -> str:
        if self.layout is None:
            return f"Rang {rank + 1}"
        return self.layout.names.get(rank, f"Rang {rank + 1}")

    @property
    def tag(self) -> str:
        return f"{self.icon} **{self.name}**"


# Crimson nutzt die bisherigen gemeinsamen Kanäle, Silent und Golden eigene.
GUILDS: tuple[ForeverGuild, ...] = (
    ForeverGuild(
        "silent-lotus",
        "Silent Lotus",
        1556277083880038501,
        "🩷",
        CRIMSON_LAYOUT,
        log_channel_id=1574469109578465310,
        daily_channel_id=1574466773611184281,
    ),
    ForeverGuild(
        "crimson-lotus", "Crimson Lotus", 1556276890853965884, "❤️", CRIMSON_LAYOUT
    ),
    ForeverGuild(
        "golden-lotus",
        "Golden Lotus",
        1556276986580566027,
        "💙",
        CRIMSON_LAYOUT,
        log_channel_id=1574469381667299398,
        daily_channel_id=1574465048682831892,
    ),
)
GUILDS_BY_SLUG = {g.slug: g for g in GUILDS}

# Blizzard-Klassenschlüssel aus Lotus Link → deutsche Namen.
CLASS_NAMES_DE = {
    "warrior": "Krieger",
    "paladin": "Paladin",
    "hunter": "Jäger",
    "rogue": "Schurke",
    "priest": "Priester",
    "shaman": "Schamane",
    "mage": "Magier",
    "warlock": "Hexenmeister",
    "druid": "Druide",
}

# Stufen-Meilensteine wie bei Black Lotus, um Stufe 20 ergänzt.
LEVEL_MILESTONE_POINTS = {20: 3, 30: 5, 40: 10, 50: 20, 60: 50}
RUN_POINTS = 3
RUN_ORGANIZER_POINTS = 5

# Fortschritt aus Lotus Link (Gerrit, 17.11.2026: „alle vier“). Berufe und
# Itemlevel wie früher bei Black Lotus. Punkte gibt es nur über dem Ausgangsstand.
PROFESSION_SKILL_POINTS = {75: 3, 150: 6, 225: 12, 300: 25}
ITEM_LEVEL_POINTS = {50: 2, 55: 2, 60: 5, 65: 8, 70: 15, 75: 25}
HONORABLE_KILL_POINTS = {100: 3, 500: 6, 1000: 12, 5000: 25, 10000: 50}
# Jeder neue PvP-Rang zählt, höhere mehr.
PVP_RANK_POINTS = {
    r: 3 if r <= 4 else 6 if r <= 8 else 12 if r <= 11 else 25 for r in range(1, 15)
}

# Blizzard liefert englische Berufsnamen.
PROFESSION_NAMES_DE = {
    129: "Erste Hilfe",
    164: "Schmiedekunst",
    165: "Lederverarbeitung",
    171: "Alchemie",
    182: "Kräuterkunde",
    185: "Kochkunst",
    186: "Bergbau",
    197: "Schneiderei",
    202: "Ingenieurskunst",
    333: "Verzauberkunst",
    356: "Angeln",
    393: "Kürschnerei",
}


@dataclass(frozen=True)
class Metric:
    """Ein Fortschrittswert eines Chars, für den es Meilenstein-Punkte gibt.

    ``key`` ist eindeutig je Char (z. B. ``prof:197``), ``kind`` die Art im
    Tagesbericht, ``label`` der Berufsname (sonst leer).
    """

    key: str
    kind: str
    label: str
    value: int
    points: dict[int, int]


def progress_metrics(progress) -> list[Metric]:
    """Alle bekannten Werte. Unbekanntes (``None``) fehlt, statt als 0 zu zählen."""
    if progress is None:
        return []
    metrics: list[Metric] = []
    if progress.average_item_level is not None:
        metrics.append(
            Metric("ilvl", "ilvl", "", progress.average_item_level, ITEM_LEVEL_POINTS)
        )
    if progress.honorable_kills is not None:
        metrics.append(
            Metric("hk", "hk", "", progress.honorable_kills, HONORABLE_KILL_POINTS)
        )
    if progress.pvp_rank is not None:
        metrics.append(
            Metric("pvprank", "pvprank", "", progress.pvp_rank, PVP_RANK_POINTS)
        )
    for profession_id, name, skill in progress.professions:
        label = PROFESSION_NAMES_DE.get(profession_id, name)
        metrics.append(
            Metric(
                f"prof:{profession_id}", "skill", label, skill, PROFESSION_SKILL_POINTS
            )
        )
    return metrics


def thresholds_reached(points: dict[int, int], baseline: int, value: int) -> list[int]:
    return [t for t in sorted(points) if baseline < t <= value]


def lotus_guild_of(
    char: LinkedCharacter, roster_guild: dict[int, str]
) -> ForeverGuild | None:
    """Die Gildenliste ist stündlich frisch, das Charakterprofil täglich."""
    slug = roster_guild.get(char.blizzard_id) or char.guild_slug
    return GUILDS_BY_SLUG.get(slug) if slug else None


def role_guild_of(
    char: LinkedCharacter,
    roster_guild: dict[int, str],
    rosters_loaded: frozenset[str],
) -> ForeverGuild | None:
    """Gilde, deren Rolle dieser Char verdient (strenger als ``lotus_guild_of``).

    Liegt die Gildenliste vor, entscheidet nur sie: Wer dort fehlt, ist raus,
    auch wenn das bis zu einen Tag alte Charakterprofil noch die Gilde nennt.
    """
    slug = roster_guild.get(char.blizzard_id)
    if slug is None and char.guild_slug not in rosters_loaded:
        slug = char.guild_slug
    return GUILDS_BY_SLUG.get(slug) if slug else None


def role_holders(
    linked: tuple[LinkedCharacter, ...] | list[LinkedCharacter],
    members: tuple[GuildMember, ...] | list[GuildMember],
    rosters_loaded: frozenset[str],
    absent: set[int] | frozenset[int] = frozenset(),
) -> dict[str, set[int]]:
    """Discord-Nutzer je Gilde, die die Gildenrolle haben sollen."""
    roster_guild = {m.blizzard_id: m.guild_slug for m in members}
    holders: dict[str, set[int]] = {g.slug: set() for g in GUILDS}
    for char in linked:
        if char.discord_user_id in absent:
            continue
        guild = role_guild_of(char, roster_guild, rosters_loaded)
        if guild is not None:
            holders[guild.slug].add(char.discord_user_id)
    return holders


def roster_is_plausible(previous: int, current: int) -> bool:
    """Schützt vor Massen-Austritten durch eine kaputte oder leere Liste."""
    if current == 0:
        return previous == 0
    return previous < 10 or current * 2 >= previous


def class_name(class_key: str | None) -> str:
    if not class_key:
        return ""
    return CLASS_NAMES_DE.get(class_key, class_key.capitalize())


def char_details(member: GuildMember | None, guild: ForeverGuild) -> str:
    """``Level 42 Krieger, Member`` für Meldungen."""
    if member is None:
        return "nicht in der Gildenliste"
    parts = [f"Level {member.level}"]
    if class_name(member.class_key):
        parts[0] += f" {class_name(member.class_key)}"
    parts.append(guild.rank_name(member.rank))
    return ", ".join(parts)


def milestones_reached(baseline: int, level: int) -> list[int]:
    """Meilensteine, die nach dem Verbinden erreicht wurden."""
    return [m for m in sorted(LEVEL_MILESTONE_POINTS) if baseline < m <= level]


@dataclass
class GuildReport:
    guild: ForeverGuild
    unlinked_ranked: list[GuildMember] = field(default_factory=list)
    linked_initiates: list[tuple[GuildMember, int]] = field(default_factory=list)
    no_main: list[tuple[int, list[GuildMember]]] = field(default_factory=list)
    multi_main: list[tuple[int, list[GuildMember]]] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (
            self.unlinked_ranked
            or self.linked_initiates
            or self.no_main
            or self.multi_main
        )


def build_report(
    guild: ForeverGuild,
    members: list[GuildMember],
    owner_of: dict[int, int],
) -> GuildReport:
    """Vergleicht Gildenränge mit Battle.net-Verbindungen.

    ``owner_of`` bildet die Blizzard-ID verbundener Chars auf den Discord-Nutzer ab.
    """
    layout = guild.layout
    report = GuildReport(guild)
    if layout is None:
        return report
    by_user: dict[int, list[GuildMember]] = {}
    for member in members:
        owner = owner_of.get(member.blizzard_id)
        if owner is None:
            if member.rank <= layout.twink:
                report.unlinked_ranked.append(member)
            continue
        if member.rank == layout.initiate:
            report.linked_initiates.append((member, owner))
        by_user.setdefault(owner, []).append(member)

    for owner, chars in by_user.items():
        mains = [m for m in chars if is_main_rank(m.rank, layout)]
        if len(mains) > 1:
            report.multi_main.append((owner, sorted(mains, key=lambda m: m.rank)))
        if any(m.rank <= layout.member for m in chars):
            continue
        alts = {layout.twink, layout.bank} - {None}
        if any(m.rank in alts for m in chars):
            ordered = sorted(chars, key=lambda m: (-m.level, m.rank, m.name.casefold()))
            report.no_main.append((owner, ordered))

    report.unlinked_ranked.sort(key=lambda m: (m.rank, m.name.casefold()))
    report.linked_initiates.sort(key=lambda pair: pair[0].name.casefold())
    report.no_main.sort(key=lambda pair: pair[0])
    report.multi_main.sort(key=lambda pair: pair[0])
    return report


def mention(user_id: int) -> str:
    return f"<@{user_id}>"


def report_sections(
    report: GuildReport, name_of: Callable[[int], str] = mention
) -> list[tuple[str | None, list[str]]]:
    """``name_of`` macht aus einer Discord-ID den angezeigten Text."""
    guild = report.guild
    sections: list[tuple[str | None, list[str]]] = []
    if report.unlinked_ranked:
        sections.append(
            (
                f"{guild.icon} **{guild.name}: Twink+ ohne Battle.net-Claim**, verbinden lassen "
                "oder auf Initiate runterstufen:",
                [
                    f"- **{m.name}** ({guild.rank_name(m.rank)}, Level {m.level})"
                    for m in report.unlinked_ranked
                ],
            )
        )
    if report.linked_initiates:
        sections.append(
            (
                f"{guild.icon} **{guild.name}: verbunden, aber noch Initiate**, auf Twink/Member "
                "hochstufen (NICHT kicken!):",
                [
                    f"- **{m.name}** (Level {m.level}) - {name_of(owner)}"
                    for m, owner in report.linked_initiates
                ],
            )
        )
    if report.no_main:
        sections.append(
            (
                f"{guild.icon} **{guild.name}: Twink/Bank ohne Main**, höchsten Char (zuerst "
                "gelistet) zum Member befördern:",
                [
                    f"- {name_of(owner)}: "
                    + ", ".join(
                        f"**{m.name}** ({guild.rank_name(m.rank)}, Level {m.level})"
                        for m in chars
                    )
                    for owner, chars in report.no_main
                ],
            )
        )
    if report.multi_main:
        sections.append(
            (
                f"{guild.icon} **{guild.name}: mehr als ein Main-Char**, nur einer soll Member+ "
                "sein, Rest auf Twink:",
                [
                    f"- {name_of(owner)}: "
                    + ", ".join(
                        f"**{m.name}** ({guild.rank_name(m.rank)})" for m in chars
                    )
                    for owner, chars in report.multi_main
                ],
            )
        )
    return sections


def link_notice(
    char: LinkedCharacter,
    guild: ForeverGuild,
    member: GuildMember | None,
    *,
    discord_name: str | None = None,
    others: list[GuildMember] | None = None,
    name_of: Callable[[int], str] = mention,
) -> str:
    """Meldung für einen neu verbundenen Char, mit Rang-Empfehlung.

    ``others`` sind die übrigen verbundenen Chars desselben Nutzers in dieser
    Gilde. Hat er schon einen Main-Platz, ist der neue Char vermutlich ein Twink.
    """
    if member is not None:
        details = char_details(member, guild)
    else:
        details = f"Level {char.level}, noch nicht in der Gildenliste"
    lines = [
        f"{guild.tag} · 🔗 Neuer Claim",
        f"{name_of(char.discord_user_id)} hat **{char.name}** per Battle.net verbunden "
        f"({details}).",
    ]
    if discord_name:
        lines.append(f"Für die Offi-Note: `{discord_name}`")
    layout = guild.layout
    others = sorted(others or [], key=lambda m: (m.rank, -m.level, m.name.casefold()))
    if others:
        lines.append("Weitere verbundene Chars in dieser Gilde:")
        lines.extend(f"- **{m.name}** ({char_details(m, guild)})" for m in others)
    if layout is None:
        return "\n".join(lines)  # Ränge noch nicht abgestimmt, keine Empfehlung
    has_main = any(is_main_rank(m.rank, layout) for m in others)
    on_main = member is not None and is_main_rank(member.rank, layout)
    if on_main and has_main:
        lines.append(
            "➡️ Hat schon einen Main-Platz, dieser Char steht aber auch auf einem "
            f"Main-Rang (**{guild.rank_name(member.rank)}**). Einer von beiden "
            "sollte **Twink** werden."
        )
    elif on_main:
        lines.append(
            "✅ Steht schon auf einem Main-Rang "
            f"(**{guild.rank_name(member.rank)}**), der Rang passt so."
        )
    elif has_main:
        lines.append(
            "➡️ Hat schon einen Main-Platz, dieser Char ist wohl ein **Twink**."
        )
    else:
        lines.append("➡️ Noch kein Main-Platz, dieser Char wird der **Member**-Char.")
    return "\n".join(lines)


def is_main_rank(rank: int, layout: RankLayout) -> bool:
    """Gildenmeister, Officer, Veteran und Member sind Main-Ränge.

    Officer Twink steht zwar über Member, ist aber ein Twink.
    """
    return rank <= layout.member and rank != layout.officer_twink


def guild_left_notice(
    guild: ForeverGuild,
    member: GuildMember,
    *,
    owner_id: int | None,
    listed_since: str | None,
    moved_to: ForeverGuild | None,
    name_of: Callable[[int], str] = mention,
) -> str:
    """Ein Char steht nicht mehr in der Gildenliste (gekickt, gegangen, gewechselt)."""
    lines = [
        f"{guild.tag} · 🚪 **{member.name}** ist nicht mehr in der Gilde.",
        f"• {char_details(member, guild)}",
        f"• Claim: {name_of(owner_id)}" if owner_id else "• Claim: _nicht verbunden_",
    ]
    if moved_to is not None:
        lines.append(f"• Jetzt in: {moved_to.tag}")
    if listed_since:
        lines.append(f"• Bei uns gelistet seit: **{listed_since[:10]}**")
    return "\n".join(lines)


def discord_left_notice(
    guild: ForeverGuild,
    user_id: int,
    chars: list[GuildMember],
    name_of: Callable[[int], str] = mention,
) -> str:
    """Wer Discord verlässt, verliert seine Plätze in der Gilde."""
    ordered = sorted(chars, key=lambda m: (m.rank, m.name.casefold()))
    return "\n".join(
        [
            f"{guild.tag} · ⬇️ {name_of(user_id)} hat den Discord verlassen.",
            "Bitte diese Chars in-game auf den niedrigsten Rang runterstufen:",
            *(f"- **{m.name}** ({char_details(m, guild)})" for m in ordered),
        ]
    )


def ping_text(
    guild: ForeverGuild,
    rows: list[tuple[int, str, str]],
    open_total: int,
    jump_url,
    max_links: int = 10,
) -> str:
    """Gesammelter Ping an die Gildenrolle für neue, offene Meldungen.

    ``rows`` sind (Nachrichten-ID, Art, Name), ``jump_url`` baut den Link.
    """
    claims = sum(1 for _, kind, _ in rows if kind == "link")
    demotes = sum(1 for _, kind, _ in rows if kind == "discord_left")
    parts = []
    if claims:
        parts.append("1 neuer Claim" if claims == 1 else f"{claims} neue Claims")
    if demotes:
        parts.append(
            "1 Discord-Austritt zum Runterstufen"
            if demotes == 1
            else f"{demotes} Discord-Austritte zum Runterstufen"
        )
    lines = [
        f"🔔 <@&{guild.role_id}> {guild.tag}: {' · '.join(parts)}. "
        "Bitte per Button abhaken, wenn es im Spiel erledigt ist."
    ]
    for message_id, _, label in rows[:max_links]:
        lines.append(f"- [{label}]({jump_url(message_id)})")
    if len(rows) > max_links:
        lines.append(f"- … und {len(rows) - max_links} weitere")
    if open_total > len(rows):
        lines.append(f"-# Insgesamt offen: {open_total}")
    return "\n".join(lines)


def daily_sections(
    guild: ForeverGuild,
    events: list,
    roster_size: int,
    linked_count: int,
    name_of: Callable[[int], str] = mention,
) -> list[tuple[str | None, list[str]]]:
    """Tagesbericht einer Gilde für den Daily-Report-Kanal.

    ``events`` sind die ``DailyEvent`` seit dem letzten Bericht. Ohne Ereignis
    gibt es keinen Bericht (leere Liste), damit der Kanal ruhig bleibt.
    """
    if not events:
        return []

    def tail(user_id: int | None, points: int = 0) -> str:
        if user_id is None:
            return ""
        bonus = f" (+{points} Champion-Punkte)" if points else ""
        return f" - {name_of(user_id)}{bonus}"

    head = [f"{guild.tag} · 📰 **Tagesbericht**"]
    if roster_size:
        head.append(
            f"-# {roster_size} Chars in der Gilde, {linked_count} davon "
            "per Lotus Link verbunden"
        )
    sections: list[tuple[str | None, list[str]]] = [(None, head)]

    joined = sorted(
        (e for e in events if e.kind == "joined"),
        key=lambda e: (-e.value, e.name.casefold()),
    )
    if joined:
        sections.append(
            (
                "**Herzlich willkommen in der Gilde** 👋",
                [
                    f"- **{e.name}** (Level {e.value}"
                    + (f" {e.detail}" if e.detail else "")
                    + ")"
                    + tail(e.discord_user_id)
                    for e in joined
                ],
            )
        )

    linked = sorted(
        (e for e in events if e.kind == "link"), key=lambda e: e.name.casefold()
    )
    if linked:
        sections.append(
            (
                "**Neu mit Lotus Link verbunden** 🔗",
                [f"- **{e.name}**{tail(e.discord_user_id)}" for e in linked],
            )
        )

    # Mehrere Meilensteine eines Chars in einer Zeile, Punkte zusammengezählt.
    levels: dict[tuple[str, int | None], list] = {}
    for e in events:
        if e.kind == "level":
            levels.setdefault((e.name, e.discord_user_id), []).append(e)
    if levels:
        rows = sorted(
            (
                (max(x.value for x in group), sum(x.points for x in group), name, uid)
                for (name, uid), group in levels.items()
            ),
            key=lambda row: (-row[0], row[2].casefold()),
        )
        sections.append(
            (
                "**Glückwunsch zu diesen Meilensteinen** 🏆",
                [
                    f"- **{name}** hat Level **{level}** erreicht{tail(uid, pts)}"
                    for level, pts, name, uid in rows
                ],
            )
        )

    sections.extend(_progress_sections(events, tail))

    runs: dict[int, list] = {}
    for e in events:
        if e.kind == "run" and e.discord_user_id is not None:
            runs.setdefault(e.discord_user_id, []).append(e)
    if runs:
        lines = []
        for uid, group in sorted(runs.items(), key=lambda item: -len(item[1])):
            led = sum(1 for e in group if e.value)
            count = "1 Run" if len(group) == 1 else f"{len(group)} Runs"
            if led:
                count += f", davon {led} geleitet"
            pts = sum(e.points for e in group)
            lines.append(
                f"- {name_of(uid)}: {count} (+{pts} Champion-Punkte)",
            )
        sections.append(("**Dungeon-Runs mit Lotus Link** ⚔️", lines))
    return sections


PROGRESS_HEADERS = (
    ("skill", "**Berufe-Meilensteine** ⚒️"),
    ("hk", "**PvP: ehrenhafte Siege** ⚔️"),
    ("pvprank", "**PvP: neuer Rang** 🎖️"),
    ("ilvl", "**Ausrüstungs-Meilensteine** 🛡️"),
)


def _progress_sections(events: list, tail) -> list[tuple[str | None, list[str]]]:
    """Eine Zeile je Char und Wert: höchster Meilenstein, Punkte zusammengezählt."""
    sections: list[tuple[str | None, list[str]]] = []
    for kind, header in PROGRESS_HEADERS:
        grouped: dict[tuple[str, str, int | None], list] = {}
        for e in events:
            if e.kind == kind:
                grouped.setdefault((e.name, e.detail, e.discord_user_id), []).append(e)
        if not grouped:
            continue
        rows = sorted(
            (
                (
                    max(x.value for x in group),
                    sum(x.points for x in group),
                    name,
                    detail,
                    uid,
                )
                for (name, detail, uid), group in grouped.items()
            ),
            key=lambda row: (-row[0], row[2].casefold()),
        )
        lines = []
        for value, pts, name, detail, uid in rows:
            if kind == "skill":
                text = f"**{name}**: {detail} auf **{value}**"
            elif kind == "hk":
                text = f"**{name}** hat **{value:,}** ehrenhafte Siege".replace(
                    ",", "."
                )
            elif kind == "pvprank":
                text = f"**{name}** hat PvP-Rang **{value}** erreicht"
            else:
                text = (
                    f"**{name}** hat ein durchschnittliches Itemlevel von **{value}**"
                )
            lines.append(f"- {text}{tail(uid, pts)}")
        sections.append((header, lines))
    return sections
