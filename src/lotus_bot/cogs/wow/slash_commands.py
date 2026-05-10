import discord
from discord import app_commands

from lotus_bot.log_setup import get_logger
from lotus_bot.permissions import moderator_only

from .cog import WoWCog
from .data import CharacterClaim, CharacterProfession

logger = get_logger(__name__)

wow_group = app_commands.Group(
    name="wow",
    description="WoW Classic Hardcore Befehle",
)


def _format_claim_status(status: str) -> str:
    return "bestätigt" if status == "verified" else "ungeprüft"


def _format_claim_line(claim: CharacterClaim, *, include_user: bool = False) -> str:
    user = f" - <@{claim.discord_user_id}>" if include_user else ""
    return f"**{claim.character_name}** ({_format_claim_status(claim.status)}){user}"


def _is_mod(interaction: discord.Interaction) -> bool:
    permissions = getattr(interaction.user, "guild_permissions", None)
    return bool(permissions and permissions.manage_guild)


def _format_profession_line(
    profile: CharacterProfession, cog: WoWCog, *, include_user: bool = False
) -> str:
    user = f" - <@{profile.discord_user_id}>" if include_user else ""
    specialization = f" ({profile.specialization})" if profile.specialization else ""
    return (
        f"**{profile.character_name}** - "
        f"{cog._profession_name(profile.profession_id)} "
        f"{profile.skill_level}{specialization}{user}"
    )


async def profession_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    cog: WoWCog | None = interaction.client.get_cog("WoWCog")
    if cog is None:
        return []
    return [
        app_commands.Choice(name=name, value=value)
        for name, value in cog.profession_choices(current)
    ]


@wow_group.command(name="setup", description="Konfiguriert den WoW-Ankündigungschannel")
@moderator_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(channel="Channel für WoW-Meilensteinmeldungen")
async def setup(interaction: discord.Interaction, channel: discord.TextChannel):
    logger.info(f"/wow setup by {interaction.user} channel={channel.id}")
    cog: WoWCog | None = interaction.client.get_cog("WoWCog")
    if cog is None:
        await interaction.response.send_message(
            "❌ WoW-System nicht verfügbar.", ephemeral=True
        )
        return
    await cog.set_announcement_channel(channel.id)
    await interaction.response.send_message(
        f"✅ WoW-Ankündigungen werden in {channel.mention} gepostet.",
        ephemeral=True,
    )


@wow_group.command(name="status", description="Zeigt den WoW-Tracker Status")
async def status(interaction: discord.Interaction):
    cog: WoWCog | None = interaction.client.get_cog("WoWCog")
    if cog is None:
        await interaction.response.send_message(
            "❌ WoW-System nicht verfügbar.", ephemeral=True
        )
        return

    info = await cog.status()
    channel_id = info.get("channel_id")
    officer_channel_id = info.get("officer_channel_id")
    channel_text = f"<#{channel_id}>" if channel_id else "nicht konfiguriert"
    officer_channel_text = (
        f"<#{officer_channel_id}>" if officer_channel_id else "nicht konfiguriert"
    )
    last_scan = info.get("last_scan_at") or "noch nie"
    interval_hours = int(info["poll_interval"]) // 3600
    await interaction.response.send_message(
        "\n".join(
            [
                f"Guild: **{info['guild']}**",
                f"Realm: **{info['realm']}**",
                f"Channel: {channel_text}",
                f"Offi-Channel: {officer_channel_text}",
                f"Letzter Scan: {last_scan}",
                f"Mitglieder im Snapshot: {info['member_count']}",
                f"Polling: alle {interval_hours} Stunden",
            ]
        ),
        ephemeral=True,
    )


@wow_group.command(name="scan", description="Prüft den WoW-Roster sofort")
@moderator_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(post="Meilensteine posten, falls welche gefunden werden")
async def scan(interaction: discord.Interaction, post: bool = True):
    logger.info(f"/wow scan by {interaction.user} post={post}")
    cog: WoWCog | None = interaction.client.get_cog("WoWCog")
    if cog is None:
        await interaction.response.send_message(
            "❌ WoW-System nicht verfügbar.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        result = await cog.scan(post=post, persist=post)
    except Exception as exc:
        logger.error("[WoWCommands] Scan failed: %s", exc, exc_info=True)
        await interaction.followup.send("❌ WoW-Scan fehlgeschlagen.")
        return

    mode = "gepostet" if post else "Dry-Run"
    await interaction.followup.send(
        f"{mode}: {result.member_count} Mitglieder geprüft, "
        f"{len(result.milestones)} Meilensteine gefunden, {result.posted} gepostet."
    )


@wow_group.command(name="claim", description="Claimt einen Black-Lotus-Charakter")
@app_commands.describe(char="Name des Charakters im Black-Lotus-Roster")
async def claim(interaction: discord.Interaction, char: str):
    logger.info(f"/wow claim by {interaction.user} char={char}")
    cog: WoWCog | None = interaction.client.get_cog("WoWCog")
    if cog is None:
        await interaction.response.send_message(
            "❌ WoW-System nicht verfügbar.", ephemeral=True
        )
        return

    result = await cog.claim_character(interaction.user.id, char)
    if result.reason == "not_found":
        await interaction.response.send_message(
            f"❌ **{char}** wurde im aktuellen Black-Lotus-Roster nicht gefunden.",
            ephemeral=True,
        )
        return
    if result.claim is None:
        await interaction.response.send_message(
            "❌ Claim konnte nicht erstellt werden.", ephemeral=True
        )
        return
    if result.reason == "taken":
        await interaction.response.send_message(
            f"❌ **{result.claim.character_name}** ist bereits geclaimed.",
            ephemeral=True,
        )
        return
    if result.reason == "already_own":
        await interaction.response.send_message(
            f"ℹ️ Du hast **{result.claim.character_name}** bereits geclaimed "
            f"({_format_claim_status(result.claim.status)}).",
            ephemeral=True,
        )
        return

    warning = (
        "" if result.review_posted else "\n⚠️ Offi-Review konnte nicht gepostet werden."
    )
    await interaction.response.send_message(
        f"✅ Du hast **{result.claim.character_name}** geclaimed "
        f"({_format_claim_status(result.claim.status)}).{warning}",
        ephemeral=True,
    )


@wow_group.command(
    name="claim-release", description="Gibt deinen eigenen WoW-Claim frei"
)
@app_commands.describe(char="Name des geclaimten Charakters")
async def claim_release(interaction: discord.Interaction, char: str):
    logger.info(f"/wow claim-release by {interaction.user} char={char}")
    cog: WoWCog | None = interaction.client.get_cog("WoWCog")
    if cog is None:
        await interaction.response.send_message(
            "❌ WoW-System nicht verfügbar.", ephemeral=True
        )
        return

    existing = await cog.data.get_claim_by_name(char)
    if not existing or existing.discord_user_id != interaction.user.id:
        await interaction.response.send_message(
            f"❌ Du hast **{char}** nicht geclaimed.", ephemeral=True
        )
        return
    await cog.data.remove_claim(existing.character_key)
    await interaction.response.send_message(
        f"✅ Claim für **{existing.character_name}** wurde freigegeben.", ephemeral=True
    )


@wow_group.command(name="claim-remove", description="Entfernt einen WoW-Claim")
@moderator_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(char="Name des geclaimten Charakters")
async def claim_remove(interaction: discord.Interaction, char: str):
    logger.info(f"/wow claim-remove by {interaction.user} char={char}")
    cog: WoWCog | None = interaction.client.get_cog("WoWCog")
    if cog is None:
        await interaction.response.send_message(
            "❌ WoW-System nicht verfügbar.", ephemeral=True
        )
        return

    existing = await cog.data.get_claim_by_name(char)
    if not existing:
        await interaction.response.send_message(
            f"ℹ️ **{char}** ist aktuell nicht geclaimed.", ephemeral=True
        )
        return
    await cog.data.remove_claim(existing.character_key)
    await interaction.response.send_message(
        f"✅ Claim für **{existing.character_name}** wurde entfernt.", ephemeral=True
    )


claims_group = app_commands.Group(
    name="claims",
    description="WoW Character Claims",
    parent=wow_group,
)


@claims_group.command(name="mine", description="Zeigt deine geclaimten WoW-Charaktere")
async def claims_mine(interaction: discord.Interaction):
    cog: WoWCog | None = interaction.client.get_cog("WoWCog")
    if cog is None:
        await interaction.response.send_message(
            "❌ WoW-System nicht verfügbar.", ephemeral=True
        )
        return

    claims = await cog.data.claims_for_user(interaction.user.id)
    if not claims:
        await interaction.response.send_message(
            "Du hast noch keine WoW-Charaktere geclaimed.", ephemeral=True
        )
        return
    await interaction.response.send_message(
        "\n".join(_format_claim_line(claim) for claim in claims),
        ephemeral=True,
    )


@claims_group.command(name="list", description="Listet WoW Character Claims")
@moderator_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.choices(
    status=[
        app_commands.Choice(name="all", value="all"),
        app_commands.Choice(name="unverified", value="unverified"),
        app_commands.Choice(name="verified", value="verified"),
    ]
)
async def claims_list(interaction: discord.Interaction, status: str = "all"):
    cog: WoWCog | None = interaction.client.get_cog("WoWCog")
    if cog is None:
        await interaction.response.send_message(
            "❌ WoW-System nicht verfügbar.", ephemeral=True
        )
        return

    claims = await cog.data.list_claims(status)
    if not claims:
        await interaction.response.send_message(
            "Keine Claims gefunden.", ephemeral=True
        )
        return
    await interaction.response.send_message(
        "\n".join(_format_claim_line(claim, include_user=True) for claim in claims),
        ephemeral=True,
    )


crafting_group = app_commands.Group(
    name="crafting",
    description="WoW Crafting Profile und Suche",
    parent=wow_group,
)


@crafting_group.command(name="set", description="Setzt Beruf und Skill eines Chars")
@app_commands.describe(
    char="Name des geclaimten Charakters",
    profession="Beruf",
    skill="Berufsskill 1-300",
    specialization="Optionale Spezialisierung",
)
@app_commands.autocomplete(profession=profession_autocomplete)
async def crafting_set(
    interaction: discord.Interaction,
    char: str,
    profession: str,
    skill: app_commands.Range[int, 1, 300],
    specialization: str | None = None,
):
    logger.info(
        f"/wow crafting set by {interaction.user} char={char} profession={profession}"
    )
    cog: WoWCog | None = interaction.client.get_cog("WoWCog")
    if cog is None:
        await interaction.response.send_message(
            "âŒ WoW-System nicht verfÃ¼gbar.", ephemeral=True
        )
        return

    result = await cog.set_crafting_profile(
        interaction.user.id,
        char,
        profession,
        int(skill),
        specialization,
        is_mod=_is_mod(interaction),
    )
    if result.reason == "unknown_profession":
        await interaction.response.send_message(
            f"âŒ Beruf **{profession}** ist unbekannt.", ephemeral=True
        )
        return
    if result.reason == "not_claimed":
        await interaction.response.send_message(
            f"âŒ **{char}** ist nicht geclaimed.", ephemeral=True
        )
        return
    if result.reason == "forbidden":
        await interaction.response.send_message(
            f"âŒ Du darfst **{char}** nicht bearbeiten.", ephemeral=True
        )
        return
    if result.reason == "invalid_skill":
        await interaction.response.send_message(
            "âŒ Skill muss zwischen 1 und 300 liegen.", ephemeral=True
        )
        return

    await interaction.response.send_message(
        f"âœ… Gespeichert: {cog.format_profession(result.profession)}",
        ephemeral=True,
    )


@crafting_group.command(name="remove", description="Entfernt einen Beruf vom Char")
@app_commands.describe(
    char="Name des geclaimten Charakters",
    profession="Beruf",
)
@app_commands.autocomplete(profession=profession_autocomplete)
async def crafting_remove(
    interaction: discord.Interaction,
    char: str,
    profession: str,
):
    logger.info(
        f"/wow crafting remove by {interaction.user} char={char} profession={profession}"
    )
    cog: WoWCog | None = interaction.client.get_cog("WoWCog")
    if cog is None:
        await interaction.response.send_message(
            "âŒ WoW-System nicht verfÃ¼gbar.", ephemeral=True
        )
        return

    result = await cog.remove_crafting_profile(
        interaction.user.id,
        char,
        profession,
        is_mod=_is_mod(interaction),
    )
    if result.reason == "unknown_profession":
        await interaction.response.send_message(
            f"âŒ Beruf **{profession}** ist unbekannt.", ephemeral=True
        )
        return
    if result.reason == "not_claimed":
        await interaction.response.send_message(
            f"âŒ **{char}** ist nicht geclaimed.", ephemeral=True
        )
        return
    if result.reason == "forbidden":
        await interaction.response.send_message(
            f"âŒ Du darfst **{char}** nicht bearbeiten.", ephemeral=True
        )
        return
    if result.reason == "not_set":
        await interaction.response.send_message(
            f"â„¹ï¸ FÃ¼r **{char}** ist dieser Beruf nicht gepflegt.",
            ephemeral=True,
        )
        return

    await interaction.response.send_message(
        f"âœ… Beruf fÃ¼r **{result.claim.character_name}** entfernt.",
        ephemeral=True,
    )


@crafting_group.command(name="mine", description="Zeigt deine Crafting-Profile")
async def crafting_mine(interaction: discord.Interaction):
    cog: WoWCog | None = interaction.client.get_cog("WoWCog")
    if cog is None:
        await interaction.response.send_message(
            "âŒ WoW-System nicht verfÃ¼gbar.", ephemeral=True
        )
        return

    profiles = await cog.data.professions_for_user(interaction.user.id)
    if not profiles:
        await interaction.response.send_message(
            "Du hast noch keine Crafting-Profile gepflegt.", ephemeral=True
        )
        return
    await interaction.response.send_message(
        "\n".join(_format_profession_line(profile, cog) for profile in profiles),
        ephemeral=True,
    )


@crafting_group.command(name="list", description="Listet Crafting-Profile")
@moderator_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(profession="Optionaler Beruf-Filter")
@app_commands.autocomplete(profession=profession_autocomplete)
async def crafting_list(
    interaction: discord.Interaction, profession: str | None = None
):
    cog: WoWCog | None = interaction.client.get_cog("WoWCog")
    if cog is None:
        await interaction.response.send_message(
            "âŒ WoW-System nicht verfÃ¼gbar.", ephemeral=True
        )
        return

    profession_id = cog.resolve_profession_id(profession) if profession else None
    if profession and not profession_id:
        await interaction.response.send_message(
            f"âŒ Beruf **{profession}** ist unbekannt.", ephemeral=True
        )
        return
    profiles = await cog.data.list_professions(profession_id)
    if not profiles:
        await interaction.response.send_message(
            "Keine Crafting-Profile gefunden.", ephemeral=True
        )
        return
    await interaction.response.send_message(
        "\n".join(
            _format_profession_line(profile, cog, include_user=True)
            for profile in profiles
        ),
        ephemeral=True,
    )


@crafting_group.command(name="search", description="Sucht Crafter fÃ¼r ein Item")
@app_commands.describe(item="Deutscher oder englischer Itemname")
async def crafting_search(interaction: discord.Interaction, item: str):
    cog: WoWCog | None = interaction.client.get_cog("WoWCog")
    if cog is None:
        await interaction.response.send_message(
            "âŒ WoW-System nicht verfÃ¼gbar.", ephemeral=True
        )
        return

    result = await cog.search_crafting(item)
    await interaction.response.send_message(
        cog.format_crafting_search_result(result),
        ephemeral=True,
    )
