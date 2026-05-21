import discord

LOTUS_PINK = 0xE91E8C

PANEL_HEADER = (
    "## 🌸 Lotus Gaming – Server-Guide\n"
    "Alles Wichtige über unsere Community auf einen Blick."
)

PANEL_COMMANDS = (
    "### 🤖 Bot-Commands\n"
    "**🏆 /champion** — Deinen Rang, Punkte & History abrufen\n"
    "**🔥 /wcr** — Warcraft Rumble Cards nachschlagen & filtern\n"
    "**🧠 /quiz** — Duelle gegen andere in einem 💬 | general-Channel\n"
    "**⚔️ /wow** — Gildenmitglieder & Chars durchsuchen, Crafting-Cooldowns tracken, Gear checken\n"
    "**🃏 /ptcgp** — Pokémon TCG Pocket Cards & Sets nachschlagen\n\n"
    "Gib `/` ein für die komplette Befehlsliste."
)

PANEL_NITRO = (
    "### 💎 Server Boosts & Lotus Tag\n"
    "**Warum boosten?** Mehr Boosts = höhere Server-Level = mehr für alle: "
    "größeres Upload-Limit, bessere Audioqualität, mehr Emoji- & Sticker-Slots, animierter Banner.\n\n"
    "**Unser Ziel: Level 3** (33 Boosts) — damit aktivieren wir "
    "**discord.gg/LotusGaming** wieder. Jeder Boost zählt!\n\n"
    "**Lotus Tag:** Zeig der Welt, dass du Teil der Community bist! "
    "Eigenes Profil → Server Tag → **Lotus Gaming**."
)


def _e(emojis: dict[str, str], key: str) -> str:
    return emojis.get(key, "")


def _build_rules_text(emojis: dict[str, str]) -> str:
    mod = _e(emojis, "lotusmod")
    return (
        "### 🛡️ Regeln – kurz & klar\n"
        "✅ Sei respektvoll — keine Beleidigungen, keine Diskriminierung.\n"
        "🚫 Kein Spam, keine Eigenwerbung ohne Freigabe.\n"
        "🗂️ Nutze die richtigen Channels — jedes Spiel hat seinen eigenen Bereich.\n"
        "🔞 Kein NSFW-Content.\n"
        "🔒 Keine persönlichen Daten teilen (Nummern, Adressen usw.).\n"
        "⚖️ Keine illegalen Inhalte — Cheats, Hacks, Account-Handel o. Ä.\n"
        f"🎙️ Folge dem Team — {mod} <@&1053266596417785886> halten den Server fair & freundlich.\n"
        "💖 Have fun & be nice! 🪷\n\n"
        "Verstoß gesehen? Schreib einem Mod-Team-Mitglied direkt."
    )


def _build_roles_channels_text(emojis: dict[str, str]) -> str:
    booster = _e(emojis, "booster")
    member = emojis.get("lotus", "🪷")
    return (
        "### 🎭 Rollen & Channels\n"
        "Jedes Spiel hat eine eigene Rolle, die dir die passenden Channels freischaltet. "
        "Beim Beitritt wirst du direkt gefragt was dich interessiert — "
        "alles jederzeit anpassbar: **<id:customize>**\n\n"
        "**Ping-Rollen:**\n"
        "🥳 <@&1298576659213189130> — Community-Events & Challenges\n"
        "🏆 <@&1364876802337800214> — Turnier-Ankündigungen\n"
        "📺 <@&1109760546028388372> — Ping wenn Gerrit live auf Twitch geht\n\n"
        "**Besondere Rollen:**\n"
        f"🎨 <@&1184891060749615205> — Prestige-Rolle für den monatlichen Banner-Battle-Gewinner\n"
        f"🎖️ <@&1297596121631162479> — Prestige-Rolle für besondere Leistungen & Event-Sieger\n"
        f"{booster} <@&1088442794546319421> — Wird beim Server-Boost automatisch vergeben 💜\n"
        f"{member} <@&1225564224999133305> — Nach ein paar Nachrichten automatisch vergeben"
    )


def _build_champion_text(emojis: dict[str, str]) -> str:
    mod = _e(emojis, "lotusmod")
    return (
        "### 🏆 Champion-System\n"
        f"**Freie Rolle** — <@&1288423084839403582> {_e(emojis, 'challenger_0')}\n"
        "Wer aktiv hilft, Fragen beantwortet und die Community bereichert, "
        f"kann diese Rolle bei einem {mod} Mod-Team-Mitglied beantragen. "
        "Als Champion wirst du bei wichtigen Community-Fragen gepingt.\n\n"
        "**Verdiente Stufen** — Durch Aktivität auf dem Server sammelst du automatisch Punkte:\n"
        f"{_e(emojis, 'challenger_1')} <@&1288423580043837503>\n"
        f"{_e(emojis, 'challenger_2')} <@&1288423705231495202>\n"
        f"{_e(emojis, 'challenger_3')} <@&1313206485685370910>\n"
        f"{_e(emojis, 'challenger_4')} <@&1313206531684302900>\n"
        f"{_e(emojis, 'challenger_5')} <@&1313206585186848860>\n\n"
        "`/champion score` · `/champion leaderboard` · `/champion myhistory`"
    )


def _build_banner_text() -> str:
    return (
        "### 🎨 Banner Battle\n"
        "Zeig deine Kreativität! Jeden Monat erstellen Community-Mitglieder einen Server-Banner "
        "und treten damit gegeneinander an — das Community-Voting entscheidet.\n"
        "Das beste Banner gewinnt die Prestige-Rolle 🎨 <@&1184891060749615205> **Virtuoso**.\n"
        "Mitmachen: <#1184877204807635006>"
    )


class ServerInfoLayoutView(discord.ui.LayoutView):
    """Statisches Components-V2 Info-Panel für den infos-und-regeln Channel."""

    def __init__(self, emojis: dict[str, str] = {}) -> None:
        super().__init__(timeout=None)

        youtube_btn = discord.ui.Button(
            label="YouTube",
            url="https://www.youtube.com/@LotusGamingDE",
            style=discord.ButtonStyle.link,
            emoji="▶️",
        )

        twitch_btn = discord.ui.Button(
            label="Twitch",
            url="https://www.twitch.tv/gs3rr4",
            style=discord.ButtonStyle.link,
            emoji="🟣",
        )

        boost_btn = discord.ui.Button(
            label="Nitro & Boosts",
            url="https://support.discord.com/hc/de/articles/360028038352",
            style=discord.ButtonStyle.link,
            emoji="💜",
        )

        container = discord.ui.Container(
            discord.ui.TextDisplay(PANEL_HEADER),
            discord.ui.Separator(),
            discord.ui.TextDisplay(_build_rules_text(emojis)),
            discord.ui.Separator(),
            discord.ui.Section(
                discord.ui.TextDisplay(_build_roles_channels_text(emojis)),
                accessory=twitch_btn,
            ),
            discord.ui.Separator(),
            discord.ui.TextDisplay(_build_champion_text(emojis)),
            discord.ui.Separator(),
            discord.ui.Section(
                discord.ui.TextDisplay(_build_banner_text()),
                accessory=youtube_btn,
            ),
            discord.ui.Separator(),
            discord.ui.Section(
                discord.ui.TextDisplay(PANEL_NITRO),
                accessory=boost_btn,
            ),
            discord.ui.Separator(),
            discord.ui.TextDisplay(PANEL_COMMANDS),
            accent_color=LOTUS_PINK,
        )
        self.add_item(container)
