# cogs/wcr/cog.py

import discord
from discord.ext import commands
import os

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

        # Mapping for resolving unit names quickly: {lang: {normalized_name: id}}
        self.unit_name_map: dict[str, dict[str, int]] = {}
        for lang, texts in self.languages.items():
            name_map: dict[str, int] = {}
            for unit in texts.get("units", []):
                normalized = " ".join(helpers.normalize_name(unit.get("name", "")))
                name_map[normalized] = unit.get("id")
            self.unit_name_map[lang] = name_map
        helpers.build_category_lookup(self.languages, self.pictures)

        # Emojis liegen in bot.data["emojis"]
        self.emojis = bot.data["emojis"]

        # Cached lists for the autocomplete callbacks -----------------------
        # Unique elixir costs found in ``self.units``
        self.costs = sorted({unit["cost"] for unit in self.units})

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

    # ─── Autocomplete-Callbacks ─────────────────────────────────────────
    async def cost_autocomplete(self, interaction: discord.Interaction, current: str):
        """Provide autocomplete suggestions for unit costs."""
        return [
            discord.app_commands.Choice(name=str(c), value=str(c))
            for c in self.costs
            if current.lower() in str(c).lower()
        ][:25]

    async def speed_autocomplete(self, interaction: discord.Interaction, current: str):
        """Autocomplete unit speeds."""
        return [
            choice
            for choice in self.speed_choices
            if current.lower() in choice.name.lower()
        ][:25]

    async def faction_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        """Autocomplete factions."""
        return [
            choice
            for choice in self.faction_choices
            if current.lower() in choice.name.lower()
        ][:25]

    async def type_autocomplete(self, interaction: discord.Interaction, current: str):
        """Autocomplete unit types."""
        return [
            choice
            for choice in self.type_choices
            if current.lower() in choice.name.lower()
        ][:25]

    async def trait_autocomplete(self, interaction: discord.Interaction, current: str):
        """Autocomplete unit traits."""
        return [
            choice
            for choice in self.trait_choices
            if current.lower() in choice.name.lower()
        ][:25]

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
                ephemeral=True,
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
                    f"Kosten '{cost}' ist keine gültige Zahl.", ephemeral=True
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
                    f"Geschwindigkeit '{speed}' nicht gefunden.", ephemeral=True
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
                    f"Fraktion '{faction}' nicht gefunden.", ephemeral=True
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
                    f"Typ '{type}' nicht gefunden.", ephemeral=True
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
                    f"Merkmal '{trait}' nicht gefunden.", ephemeral=True
                )
                return
            filtered_units = [
                u for u in filtered_units if trait_id in u.get("traits_ids", [])
            ]

        if not filtered_units:
            await interaction.response.send_message(
                "Keine Minis gefunden, die den angegebenen Kriterien entsprechen.",
                ephemeral=True,
            )
            return

        if len(filtered_units) > 25:
            await interaction.response.send_message(
                "Zu viele Ergebnisse. Bitte verfeinere deine Filter.", ephemeral=True
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

        view = MiniSelectView(options, self, lang)
        await interaction.response.send_message(
            "Gefundene Minis:", view=view, ephemeral=True
        )

    async def cmd_name(
        self, interaction: discord.Interaction, name: str, lang: str = "de"
    ):
        """Implementation for the ``/wcr name`` command."""
        logger.info(
            f"[WCR] /wcr name von {interaction.user} - name={name}, lang={lang}"
        )
        await interaction.response.defer(ephemeral=True)

        try:
            embed, logo_file = self.create_mini_embed(name, lang)
        except Exception as e:
            logger.error(f"Fehler in create_mini_embed: {e}", exc_info=True)
            await interaction.followup.send(
                "Ein Fehler ist aufgetreten.", ephemeral=True
            )
            return

        if embed is None:
            await interaction.followup.send(
                f"Mini mit Namen '{name}' nicht gefunden.", ephemeral=True
            )
        else:
            if logo_file:
                await interaction.followup.send(
                    embed=embed, file=logo_file, ephemeral=True
                )
            else:
                await interaction.followup.send(embed=embed, ephemeral=True)

    def create_mini_embed(self, name_or_id, lang):
        result = self.resolve_unit(name_or_id, lang)
        if not result:
            return None, None
        if lang not in self.languages:
            return None, None

        unit_id, unit_data, lang, texts = result

        return self.build_mini_embed(unit_id, unit_data, lang, texts)

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
            unit_id = self.unit_name_map.get(lang, {}).get(normalized)
            if unit_id is None:
                for other_lang, mapping in self.unit_name_map.items():
                    if other_lang == lang:
                        continue
                    if normalized in mapping:
                        unit_id = mapping[normalized]
                        lang = other_lang
                        texts = self.languages[other_lang]
                        break
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

    async def send_mini_embed(self, interaction, unit_id, lang) -> None:
        """Send an embed with mini details as an ephemeral followup."""
        try:
            embed, logo_file = self.create_mini_embed(unit_id, lang)
            if embed is None:
                await interaction.followup.send(
                    f"Details für Mini mit ID '{unit_id}' nicht gefunden.",
                    ephemeral=True,
                )
            else:
                if logo_file:
                    await interaction.followup.send(
                        embed=embed, file=logo_file, ephemeral=True
                    )
                else:
                    await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(
                f"Fehler beim Senden des Embeds für unit_id {unit_id}: {e}",
                exc_info=True,
            )
            await interaction.followup.send(
                "Ein Fehler ist aufgetreten.", ephemeral=True
            )

    def cog_unload(self):
        """Nothing to clean up when unloading the cog."""
        return
