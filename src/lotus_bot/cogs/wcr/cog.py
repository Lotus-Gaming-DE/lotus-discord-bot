# cogs/wcr/cog.py

import discord
from discord.ext import commands
from dataclasses import dataclass

from lotus_bot.log_setup import get_logger
from . import resolver, embed_builder
from . import helpers
from .views import MiniSelectView
from .duel import DuelCalculator

logger = get_logger(__name__)


@dataclass
class DuelOutcome:
    """Ergebnistext eines Mini-Duells."""

    text: str


class WCRCog(commands.Cog):
    def __init__(self, bot) -> None:
        """Cog für Warcraft Rumble Befehle mit automatischem Fallback."""
        self.bot = bot

        wcr_data = bot.data.get("wcr") or {}

        # Bei fehlenden Daten Warnung ausgeben, aber nicht abbrechen
        if not wcr_data:
            logger.warning("[WCRCog] WCR data missing. Commands may not work")

        self.units = wcr_data.get("units", [])
        if isinstance(self.units, dict) and "units" in self.units:
            self.units = self.units["units"]
        self.languages = wcr_data.get("locals", {})
        if not self.languages:
            logger.warning("[WCRCog] No localization found, falling back to English.")
            en_units = []
            for unit in self.units:
                text = unit.get("texts", {}).get("en")
                if text:
                    entry = {"id": unit.get("id")}
                    entry.update(text)
                    en_units.append(entry)
            self.languages = {"en": {"units": en_units}}
        self.categories = wcr_data.get("categories", {})
        self.stat_labels = wcr_data.get("stat_labels", {})
        self.faction_combinations = wcr_data.get("faction_combinations", {})

        # Mapping for resolving unit names quickly
        (
            self.unit_name_map,
            self.id_name_map,
            self.name_token_index,
        ) = resolver.build_lookup_tables(self.languages)

        self.lang_category_lookup = helpers.build_category_lookup(self.categories)

        # Emojis liegen in bot.data["emojis"]
        self.emojis = bot.data["emojis"]

        # Cached lists for the autocomplete callbacks -----------------------
        # Unique elixir costs found in ``self.units``
        self.costs = sorted({unit["cost"] for unit in self.units})
        self.cost_choices = [
            discord.app_commands.Choice(name=str(c), value=str(c)) for c in self.costs
        ]

        # Choices for localized categories (always from English names if available)
        if "en" in self.languages:
            cats_lang = "en"
        else:
            cats_lang = next(iter(self.languages))
            logger.warning(
                "'en' language not found in WCR locals, using '%s' for choices",
                cats_lang,
            )

        cats = self.lang_category_lookup.get(cats_lang, {})
        self.speed_choices = [
            discord.app_commands.Choice(name=item["name"], value=str(cid))
            for cid, item in cats.get("speeds", {}).items()
        ]
        self.faction_choices = [
            discord.app_commands.Choice(name=item["name"], value=str(cid))
            for cid, item in cats.get("factions", {}).items()
        ]
        self.type_choices = [
            discord.app_commands.Choice(name=item["name"], value=str(cid))
            for cid, item in cats.get("types", {}).items()
        ]
        self.trait_choices = [
            discord.app_commands.Choice(name=item["name"], value=str(cid))
            for cid, item in cats.get("traits", {}).items()
        ]

    def _autocomplete(
        self, options: list[discord.app_commands.Choice], current: str
    ) -> list[discord.app_commands.Choice]:
        """Return up to 25 matching choices for ``current``."""
        current_lower = current.lower()
        return [opt for opt in options if current_lower in opt.name.lower()][:25]

    # ─── Autocomplete-Callbacks ─────────────────────────────────────────
    async def cost_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[discord.app_commands.Choice]:
        """Provide autocomplete suggestions for unit costs."""
        return self._autocomplete(self.cost_choices, current)

    async def speed_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[discord.app_commands.Choice]:
        """Autocomplete unit speeds."""
        return self._autocomplete(self.speed_choices, current)

    async def faction_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[discord.app_commands.Choice]:
        """Autocomplete factions."""
        return self._autocomplete(self.faction_choices, current)

    async def type_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[discord.app_commands.Choice]:
        """Autocomplete unit types."""
        return self._autocomplete(self.type_choices, current)

    async def trait_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[discord.app_commands.Choice]:
        """Autocomplete unit traits."""
        return self._autocomplete(self.trait_choices, current)

    async def unit_name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[discord.app_commands.Choice]:
        """Autocomplete Minis über alle unterstützten Sprachen."""
        normalized = " ".join(helpers.normalize_name(current))
        matched_ids: set[str] = set()
        for mapping in self.unit_name_map.values():
            for name, uid in mapping.items():
                if not normalized or normalized in name:
                    matched_ids.add(uid)

        results: list[discord.app_commands.Choice] = []
        for lang in self.languages:
            for uid in matched_ids:
                unit_name = helpers.get_text_data(uid, lang, self.languages)[0]
                results.append(
                    discord.app_commands.Choice(
                        name=f"{unit_name} [{lang}]", value=str(uid)
                    )
                )
                if len(results) >= 25:
                    return results[:25]

        return results[:25]

    # ─── Ausgelagerte Slash-Logik ────────────────────────────────────────
    async def cmd_filter(
        self,
        interaction: discord.Interaction,
        cost: str = None,
        speed: str = None,
        faction: str = None,
        type: str = None,
        trait: str = None,
        lang: str = "de",
        public: bool = False,
    ):
        """Implementation for the ``/wcr filter`` command."""
        logger.info(
            f"[WCR] /wcr filter by {interaction.user} - "
            f"cost={cost}, speed={speed}, faction={faction}, type={type}, trait={trait}, lang={lang}, public={public}"
        )

        if lang not in self.languages:
            await interaction.response.send_message(
                "Sprache nicht unterstützt. Verfügbar: "
                + ", ".join(self.languages.keys()),
                ephemeral=not public,
            )
            return

        filtered_units = self.units

        # Kosten filtern
        if cost is not None:
            try:
                cost_value = int(cost)
            except ValueError:
                await interaction.response.send_message(
                    f"Kosten '{cost}' ist keine gültige Zahl.",
                    ephemeral=not public,
                )
                return
            filtered_units = [u for u in filtered_units if u.get("cost") == cost_value]

        # Geschwindigkeit filtern
        if speed is not None:
            speed_id = (
                helpers.find_category_id(
                    speed, "speeds", lang, self.lang_category_lookup
                )
                if not speed.isdigit()
                else speed
            )
            if speed_id is None:
                await interaction.response.send_message(
                    f"Geschwindigkeit '{speed}' nicht gefunden.",
                    ephemeral=not public,
                )
                return
            filtered_units = [
                u for u in filtered_units if u.get("speed_id") == speed_id
            ]

        # Fraktion filtern
        if faction is not None:
            faction_id = (
                helpers.find_category_id(
                    faction, "factions", lang, self.lang_category_lookup
                )
                if not faction.isdigit()
                else faction
            )
            if faction_id is None:
                await interaction.response.send_message(
                    f"Fraktion '{faction}' nicht gefunden.",
                    ephemeral=not public,
                )
                return
            filtered_units = [
                u
                for u in filtered_units
                if str(faction_id)
                in [str(fid) for fid in (u.get("faction_ids") or [u.get("faction_id")])]
            ]

        # Typ filtern
        if type is not None:
            type_id = (
                helpers.find_category_id(type, "types", lang, self.lang_category_lookup)
                if not type.isdigit()
                else type
            )
            if type_id is None:
                await interaction.response.send_message(
                    f"Typ '{type}' nicht gefunden.",
                    ephemeral=not public,
                )
                return
            filtered_units = [u for u in filtered_units if u.get("type_id") == type_id]

        # Merkmal filtern
        if trait is not None:
            trait_id = (
                helpers.find_category_id(
                    trait, "traits", lang, self.lang_category_lookup
                )
                if not trait.isdigit()
                else trait
            )
            if trait_id is None:
                await interaction.response.send_message(
                    f"Merkmal '{trait}' nicht gefunden.",
                    ephemeral=not public,
                )
                return
            filtered_units = [
                u for u in filtered_units if trait_id in u.get("trait_ids", [])
            ]

        if not filtered_units:
            await interaction.response.send_message(
                "Keine Minis gefunden, die den angegebenen Kriterien entsprechen.",
                ephemeral=not public,
            )
            return

        if len(filtered_units) > 25:
            await interaction.response.send_message(
                "Zu viele Ergebnisse. Bitte verfeinere deine Filter.",
                ephemeral=not public,
            )
            return

        options = []
        for unit in filtered_units:
            unit_id = unit["id"]
            unit_name = helpers.get_text_data(unit_id, lang, self.languages)[0]
            emoji_syntax = self.emojis.get(
                helpers.get_faction_icon(unit["faction_id"], self.lang_category_lookup),
                "",
            )
            if emoji_syntax:
                option = discord.SelectOption(
                    label=unit_name, value=str(unit_id), emoji=emoji_syntax
                )
            else:
                option = discord.SelectOption(label=unit_name, value=str(unit_id))
            options.append(option)

        view = MiniSelectView(options, self, lang, public=public)
        await interaction.response.send_message(
            "Gefundene Minis:", view=view, ephemeral=not public
        )

    async def cmd_name(
        self,
        interaction: discord.Interaction,
        name: str,
        lang: str = "de",
        public: bool = False,
    ):
        """Implementation for the ``/wcr name`` command."""
        logger.info(
            f"[WCR] /wcr name by {interaction.user} - name={name}, lang={lang}, public={public}"
        )
        await interaction.response.defer(ephemeral=not public)

        try:
            embed, logo_file = self.create_mini_embed(name, lang)
        except Exception as e:
            logger.error(f"Error in create_mini_embed: {e}", exc_info=True)
            await interaction.followup.send(
                "Ein Fehler ist aufgetreten.", ephemeral=not public
            )
            return

        if embed is None:
            await interaction.followup.send(
                f"Mini mit Namen '{name}' nicht gefunden.", ephemeral=not public
            )
        else:
            if logo_file:
                await interaction.followup.send(
                    embed=embed, file=logo_file, ephemeral=not public
                )
            else:
                await interaction.followup.send(embed=embed, ephemeral=not public)

    async def cmd_duel(
        self,
        interaction: discord.Interaction,
        mini_a: str,
        mini_b: str,
        level_a: int = 1,
        level_b: int = 1,
        lang: str = "de",
        public: bool = False,
    ):
        """Implementation for ``/wcr duell``."""
        logger.info(
            f"[WCR] /wcr duell by {interaction.user} - "
            f"mini_a={mini_a}, level_a={level_a}, "
            f"mini_b={mini_b}, level_b={level_b}, lang={lang}, public={public}"
        )
        await interaction.response.defer(ephemeral=not public)

        outcome = self._compute_duel_outcome(mini_a, mini_b, level_a, level_b, lang)
        await interaction.followup.send(outcome.text, ephemeral=not public)

    async def cmd_debug(self, interaction: discord.Interaction) -> None:
        """Sendet eine kurze Übersicht der geladenen WCR-Daten."""
        units_count = len(self.units)
        categories = {k: len(v) for k, v in self.categories.items()}
        msg = f"{units_count} Minis geladen. Kategorien: " + ", ".join(
            f"{k}={v}" for k, v in categories.items()
        )
        await interaction.response.send_message(msg, ephemeral=True)

    def create_mini_embed(self, name_or_id, lang):
        """Baue ein Mini-Embed.

        Lookup erfolgt sprachübergreifend, die Ausgabe richtet sich nach
        ``lang``.
        """
        result = self.resolve_unit(name_or_id, lang)
        if not result:
            return None, None
        if lang not in self.languages:
            return None, None

        unit_id, unit_data, _ = result

        return embed_builder.build_mini_embed(
            unit_id,
            unit_data,
            lang,
            self.emojis,
            self.languages,
            self.lang_category_lookup,
            self.stat_labels,
            self.faction_combinations,
        )

    def _find_unit_id_by_name(
        self, normalized: str, lang: str
    ) -> tuple[str | None, str]:
        return resolver.find_unit_id_by_name(
            normalized,
            lang,
            self.unit_name_map,
            self.id_name_map,
            self.name_token_index,
        )

    def resolve_unit(self, name_or_id, lang):
        """Finde ein Mini in allen Sprachen.

        Lookup erfolgt sprachübergreifend, die Ausgabe richtet sich nach
        ``lang``.
        """
        if lang not in self.languages:
            return None

        if any(unit["id"] == str(name_or_id) for unit in self.units):
            unit_id = str(name_or_id)
            unit_data = next((u for u in self.units if u["id"] == unit_id), None)
            if not unit_data:
                return None
            name, _, _ = helpers.get_text_data(unit_id, lang, self.languages)
            if name == "Unbekannt":
                return None
        else:
            normalized = " ".join(helpers.normalize_name(name_or_id))
            unit_id, lang = self._find_unit_id_by_name(normalized, lang)
            if unit_id is None:
                for other_lang in self.languages:
                    if other_lang == lang:
                        continue
                    unit_id, found_lang = self._find_unit_id_by_name(
                        normalized, other_lang
                    )
                    if unit_id is not None:
                        lang = found_lang
                        break
            if unit_id is None:
                return None

            unit_data = next(
                (unit for unit in self.units if unit["id"] == unit_id), None
            )
            if not unit_data:
                return None

        return unit_id, unit_data, lang

    # Helper methods -----------------------------------------------------
    def _compute_duel_outcome(
        self,
        mini_a: str,
        mini_b: str,
        level_a: int = 1,
        level_b: int = 1,
        lang: str = "de",
    ) -> DuelOutcome:
        """Berechne den Ergebnistext für ``/wcr duell``."""

        res_a = self.resolve_unit(mini_a, lang)
        res_b = self.resolve_unit(mini_b, lang)
        if not res_a or not res_b:
            return DuelOutcome("Eines der Minis wurde nicht gefunden.")

        id_a, data_a, _ = res_a
        id_b, data_b, _ = res_b

        name_a = helpers.get_text_data(id_a, lang, self.languages)[0]
        name_b = helpers.get_text_data(id_b, lang, self.languages)[0]

        calculator = DuelCalculator()

        base_a = data_a.get("stats", {})
        base_b = data_b.get("stats", {})
        stats_a = calculator.scaled_stats(data_a, level_a)
        stats_b = calculator.scaled_stats(data_b, level_b)

        dps_a, notes_a = calculator.compute_dps_details(data_a, stats_a, data_b)
        dps_b, notes_b = calculator.compute_dps_details(data_b, stats_b, data_a)

        def _flight_issue(att: dict, def_: dict) -> bool:
            ta = [str(t) for t in att.get("trait_ids", [])]
            td = [str(t) for t in def_.get("trait_ids", [])]
            if att.get("type_id") == "2":
                return False
            return "15" in td and "11" not in ta and "15" not in ta

        issue_a = _flight_issue(data_a, data_b)
        issue_b = _flight_issue(data_b, data_a)

        if (issue_a or dps_a == 0) and (issue_b or dps_b == 0):
            return DuelOutcome("Keines der Minis kann den Gegner treffen.")

        winner_data = calculator.duel_result(data_a, level_a, data_b, level_b)

        is_spell_a = data_a.get("type_id") == 2
        is_spell_b = data_b.get("type_id") == 2

        if is_spell_a and is_spell_b:
            if winner_data is None:
                header = "Beide Zauber verursachen gleich viel Schaden."
            else:
                winner, _ = winner_data
                if winner == "a":
                    header = f"Zauber {name_a} hat mehr DPS und w\u00fcrde daher {name_b} outperformen."
                else:
                    header = f"Zauber {name_b} hat mehr DPS und w\u00fcrde daher {name_a} outperformen."
        elif is_spell_a or is_spell_b:
            spell_name = name_a if is_spell_a else name_b
            mini_name = name_b if is_spell_a else name_a
            if winner_data is None:
                header = f"{spell_name} w\u00fcrde {mini_name} nicht t\u00f6ten."
            else:
                header = f"{spell_name} w\u00fcrde {mini_name} t\u00f6ten."
        else:
            if winner_data is None:
                return DuelOutcome("Unentschieden oder kein Schaden.")
            winner, time = winner_data
            if winner == "a":
                header = (
                    f"{name_a} w\u00fcrde {name_b} nach {time:.1f} Sekunden besiegen."
                )
            else:
                header = (
                    f"{name_b} w\u00fcrde {name_a} nach {time:.1f} Sekunden besiegen."
                )

        def _fmt_stats(base: dict, scaled: dict, lvl: int) -> str:
            dmg_key = "damage" if "damage" in base else "area_damage"
            dmg_scaled = scaled.get(dmg_key, 0)
            hp_scaled = scaled.get("health", 0)
            dps_scaled = scaled.get("dps", base.get("dps", 0))
            return (
                f"Level {lvl}: Schaden {dmg_scaled:.0f}, "
                f"DPS {dps_scaled:.0f}, HP {hp_scaled:.0f}"
            )

        parts = [f"{header}\n"]

        parts.append(
            f"\n{name_a} (Level {level_a})\n{_fmt_stats(base_a, stats_a, level_a)}"
        )
        if not is_spell_b or is_spell_a:
            parts.append(f"DPS gegen {name_b}: {dps_a:.1f}")
            for note in notes_a:
                parts.append(f"- {note}")

        parts.append(
            f"\n{name_b} (Level {level_b})\n{_fmt_stats(base_b, stats_b, level_b)}"
        )
        if not is_spell_a or is_spell_b:
            parts.append(f"DPS gegen {name_a}: {dps_b:.1f}")
            for note in notes_b:
                parts.append(f"- {note}")

        text = "\n".join(parts)

        return DuelOutcome(text)

    async def send_mini_embed(
        self, interaction, unit_id, lang, public: bool = False
    ) -> None:
        """Send an embed with mini details as an ephemeral followup."""
        try:
            embed, logo_file = self.create_mini_embed(unit_id, lang)
            if embed is None:
                await interaction.followup.send(
                    f"Details für Mini mit ID '{unit_id}' nicht gefunden.",
                    ephemeral=not public,
                )
            else:
                if logo_file:
                    await interaction.followup.send(
                        embed=embed, file=logo_file, ephemeral=not public
                    )
                else:
                    await interaction.followup.send(embed=embed, ephemeral=not public)
        except Exception as e:
            logger.error(
                f"Error sending embed for unit_id {unit_id}: {e}",
                exc_info=True,
            )
            await interaction.followup.send(
                "Ein Fehler ist aufgetreten.", ephemeral=not public
            )

    def cog_unload(self):
        """Nothing to clean up when unloading the cog."""
        return
