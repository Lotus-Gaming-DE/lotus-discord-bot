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
    # ``None``: Ränge noch nicht abgestimmt. Dann gibt es für diese Gilde keinen
    # Sync-Report, denn ohne Bedeutung der Nummern wäre er falsch.
    layout: RankLayout | None = None

    def rank_name(self, rank: int) -> str:
        if self.layout is None:
            return f"Rang {rank + 1}"
        return self.layout.names.get(rank, f"Rang {rank + 1}")


GUILDS: tuple[ForeverGuild, ...] = (
    ForeverGuild("silent-lotus", "Silent Lotus"),
    ForeverGuild("crimson-lotus", "Crimson Lotus", CRIMSON_LAYOUT),
    ForeverGuild("golden-lotus", "Golden Lotus"),
)
GUILDS_BY_SLUG = {g.slug: g for g in GUILDS}

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
                f"**{guild.name}: Twink+ ohne Battle.net-Claim**, verbinden lassen "
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
                f"**{guild.name}: verbunden, aber noch Initiate**, auf Twink/Member "
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
                f"**{guild.name}: Twink/Bank ohne Main**, höchsten Char (zuerst "
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
                f"**{guild.name}: mehr als ein Main-Char**, nur einer soll Member+ "
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
    char: LinkedCharacter, guild: ForeverGuild, member: GuildMember | None
) -> str:
    rank = guild.rank_name(member.rank) if member else "Rang unbekannt"
    level = member.level if member else char.level
    return (
        f"🔗 <@{char.discord_user_id}> hat **{char.name}** per Battle.net verbunden "
        f"({guild.name}, {rank}, Level {level})."
    )
