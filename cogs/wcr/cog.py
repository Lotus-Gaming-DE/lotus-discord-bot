# cogs/wcr/cog.py

import discord
from discord.ext import commands
import os
import difflib

from log_setup import get_logger
from . import helpers
from .views import MiniSelectView

logger = get_logger(__name__)


class WCRCog(commands.Cog):
    def __init__(self, bot) -> None:
        """Cog providing Warcraft Rumble helper commands."""
        self.bot = bot

        # === WICHTIG ===
        # Statt bot.quiz_data[...] nutzen wir jetzt bot.data["wcr"][...],
        # das bereits in bot.py im setup_hook gefüllt wird.
        self.units = bot.data["wcr"]["units"]
        if isinstance(self.units, dict) and "units" in self.units:
            self.units = self.units["units"]
        self.languages = bot.data["wcr"]["locals"]
        self.pictures = bot.data["wcr"]["pictures"]

        # Mapping for resolving unit names quickly
        # {lang: {normalized_name: id}}
        self.unit_name_map: dict[str, dict[str, int]] = {}
        # Reverse mapping and token index for fuzzy search
        # {lang: {id: normalized_name}}
        self.id_name_map: dict[str, dict[int, str]] = {}
        # {lang: {token: set(ids)}}
        self.name_token_index: dict[str, dict[str, set[int]]] = {}

        for lang, texts in self.languages.items():
            name_map: dict[str, int] = {}
            id_map: dict[int, str] = {}
            token_index: dict[str, set[int]] = {}
            for unit in texts.get("units", []):
                normalized = " ".join(helpers.normalize_name(unit.get("name", "")))
                unit_id = unit.get("id")
                name_map[normalized] = unit_id
                id_map[unit_id] = normalized
                for token in normalized.split():
                    token_index.setdefault(token, set()).add(unit_id)
            self.unit_name_map[lang] = name_map
            self.id_name_map[lang] = id_map
            self.name_token_index[lang] = token_index

        (
            self.lang_category_lookup,
            self.picture_category_lookup,
        ) = helpers.build_category_lookup(self.languages, self.pictures)

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

        cats = self.languages[cats_lang]["categories"]
        self.speed_choices = [
            discord.app_commands.Choice(name=s["name"], value=str(s["id"]))
            for s in cats["speeds"]
        ]
        self.faction_choices = [
            discord.app_commands.Choice(name=f["name"], value=str(f["id"]))
            for f in cats["factions"]
        ]
        self.type_choices = [
            discord.app_commands.Choice(name=t["name"], value=str(t["id"]))
            for t in cats["types"]
        ]
        self.trait_choices = [
            discord.app_commands.Choice(name=t["name"], value=str(t["id"]))
            for t in cats["traits"]
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
            f"[WCR] /wcr filter von {interaction.user} - "
            f"cost={cost}, speed={speed}, faction={faction}, type={type}, trait={trait}, lang={lang}"
        )

        if lang not in self.languages:
            await interaction.response.send_message(
                "Sprache nicht unterstützt. Verfügbar: "
                + ", ".join(self.languages.keys()),
                ephemeral=not public,
            )
            return

        texts = self.languages[lang]
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
                int(speed)
                if speed.isdigit()
                else helpers.find_category_id(speed, "speeds", lang, self.languages)
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
                int(faction)
                if faction.isdigit()
                else helpers.find_category_id(faction, "factions", lang, self.languages)
            )
            if faction_id is None:
                await interaction.response.send_message(
                    f"Fraktion '{faction}' nicht gefunden.",
                    ephemeral=not public,
                )
                return
            filtered_units = [
                u for u in filtered_units if u.get("faction_id") == faction_id
            ]

        # Typ filtern
        if type is not None:
            type_id = (
                int(type)
                if type.isdigit()
                else helpers.find_category_id(type, "types", lang, self.languages)
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
                int(trait)
                if trait.isdigit()
                else helpers.find_category_id(trait, "traits", lang, self.languages)
            )
            if trait_id is None:
                await interaction.response.send_message(
                    f"Merkmal '{trait}' nicht gefunden.",
                    ephemeral=not public,
                )
                return
            filtered_units = [
                u for u in filtered_units if trait_id in u.get("traits_ids", [])
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
            unit_text = next((u for u in texts["units"] if u["id"] == unit_id), {})
            unit_name = unit_text.get("name", "Unbekannt")
            emoji_syntax = self.emojis.get(
                helpers.get_faction_icon(unit["faction_id"], self.pictures), {}
            ).get("syntax")
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
            f"[WCR] /wcr name von {interaction.user} - name={name}, lang={lang}"
        )
        await interaction.response.defer(ephemeral=not public)

        try:
            embed, logo_file = self.create_mini_embed(name, lang)
        except Exception as e:
            logger.error(f"Fehler in create_mini_embed: {e}", exc_info=True)
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
        level_a: int,
        mini_b: str,
        level_b: int,
        lang: str = "de",
        public: bool = False,
    ):
        """Implementation for ``/wcr duell``."""
        if lang not in self.languages:
            await interaction.response.send_message(
                "Sprache nicht unterstützt. Verfügbar: "
                + ", ".join(self.languages.keys()),
                ephemeral=not public,
            )
            return

        logger.info(
            f"[WCR] /wcr duell von {interaction.user} - "
            f"mini_a={mini_a}, level_a={level_a}, "
            f"mini_b={mini_b}, level_b={level_b}, lang={lang}"
        )
        await interaction.response.defer(ephemeral=not public)

        res_a = self.resolve_unit(mini_a, lang)
        res_b = self.resolve_unit(mini_b, lang)
        if not res_a or not res_b:
            await interaction.followup.send(
                "Eines der Minis wurde nicht gefunden.", ephemeral=not public
            )
            return

        id_a, data_a, lang_a, texts_a = res_a
        id_b, data_b, lang_b, texts_b = res_b

        name_a = helpers.get_text_data(id_a, lang_a, self.languages)[0]
        name_b = helpers.get_text_data(id_b, lang_b, self.languages)[0]

        base_a = data_a.get("stats", {})
        base_b = data_b.get("stats", {})
        stats_a = self._scaled_stats(data_a, level_a)
        stats_b = self._scaled_stats(data_b, level_b)

        dps_a = self._compute_dps(data_a, stats_a, data_b)
        dps_b = self._compute_dps(data_b, stats_b, data_a)

        winner_data = self.duel_result(data_a, level_a, data_b, level_b)

        is_spell_a = data_a.get("type_id") == 2
        is_spell_b = data_b.get("type_id") == 2

        if is_spell_a and is_spell_b:
            if winner_data is None:
                header = "Beide Zauber verursachen gleich viel Schaden."
            else:
                winner, _ = winner_data
                if winner == "a":
                    header = (
                        f"Zauber {name_a} hat mehr DPS und w\u00fcrde daher {name_b} "
                        "outperformen."
                    )
                else:
                    header = (
                        f"Zauber {name_b} hat mehr DPS und w\u00fcrde daher {name_a} "
                        "outperformen."
                    )
        elif is_spell_a or is_spell_b:
            spell_name = name_a if is_spell_a else name_b
            mini_name = name_b if is_spell_a else name_a
            if winner_data is None:
                header = f"{spell_name} w\u00fcrde {mini_name} nicht t\u00f6ten."
            else:
                header = f"{spell_name} w\u00fcrde {mini_name} t\u00f6ten."
        else:
            if winner_data is None:
                await interaction.followup.send(
                    "Unentschieden oder kein Schaden.", ephemeral=not public
                )
                return
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

        def _flight_issue(att: dict, def_: dict) -> bool:
            ta = att.get("traits_ids", [])
            td = def_.get("traits_ids", [])
            if att.get("type_id") == 2:
                return False
            return 15 in td and 11 not in ta and 15 not in ta

        issue_a = _flight_issue(data_a, data_b)
        issue_b = _flight_issue(data_b, data_a)

        parts = [f"{header}\n"]

        parts.append(
            f"\n{name_a} (Level {level_a})\n{_fmt_stats(base_a, stats_a, level_a)}"
        )
        if not is_spell_b or is_spell_a:
            line = f"DPS gegen {name_b}: {dps_a:.1f}"
            if issue_a:
                line += " (kann Flieger nicht treffen)"
            parts.append(line)

        parts.append(
            f"\n{name_b} (Level {level_b})\n{_fmt_stats(base_b, stats_b, level_b)}"
        )
        if not is_spell_a or is_spell_b:
            line = f"DPS gegen {name_a}: {dps_b:.1f}"
            if issue_b:
                line += " (kann Flieger nicht treffen)"
            parts.append(line)

        text = "\n".join(parts)

        await interaction.followup.send(text, ephemeral=not public)

    def create_mini_embed(self, name_or_id, lang):
        result = self.resolve_unit(name_or_id, lang)
        if not result:
            return None, None
        if lang not in self.languages:
            return None, None

        unit_id, unit_data, lang, texts = result

        return self.build_mini_embed(unit_id, unit_data, lang, texts)

    def _find_unit_id_by_name(
        self, normalized: str, lang: str
    ) -> tuple[int | None, str]:
        """Search a unit ID by normalized name with fuzzy matching."""
        mapping = self.unit_name_map.get(lang, {})
        id_map = self.id_name_map.get(lang, {})
        token_index = self.name_token_index.get(lang, {})

        if normalized in mapping:
            return mapping[normalized], lang

        tokens = normalized.split()
        candidate_ids: set[int] = set()
        for token in tokens:
            candidate_ids.update(token_index.get(token, set()))

        if not candidate_ids:
            candidate_ids = set(mapping.values())

        for unit_id in candidate_ids:
            key = id_map.get(unit_id, "")
            if normalized in key:
                return unit_id, lang

        best_id = None
        best_ratio = 0.0
        for unit_id in candidate_ids:
            key = id_map.get(unit_id, "")
            ratio = difflib.SequenceMatcher(None, normalized, key).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_id = unit_id
        if best_ratio >= 0.6:
            return best_id, lang
        return None, lang

    def resolve_unit(self, name_or_id, lang):
        if lang not in self.languages:
            return None

        texts = self.languages[lang]

        try:
            unit_id = int(name_or_id)
            unit_data = next(
                (unit for unit in self.units if unit["id"] == unit_id), None
            )
            if not unit_data:
                return None
            matching_unit_text = next(
                (u for u in texts["units"] if u["id"] == unit_id), None
            )
            if not matching_unit_text:
                return None
        except ValueError:
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
                        texts = self.languages[found_lang]
                        break
            else:
                texts = self.languages[lang]
            if unit_id is None:
                return None

            unit_data = next(
                (unit for unit in self.units if unit["id"] == unit_id), None
            )
            if not unit_data:
                return None

        return unit_id, unit_data, lang, texts

    # Helper methods -----------------------------------------------------
    def _prepare_stat_rows(self, unit_data, stat_labels, type_name, speed_name):
        """Return stat rows and set of used stat keys."""
        stats = unit_data.get("stats", {})

        row1_stats: list[dict] = []
        row2_stats: list[dict] = []
        row3_stats: list[dict] = []

        cost = unit_data.get("cost", "N/A")
        row1_stats.append(
            {
                "name": f"{self.emojis.get('wcr_cost', {}).get('syntax', '')} "
                f"{stat_labels.get('cost', 'Kosten')}",
                "value": str(cost),
                "inline": True,
            }
        )
        row1_stats.append(
            {
                "name": f"{self.emojis.get('wcr_type', {}).get('syntax', '')} "
                f"{stat_labels.get('type_id', 'Typ')}",
                "value": type_name,
                "inline": True,
            }
        )

        health = stats.get("health")
        if health is not None:
            row2_stats.append(
                {
                    "name": f"{self.emojis.get('wcr_health', {}).get('syntax', '')} "
                    f"{stat_labels.get('health', 'Gesundheit')}",
                    "value": str(health),
                    "inline": True,
                }
            )
        if speed_name:
            row2_stats.append(
                {
                    "name": f"{self.emojis.get('wcr_speed', {}).get('syntax', '')} "
                    f"{stat_labels.get('speed_id', 'Geschwindigkeit')}",
                    "value": speed_name,
                    "inline": True,
                }
            )

        is_elemental = 8 in unit_data.get("traits_ids", [])
        if "damage" in stats or "area_damage" in stats:
            if "damage" in stats:
                damage_value = stats["damage"]
                if is_elemental:
                    damage_label = stat_labels.get("damage", "Elementarschaden")
                    damage_emoji = self.emojis.get("wcr_damage_ele", {}).get(
                        "syntax", ""
                    )
                else:
                    damage_label = stat_labels.get("damage", "Schaden")
                    damage_emoji = self.emojis.get("wcr_damage", {}).get("syntax", "")
            else:
                damage_value = stats["area_damage"]
                if is_elemental:
                    damage_label = stat_labels.get(
                        "area_damage", "Elementarflächenschaden"
                    )
                    damage_emoji = self.emojis.get("wcr_damage_ele", {}).get(
                        "syntax", ""
                    )
                else:
                    damage_label = stat_labels.get("area_damage", "Flächenschaden")
                    damage_emoji = self.emojis.get("wcr_damage", {}).get("syntax", "")
            row3_stats.append(
                {
                    "name": f"{damage_emoji} {damage_label}",
                    "value": str(damage_value),
                    "inline": True,
                }
            )

        attack_speed = stats.get("attack_speed")
        if attack_speed is not None:
            row3_stats.append(
                {
                    "name": f"{self.emojis.get('wcr_attack_speed', {}).get('syntax', '')} "
                    f"{stat_labels.get('attack_speed', 'Angriffsgeschwindigkeit')}",
                    "value": str(attack_speed),
                    "inline": True,
                }
            )

        dps = stats.get("dps")
        if dps is not None:
            row3_stats.append(
                {
                    "name": f"{self.emojis.get('wcr_dps', {}).get('syntax', '')} "
                    f"{stat_labels.get('dps', 'DPS')}",
                    "value": str(dps),
                    "inline": True,
                }
            )

        used_stats_keys = {"damage", "area_damage", "attack_speed", "dps", "health"}
        return row1_stats, row2_stats, row3_stats, stats, used_stats_keys

    def _prepare_extra_stats(self, stats, stat_labels, used_stats_keys):
        """Return a list with remaining stats."""
        extra_stats: list[dict] = []
        for stat_key, emoji_name in [
            ("range", "wcr_range"),
            ("duration", "wcr_duration"),
            ("healing", "wcr_healing"),
            ("radius", "wcr_radius"),
            ("lvl_advantage", "wcr_advantage"),
            ("percent_dmg", "wcr_percent_dmg"),
            ("percent_dps", "wcr_percent_dps"),
            ("fan_damage", "wcr_fan_damage"),
            ("crash_damage", "wcr_crash_damage"),
            ("area_healing", "wcr_area_healing"),
            ("dwarf_dmg", "wcr_damage"),
            ("bear_dmg", "wcr_damage"),
            ("dwarf_dps", "wcr_dps"),
            ("bear_dps", "wcr_dps"),
            ("dwarf_health", "wcr_health"),
            ("bear_health", "wcr_health"),
            ("dwarf_range", "wcr_range"),
        ]:
            if stat_key in stats and stat_key not in used_stats_keys:
                label = stat_labels.get(stat_key, stat_key.capitalize())
                extra_stats.append(
                    {
                        "name": f"{self.emojis.get(emoji_name, {}).get('syntax', '')} {label}",
                        "value": str(stats[stat_key]),
                        "inline": True,
                    }
                )
                used_stats_keys.add(stat_key)
        return extra_stats

    def _prepare_talent_fields(self, talents):
        """Return fields for talents."""
        fields: list[dict] = []
        if not talents:
            return fields
        fields.append({"name": "\u200b", "value": "**Talents**", "inline": False})
        for talent in talents[:3]:
            fields.append(
                {
                    "name": talent.get("name", "Unbekanntes Talent"),
                    "value": talent.get("description", "Beschreibung fehlt"),
                    "inline": True,
                }
            )
        remainder = len(talents[:3]) % 3
        if remainder:
            for _ in range(3 - remainder):
                fields.append({"name": "\u200b", "value": "\u200b", "inline": True})
        return fields

    def _prepare_traits_field(self, unit_data, texts, stat_labels):
        """Return a field for trait display if traits exist."""
        traits_ids = unit_data.get("traits_ids", [])
        all_traits = texts.get("categories", {}).get("traits", [])
        names = [t["name"] for t in all_traits if t["id"] in traits_ids]
        if not names:
            return None
        return {
            "name": stat_labels.get("traits", "Traits"),
            "value": ", ".join(names),
            "inline": False,
        }

    def build_mini_embed(self, unit_id, unit_data, lang, texts):
        unit_name, unit_description, talents = helpers.get_text_data(
            unit_id, lang, self.languages
        )

        stat_labels = texts.get("stat_labels", {})
        faction_data = helpers.get_faction_data(
            unit_data.get("faction_id"), self.pictures
        )
        embed_color = int(faction_data.get("color", "#3498db").strip("#"), 16)
        faction_emoji = self.emojis.get(faction_data.get("icon", ""), {}).get(
            "syntax", ""
        )

        type_name = helpers.get_category_name(
            "types", unit_data.get("type_id"), lang, self.languages
        )
        speed_name = helpers.get_category_name(
            "speeds", unit_data.get("speed_id"), lang, self.languages
        )

        row1, row2, row3, stats, used_keys = self._prepare_stat_rows(
            unit_data, stat_labels, type_name, speed_name
        )
        extra_stats = self._prepare_extra_stats(stats, stat_labels, used_keys)
        talent_fields = self._prepare_talent_fields(talents)
        traits_field = self._prepare_traits_field(unit_data, texts, stat_labels)

        embed = discord.Embed(
            title=f"{faction_emoji} {unit_name}",
            description=f"{unit_description}\n\n**Stats**",
            color=embed_color,
        )

        def _add_group(fields: list[dict]):
            for field in fields:
                embed.add_field(
                    name=field["name"],
                    value=field["value"],
                    inline=field.get("inline", True),
                )
            while len(fields) < 3:
                embed.add_field(name="\u200b", value="\u200b", inline=True)
                fields.append(None)

        for group in (row1, row2, row3):
            if group:
                _add_group(group)

        for i in range(0, len(extra_stats), 3):
            _add_group(extra_stats[i : i + 3])

        for field in talent_fields:
            embed.add_field(
                name=field["name"],
                value=field["value"],
                inline=field.get("inline", True),
            )

        if traits_field:
            embed.add_field(
                name=traits_field["name"],
                value=traits_field["value"],
                inline=traits_field.get("inline", True),
            )

        pose_url = helpers.get_pose_url(unit_id, self.pictures)
        if pose_url:
            embed.set_thumbnail(url=pose_url)

        logo_filename = "LotusGaming.png"
        logo_path = os.path.join("data", "media", logo_filename)
        if os.path.exists(logo_path):
            embed.set_footer(
                text="a service brought to you by Lotus Gaming",
                icon_url=f"attachment://{logo_filename}",
            )
            logo_file = discord.File(logo_path, filename=logo_filename)
        else:
            embed.set_footer(text="a service brought to you by Lotus Gaming")
            logo_file = None

        return embed, logo_file

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
                f"Fehler beim Senden des Embeds für unit_id {unit_id}: {e}",
                exc_info=True,
            )
            await interaction.followup.send(
                "Ein Fehler ist aufgetreten.", ephemeral=not public
            )

    # ─── Duel Feature ------------------------------------------------------------
    def _scale_stat(self, base: float | int, level: int) -> float:
        """Return ``base`` scaled by +10% per level above 1."""
        if level < 1:
            level = 1
        return base * (1 + 0.1 * (level - 1))

    def _scaled_stats(self, unit_data: dict, level: int) -> dict:
        """Return a copy of ``unit_data['stats']`` scaled for ``level``."""
        stats = unit_data.get("stats", {})
        result = {}
        dmg_key = (
            "damage"
            if "damage" in stats
            else "area_damage" if "area_damage" in stats else None
        )
        if dmg_key:
            result[dmg_key] = self._scale_stat(stats[dmg_key], level)
        if "health" in stats:
            result["health"] = self._scale_stat(stats["health"], level)
        attack_speed = stats.get("attack_speed")
        if attack_speed is not None:
            result["attack_speed"] = attack_speed
        if dmg_key and attack_speed:
            result["dps"] = result[dmg_key] / attack_speed
        return result

    def _spell_total_damage(self, unit: dict, stats: dict) -> float:
        """Return estimated total damage a spell deals."""
        base_stats = unit.get("stats", {})
        damage = stats.get("damage", stats.get("area_damage", 0))
        if "dps" in stats:
            duration = base_stats.get("duration", 1)
            damage = max(damage, stats["dps"] * duration)
        return damage

    def _compute_dps(
        self,
        attacker: dict,
        attacker_stats: dict,
        defender: dict,
    ) -> float:
        """Calculate DPS attacker does to defender considering traits."""
        traits_a = attacker.get("traits_ids", [])
        traits_d = defender.get("traits_ids", [])

        # Check if attacker can hit flying target
        if (
            attacker.get("type_id") != 2
            and 15 in traits_d
            and 11 not in traits_a
            and 15 not in traits_a
        ):
            return 0.0

        dmg_key = (
            "damage"
            if "damage" in attacker_stats
            else "area_damage" if "area_damage" in attacker_stats else None
        )
        if dmg_key is None:
            return 0.0

        damage = attacker_stats[dmg_key]
        if 8 in traits_a and 20 in traits_d:  # elemental vs resistant
            damage *= 0.5
        elif 8 not in traits_a and 13 in traits_d:  # physical vs armored
            damage *= 0.5

        attack_speed = attacker_stats.get("attack_speed")
        if attack_speed:
            return damage / attack_speed

        if attacker.get("type_id") == 2:
            dps = attacker_stats.get("dps")
            if dps is not None:
                return dps
            return damage

        # Fallback to provided dps if available
        return attacker_stats.get("dps", 0.0)

    def duel_result(
        self,
        unit_a: dict,
        level_a: int,
        unit_b: dict,
        level_b: int,
    ) -> tuple[str, float] | None:
        """Return (winner_name, time) or None for tie/impossible."""
        stats_a = self._scaled_stats(unit_a, level_a)
        stats_b = self._scaled_stats(unit_b, level_b)

        is_spell_a = unit_a.get("type_id") == 2
        is_spell_b = unit_b.get("type_id") == 2

        dps_a = self._compute_dps(unit_a, stats_a, unit_b)
        dps_b = self._compute_dps(unit_b, stats_b, unit_a)

        if is_spell_a and is_spell_b:
            if dps_a == dps_b:
                return None
            return ("a", 0.0) if dps_a > dps_b else ("b", 0.0)

        if is_spell_a:
            total_damage = self._spell_total_damage(unit_a, stats_a)
            if total_damage >= stats_b.get("health", 0):
                return "a", 0.0
            return None

        if is_spell_b:
            total_damage = self._spell_total_damage(unit_b, stats_b)
            if total_damage >= stats_a.get("health", 0):
                return "b", 0.0
            return None

        health_a = stats_a.get("health", 0)
        health_b = stats_b.get("health", 0)

        time_a = health_b / dps_a if dps_a > 0 else float("inf")
        time_b = health_a / dps_b if dps_b > 0 else float("inf")

        if time_a == time_b:
            return None
        if time_a < time_b:
            return "a", time_a
        return "b", time_b

    def cog_unload(self):
        """Nothing to clean up when unloading the cog."""
        return
