"""Regeln für die WoW-Forever-Gilden, ohne Discord und ohne Datenbank.

Der Claim ist der Battle.net-Login in Lotus Link. Punkte gibt es nur für
Fortschritt nach dem Verbinden: Beim ersten Sehen merkt sich der Bot die Stufe
(Ausgangsstand), Meilensteine bis dahin zählen nicht.
"""

from __future__ import annotations

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

    def rank_name(self, rank: int) -> str:
        if self.layout is None:
            return f"Rang {rank + 1}"
        return self.layout.names.get(rank, f"Rang {rank + 1}")

    @property
    def tag(self) -> str:
        return f"{self.icon} **{self.name}**"


GUILDS: tuple[ForeverGuild, ...] = (
    ForeverGuild("silent-lotus", "Silent Lotus", 1556277083880038501, "🩷"),
    ForeverGuild(
        "crimson-lotus", "Crimson Lotus", 1556276890853965884, "❤️", CRIMSON_LAYOUT
    ),
    ForeverGuild(
        "golden-lotus", "Golden Lotus", 1556276986580566027, "💙", CRIMSON_LAYOUT
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
        mains = [
            m
            for m in chars
            if m.rank <= layout.member and m.rank != layout.officer_twink
        ]
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


def report_sections(report: GuildReport) -> list[tuple[str | None, list[str]]]:
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
                    f"- **{m.name}** (Level {m.level}) - <@{owner}>"
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
                    f"- <@{owner}>: "
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
                    f"- <@{owner}>: "
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
        f"<@{char.discord_user_id}> hat **{char.name}** per Battle.net verbunden "
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
    has_main = any(
        m.rank <= layout.member and m.rank != layout.officer_twink for m in others
    )
    if has_main:
        lines.append(
            "➡️ Hat schon einen Main-Platz, dieser Char ist wohl ein **Twink**."
        )
    else:
        lines.append("➡️ Noch kein Main-Platz, dieser Char wird der **Member**-Char.")
    return "\n".join(lines)


def guild_left_notice(
    guild: ForeverGuild,
    member: GuildMember,
    *,
    owner_id: int | None,
    listed_since: str | None,
    moved_to: ForeverGuild | None,
) -> str:
    """Ein Char steht nicht mehr in der Gildenliste (gekickt, gegangen, gewechselt)."""
    lines = [
        f"{guild.tag} · 🚪 **{member.name}** ist nicht mehr in der Gilde.",
        f"• {char_details(member, guild)}",
        f"• Claim: <@{owner_id}>" if owner_id else "• Claim: _nicht verbunden_",
    ]
    if moved_to is not None:
        lines.append(f"• Jetzt in: {moved_to.tag}")
    if listed_since:
        lines.append(f"• Bei uns gelistet seit: **{listed_since[:10]}**")
    return "\n".join(lines)


def discord_left_notice(
    guild: ForeverGuild, user_id: int, chars: list[GuildMember]
) -> str:
    """Wer Discord verlässt, verliert seine Plätze in der Gilde."""
    ordered = sorted(chars, key=lambda m: (m.rank, m.name.casefold()))
    return "\n".join(
        [
            f"{guild.tag} · ⬇️ <@{user_id}> hat den Discord verlassen.",
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
