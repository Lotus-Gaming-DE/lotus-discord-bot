import discord

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
    "🎙️ **Folge dem Team** — Unsere Community Mods halten den Server fair & freundlich.\n"
    "💖 **Have fun & be nice!** — Wir wollen eine gute Zeit haben – und zwar zusammen 🪷"
)

PANEL_CHAMPION = (
    "### 🏆 Champion-System\n"
    "Für Aktivität auf dem Server sammelst du automatisch **Champion-Punkte**. "
    "Ab bestimmten Schwellenwerten erhältst du dauerhaft eine höhere Rolle:\n\n"
    "✏️ Champion → 🚀 Emerging Champion → 🔶 Seasoned Champion\n"
    "→ 🌟 Renowned Champion → 🔥 Epic Champion → 💫 Ultimate Champion\n\n"
    "`/champion score` · `/champion leaderboard` · `/champion myhistory`"
)

PANEL_ROLES = (
    "### 🎭 Wichtige Rollen\n"
    "**Member** — Wird durch MEE6-Aktivität vergeben; schaltet das Posten von Links frei.\n"
    "**Listener** — Erhalte einen Ping wenn Gerrit auf Twitch live geht.\n"
    "**event** — Werde bei Events, Turnieren & Challenges benachrichtigt.\n"
    "**Virtuoso** 🎨 — Prestige-Rolle für den monatlichen Banner-Battle-Gewinner.\n"
    "**Maestro** 🥇 — Prestige-Rolle für besondere Leistungen oder Event-Sieger.\n"
    "**Booster** 💜 — Server-Booster erhalten diese Rolle als Dankeschön.\n\n"
    "Rollen wählen: **⁠<id:customize>**"
)

PANEL_GAMES = (
    "### 🎮 Game-Bereiche freischalten\n"
    "Beim Beitritt wirst du gefragt, welche Spiele dich interessieren – "
    "mindestens eines ist Pflicht. "
    "Danach schalten die entsprechenden Channels automatisch frei.\n\n"
    "Jederzeit ändern: **⁠<id:customize>**\n\n"
    "Verfügbare Bereiche: WoW · WCR · LoL · Diablo 4 · Apex · Overwatch · "
    "Dead by Daylight · Summoners War · Pokémon TCG Pocket · MTG · PoE · Warcraft Rumble · Fellowship"
)

PANEL_NITRO = (
    "### 💎 Server Boosts & Lotus Tag\n"
    "**Warum boosten?** Mit mehr Boosts erreichen wir höhere Server-Level "
    "und schalten Community-Vorteile frei: größeres Upload-Limit, bessere Audioqualität, "
    "mehr Emoji- & Sticker-Slots, animierter Banner und mehr.\n\n"
    "**Boost-Ziel:** <id:guide> → Server Boosts\n\n"
    "**Lotus Tag aktivieren:**\n"
    "Desktop: ⚙️ → Profil → Server Tag → **Lotus Gaming**\n"
    "Mobil: Avatar → Profil bearbeiten → Server Tags → **Lotus Gaming**\n\n"
    "Jeder sichtbare Lotus-Tag und jeder Boost hilft der ganzen Community. 🌸"
)

PANEL_COMMANDS = (
    "### 🤖 Bot-Commands (Auszug)\n"
    "**🏆 /champion** — score · leaderboard · myhistory · roles · rank\n"
    "**🔥 /wcr** — name · filter\n"
    "**🧠 /quiz** — duel (in einem der 💬 | general-Channels)\n\n"
    "Gib `/` ein und wähle den gewünschten Bereich für die komplette Liste."
)


class ServerInfoLayoutView(discord.ui.LayoutView):
    """Statisches Components-V2 Info-Panel für den infos-und-regeln Channel."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

        container = discord.ui.Container(
            discord.ui.TextDisplay(PANEL_HEADER),
            discord.ui.Separator(),
            discord.ui.TextDisplay(PANEL_RULES),
            discord.ui.Separator(),
            discord.ui.TextDisplay(PANEL_CHAMPION),
            discord.ui.Separator(),
            discord.ui.TextDisplay(PANEL_ROLES),
            discord.ui.Separator(),
            discord.ui.TextDisplay(PANEL_GAMES),
            discord.ui.Separator(),
            discord.ui.TextDisplay(PANEL_NITRO),
            discord.ui.Separator(),
            discord.ui.TextDisplay(PANEL_COMMANDS),
        )
        self.add_item(container)
