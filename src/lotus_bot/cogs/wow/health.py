"""Selbstcheck: Darf der Bot in seinen Channels, was er dort tun muss?

Fehlende Rechte fallen sonst erst auf, wenn etwas fehlt — so sind Claims
„verschwunden", weil der Bot im neuen Offi-Channel nicht schreiben durfte.
``/wow doctor`` und der Check beim Start machen solche Lücken sofort sichtbar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from lotus_bot.cogs.community.cog import PANEL_CHANNEL_ID as COMMUNITY_PANEL_CHANNEL_ID

from .cog import DEFAULT_PANEL_CHANNEL_ID, DUNGEONS_FORUM_CHANNEL_ID, GUILD_ROLE_ID
from .duo_cog import DUO_FORUM_CHANNEL_ID
from .marketplace_cog import MARKETPLACE_FORUM_CHANNEL_ID

if TYPE_CHECKING:  # pragma: no cover
    from .cog import WoWCog

PERMISSION_LABELS = {
    "view_channel": "Kanal sehen",
    "send_messages": "Nachrichten senden / Beiträge erstellen",
    "send_messages_in_threads": "In Threads schreiben",
    "embed_links": "Links einbetten",
    "read_message_history": "Nachrichtenverlauf lesen",
    "attach_files": "Dateien anhängen",
    "manage_threads": "Threads verwalten",
}

# Text-Channels: posten, Embeds, eigene Nachrichten wiederfinden und bearbeiten.
TEXT_CHANNEL = ("view_channel", "send_messages", "embed_links", "read_message_history")
# Foren zusätzlich: in Beiträgen schreiben, Beiträge anpinnen/taggen/archivieren.
FORUM_CHANNEL = TEXT_CHANNEL + ("send_messages_in_threads", "manage_threads")
# Der Offi-Channel bekommt außerdem das wöchentliche Backup als Datei.
UPLOADS = ("attach_files",)


@dataclass(frozen=True)
class ChannelRequirement:
    label: str
    channel_id: int | None
    permissions: tuple[str, ...]


@dataclass
class ChannelCheck:
    label: str
    channel_id: int | None
    mention: str | None = None
    problem: str | None = None
    missing: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.problem is None and not self.missing


@dataclass
class RoleCheck:
    label: str
    role_id: int
    problem: str | None = None

    @property
    def ok(self) -> bool:
        return self.problem is None


@dataclass
class HealthReport:
    channels: list[ChannelCheck]
    roles: list[RoleCheck]
    guild_problem: str | None = None

    @property
    def problems(self) -> list[str]:
        problems = [self.guild_problem] if self.guild_problem else []
        for check in self.channels:
            if check.problem:
                problems.append(f"{check.label}: {check.problem}")
            elif check.missing:
                labels = ", ".join(_permission_label(p) for p in check.missing)
                problems.append(f"{check.label}: fehlt {labels}")
        problems += [f"{r.label}: {r.problem}" for r in self.roles if r.problem]
        return problems

    @property
    def ok(self) -> bool:
        return not self.problems


def _permission_label(name: str) -> str:
    return PERMISSION_LABELS.get(name, name)


def missing_permissions(permissions, required: tuple[str, ...]) -> list[str]:
    return [name for name in required if not getattr(permissions, name, False)]


def check_channel(guild, requirement: ChannelRequirement) -> ChannelCheck:
    check = ChannelCheck(requirement.label, requirement.channel_id)
    if requirement.channel_id is None:
        check.problem = "nicht eingerichtet"
        return check
    channel = guild.get_channel(requirement.channel_id)
    if channel is None:
        check.problem = (
            "Channel nicht gefunden — gelöscht, oder der Bot sieht ihn nicht"
        )
        return check
    check.mention = getattr(channel, "mention", None)
    check.missing = missing_permissions(
        channel.permissions_for(guild.me), requirement.permissions
    )
    return check


def check_role(guild, label: str, role_id: int) -> RoleCheck:
    check = RoleCheck(label, role_id)
    role = guild.get_role(role_id)
    if role is None:
        check.problem = "Rolle existiert nicht mehr"
        return check
    top_role = getattr(guild.me, "top_role", None)
    if top_role is not None and role.position >= top_role.position:
        check.problem = (
            "steht über der Bot-Rolle, der Bot kann sie nicht vergeben "
            "(Bot-Rolle in den Servereinstellungen nach oben ziehen)"
        )
    return check


def build_report(
    guild,
    channels: list[ChannelRequirement],
    roles: list[tuple[str, int]],
) -> HealthReport:
    guild_permissions = getattr(guild.me, "guild_permissions", None)
    guild_problem = (
        None
        if getattr(guild_permissions, "manage_roles", False)
        else 'Server-Berechtigung „Rollen verwalten" fehlt'
    )
    return HealthReport(
        channels=[check_channel(guild, requirement) for requirement in channels],
        roles=[check_role(guild, label, role_id) for label, role_id in roles],
        guild_problem=guild_problem,
    )


async def channel_requirements(wow: "WoWCog") -> list[ChannelRequirement]:
    return [
        ChannelRequirement(
            "Offi-Logs (Claims, Reports, Backups)",
            await wow.get_claim_review_channel_id(),
            TEXT_CHANNEL + UPLOADS,
        ),
        ChannelRequirement(
            "Daily-Digest", await wow.get_announcement_channel_id(), TEXT_CHANNEL
        ),
        ChannelRequirement("WoW-Panel", DEFAULT_PANEL_CHANNEL_ID, TEXT_CHANNEL),
        ChannelRequirement(
            "Dungeon-Guide (Forum)", DUNGEONS_FORUM_CHANNEL_ID, FORUM_CHANNEL
        ),
        ChannelRequirement("WoW-Duo (Forum)", DUO_FORUM_CHANNEL_ID, FORUM_CHANNEL),
        ChannelRequirement(
            "Marktplatz (Forum)", MARKETPLACE_FORUM_CHANNEL_ID, FORUM_CHANNEL
        ),
        ChannelRequirement("Community-Panel", COMMUNITY_PANEL_CHANNEL_ID, TEXT_CHANNEL),
    ]


def role_requirements(bot) -> list[tuple[str, int]]:
    """Rollen, die der Bot selbst vergibt — nur die müssen unter seiner stehen."""
    roles = [("Gilden-Rolle", GUILD_ROLE_ID)]
    data = getattr(bot, "data", None) or {}
    for entry in data.get("champion", {}).get("roles", []):
        role_id = int(entry.get("id") or 0)
        if role_id:
            roles.append((f"Champion-Rolle {entry.get('name', role_id)}", role_id))
    return roles


async def run_health_check(wow: "WoWCog") -> HealthReport | None:
    """``None``, solange die Guild noch nicht geladen ist."""
    guild = wow._main_guild()
    if guild is None:
        return None
    return build_report(
        guild, await channel_requirements(wow), role_requirements(wow.bot)
    )


def format_report(report: HealthReport) -> str:
    problems = report.problems
    if problems:
        header = f"🩺 **Bot-Check** — {len(problems)} Problem(e) gefunden"
    else:
        header = "🩺 **Bot-Check** — alles in Ordnung ✅"
    lines = [header, "", "**Channels**"]
    for check in report.channels:
        where = check.mention or (f"`{check.channel_id}`" if check.channel_id else "")
        name = f"{check.label} {where}".strip()
        if check.ok:
            lines.append(f"✅ {name}")
        elif check.problem:
            lines.append(f"❌ {name} — {check.problem}")
        else:
            labels = ", ".join(_permission_label(p) for p in check.missing)
            lines.append(f"❌ {name} — fehlt: {labels}")
    lines += ["", "**Rollen**"]
    if report.guild_problem:
        lines.append(f"❌ {report.guild_problem}")
    for role in report.roles:
        if role.ok:
            lines.append(f"✅ {role.label}")
        else:
            lines.append(f"❌ {role.label} — {role.problem}")
    text = "\n".join(lines)
    return text if len(text) <= 1990 else text[:1985] + "\n…"
