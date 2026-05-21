import discord

LOTUS_PINK = 0xE91E8C

PANEL_HEADER = (
    "## 🌸 Lotus Gaming – Server-Guide\n"
    "Alles Wichtige über unsere Community auf einen Blick."
)

PANEL_RULES = (
    "### 🛡️ Regeln – kurz & klar\n"
    "✅ **Sei respektvoll** — Kein Platz für Beleidigungen, Diskriminierung oder Toxizität.\n"
    "🚫 **Kein Spam / Keine Eigenwerbung** — Keine Massennachrichten oder Werbung ohne Freigabe.\n"
    "🗂️ **Nutze passende Channels** — Jedes Spiel hat seinen eigenen Bereich.\n"
    "🔞 **NSFW ist tabu** — Pornografie, Gewalt oder verstörende Inhalte sind verboten.\n"
    "🔒 **Schütze deine Privatsphäre** — Keine realen Daten, Telefonnummern, Adressen usw.\n"
    "⚖️ **Keine illegalen Inhalte** — Cheats, Hacks, Account-Handel o. Ä. sind verboten.\n"
    "🎙️ **Folge dem Team** — Unsere Community Mods <@&1053266596417785886> halten den Server fair & freundlich.\n"
    "💖 **Have fun & be nice!** — Wir wollen eine gute Zeit haben – und zwar zusammen 🪷\n\n"
    "Verstoß gesehen? Schreib einem Mod-Team-Mitglied direkt."
)

PANEL_ONBOARDING = (
    "### 🔧 Server einrichten\n"
    "Beim Beitritt wirst du automatisch gefragt, welche Spiele dich interessieren – "
    "die passenden Channels schalten sich direkt frei. "
    "Jederzeit anpassen: **<id:customize>**\n\n"
    "**Verfügbare Game-Bereiche:**\n"
    "WoW · WCR · LoL · Diablo 4 · Apex · Overwatch · Dead by Daylight · "
    "Summoners War · Pokémon TCG Pocket · MTG · PoE · Warcraft Rumble · Fellowship\n\n"
    "**Ping-Benachrichtigungen** (ebenfalls in <id:customize>):\n"
    "🔔 **@event** — Community-Events & Challenges\n"
    "🏆 **@tournament** — Turnier-Ankündigungen\n"
    "📺 **@Listener** — Ping wenn Gerrit auf Twitch live geht"
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
    "**Boost-Ziel:** <id:guide> → Server Boosts\n\n"
    "**Lotus Tag:** Zeig der Welt, dass du Teil der Community bist! "
    "Aktivieren: Eigenes Profil → Server Tag → **Lotus Gaming**.\n\n"
    "Jeder sichtbare Tag und jeder Boost hilft der ganzen Community. 🌸"
)


def _e(emojis: dict[str, str], key: str) -> str:
    return emojis.get(key, "")


def _build_champion_text(emojis: dict[str, str]) -> str:
    return (
        "### 🏆 Champion-System\n"
        f"**Freie Rolle** — <@&1288423084839403582> {_e(emojis, 'challenger_0')} für jeden!\n"
        "Wer aktiv hilft, Fragen beantwortet und die Community bereichert, "
        "kann die Rolle bei einem Mod-Team-Mitglied beantragen. "
        "Als Champion wirst du bei wichtigen Community-Fragen gepingt.\n\n"
        "**Verdiente Stufen** — Durch Aktivität auf dem Server sammelst du automatisch Punkte:\n"
        f"{_e(emojis, 'challenger_1')} <@&1288423580043837503> Emerging Champion\n"
        f"{_e(emojis, 'challenger_2')} <@&1288423705231495202> Seasoned Champion\n"
        f"{_e(emojis, 'challenger_3')} <@&1313206485685370910> Renowned Champion\n"
        f"{_e(emojis, 'challenger_4')} <@&1313206531684302900> Epic Champion\n"
        f"{_e(emojis, 'challenger_5')} <@&1313206585186848860> Ultimate Champion\n\n"
        "`/champion score` · `/champion leaderboard` · `/champion myhistory`"
    )


def _build_banner_text(emojis: dict[str, str]) -> str:
    return (
        "### 🎨 Banner Battle\n"
        "Jeden Monat treten Community-Mitglieder im Banner-Battle-Forum gegeneinander an – "
        "das Community-Voting entscheidet!\n"
        f"Das beste Banner gewinnt die Prestige-Rolle {_e(emojis, 'art')} <@&1184891060749615205> **Virtuoso**.\n"
        "Mitmachen: <#1184877204807635006>"
    )


def _build_roles_text(emojis: dict[str, str]) -> str:
    return (
        "### 🎭 Besondere Rollen\n"
        f"{_e(emojis, 'art')} <@&1184891060749615205> **Virtuoso** — Prestige-Rolle für den monatlichen Banner-Battle-Gewinner.\n"
        f"{_e(emojis, 'military_medal')} <@&1297596121631162479> **Maestro** — Prestige-Rolle für besondere Leistungen oder Event-Sieger.\n"
        "**Booster** 💜 — Vergibt sich automatisch beim Server-Boost — danke!\n"
        "**Member** — Spam-Schutz: kommt automatisch nach ein paar Nachrichten und schaltet das Posten von Links frei."
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

        container = discord.ui.Container(
            discord.ui.TextDisplay(PANEL_HEADER),
            discord.ui.Separator(),
            discord.ui.TextDisplay(PANEL_RULES),
            discord.ui.Separator(),
            discord.ui.Section(
                discord.ui.TextDisplay(PANEL_ONBOARDING),
                accessory=twitch_btn,
            ),
            discord.ui.Separator(),
            discord.ui.TextDisplay(_build_champion_text(emojis)),
            discord.ui.Separator(),
            discord.ui.Section(
                discord.ui.TextDisplay(_build_banner_text(emojis)),
                accessory=youtube_btn,
            ),
            discord.ui.Separator(),
            discord.ui.TextDisplay(_build_roles_text(emojis)),
            discord.ui.Separator(),
            discord.ui.TextDisplay(PANEL_COMMANDS),
            discord.ui.Separator(),
            discord.ui.TextDisplay(PANEL_NITRO),
            accent_color=LOTUS_PINK,
        )
        self.add_item(container)
