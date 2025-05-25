# cogs/wcr/cog.py

import discord
from discord.ext import commands
import os
import logging
from . import data_loader
from . import helpers
from .views import MiniSelectView
import itertools

logger = logging.getLogger(__name__)

# Hauptserver-ID aus der Umgebungsvariablen lesen
SERVER_ID = os.getenv('server_id')
if SERVER_ID is None:
    raise ValueError("Environment variable 'server_id' is not set.")
MAIN_SERVER_ID = int(SERVER_ID)


class WCRCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.units = data_loader.load_units()
        self.languages = data_loader.load_languages()
        self.pictures = data_loader.load_pictures()
        self.emojis = data_loader.load_emojis()

    # ─── Autocomplete-Callbacks ─────────────────────────────────────────
    async def cost_autocomplete(self, interaction: discord.Interaction, current: str):
        costs = sorted(set(unit["cost"] for unit in self.units))
        return [
            discord.app_commands.Choice(name=str(c), value=str(c))
            for c in costs if current.lower() in str(c).lower()
        ][:25]

    async def speed_autocomplete(self, interaction: discord.Interaction, current: str):
        speeds = self.languages['en']['categories']['speeds']
        return [
            discord.app_commands.Choice(name=s['name'], value=str(s['id']))
            for s in speeds if current.lower() in s['name'].lower()
        ][:25]

    async def faction_autocomplete(self, interaction: discord.Interaction, current: str):
        factions = self.languages['en']['categories']['factions']
        return [
            discord.app_commands.Choice(name=f['name'], value=str(f['id']))
            for f in factions if current.lower() in f['name'].lower()
        ][:25]

    async def type_autocomplete(self, interaction: discord.Interaction, current: str):
        types = self.languages['en']['categories']['types']
        return [
            discord.app_commands.Choice(name=t['name'], value=str(t['id']))
            for t in types if current.lower() in t['name'].lower()
        ][:25]

    async def trait_autocomplete(self, interaction: discord.Interaction, current: str):
        traits = self.languages['en']['categories']['traits']
        return [
            discord.app_commands.Choice(name=t['name'], value=str(t['id']))
            for t in traits if current.lower() in t['name'].lower()
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
        lang: str = "de"
    ):
        """Logik für /wcr filter"""
        logger.info(f"[WCR] /wcr filter von {interaction.user} - "
                    f"cost={cost}, speed={speed}, faction={faction}, type={type}, trait={trait}, lang={lang}")

        if lang not in self.languages:
            await interaction.response.send_message(
                "Sprache nicht unterstützt. Verfügbar: " +
                ", ".join(self.languages.keys()),
                ephemeral=True
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
                    ephemeral=True
                )
                return
            filtered_units = [
                u for u in filtered_units if u.get("cost") == cost_value]

        # Geschwindigkeit filtern
        if speed is not None:
            speed_id = int(speed) if speed.isdigit() else helpers.find_category_id(
                speed, 'speeds', lang, self.languages)
            if speed_id is None:
                await interaction.response.send_message(
                    f"Geschwindigkeit '{speed}' nicht gefunden.",
                    ephemeral=True
                )
                return
            filtered_units = [
                u for u in filtered_units if u.get("speed_id") == speed_id]

        # Fraktion filtern
        if faction is not None:
            faction_id = int(faction) if faction.isdigit() else helpers.find_category_id(
                faction, 'factions', lang, self.languages)
            if faction_id is None:
                await interaction.response.send_message(
                    f"Fraktion '{faction}' nicht gefunden.",
                    ephemeral=True
                )
                return
            filtered_units = [u for u in filtered_units if u.get(
                "faction_id") == faction_id]

        # Typ filtern
        if type is not None:
            type_id = int(type) if type.isdigit() else helpers.find_category_id(
                type, 'types', lang, self.languages)
            if type_id is None:
                await interaction.response.send_message(
                    f"Typ '{type}' nicht gefunden.",
                    ephemeral=True
                )
                return
            filtered_units = [
                u for u in filtered_units if u.get("type_id") == type_id]

        # Merkmal filtern
        if trait is not None:
            trait_id = int(trait) if trait.isdigit() else helpers.find_category_id(
                trait, 'traits', lang, self.languages)
            if trait_id is None:
                await interaction.response.send_message(
                    f"Merkmal '{trait}' nicht gefunden.",
                    ephemeral=True
                )
                return
            filtered_units = [
                u for u in filtered_units if trait_id in u.get("traits_ids", [])]

        if not filtered_units:
            await interaction.response.send_message(
                "Keine Minis gefunden, die den angegebenen Kriterien entsprechen.",
                ephemeral=True
            )
            return

        if len(filtered_units) > 25:
            await interaction.response.send_message(
                "Zu viele Ergebnisse. Bitte verfeinere deine Filter.",
                ephemeral=True
            )
            return

        options = []
        for unit in filtered_units:
            unit_id = unit["id"]
            unit_text = next(
                (u for u in texts["units"] if u["id"] == unit_id), {})
            unit_name = unit_text.get("name", "Unbekannt")
            emoji = self.emojis.get(
                helpers.get_faction_icon(unit["faction_id"], self.pictures), {}
            ).get("syntax", "")
            options.append(discord.SelectOption(
                label=unit_name, value=str(unit_id), emoji=emoji
            ))

        view = MiniSelectView(options, self, lang)
        await interaction.response.send_message("Gefundene Minis:", view=view, ephemeral=True)

    async def cmd_name(
        self,
        interaction: discord.Interaction,
        name: str,
        lang: str = "de"
    ):
        """Logik für /wcr name"""
        logger.info(
            f"[WCR] /wcr name von {interaction.user} - name={name}, lang={lang}")
        await interaction.response.defer(ephemeral=True)

        try:
            embed, logo_file = self.create_mini_embed(name, lang)
        except Exception as e:
            logger.error(f"Fehler in create_mini_embed: {e}", exc_info=True)
            await interaction.followup.send("Ein Fehler ist aufgetreten.", ephemeral=True)
            return

        if embed is None:
            await interaction.followup.send(
                f"Mini mit Namen '{name}' nicht gefunden.",
                ephemeral=True
            )
        else:
            if logo_file:
                await interaction.followup.send(embed=embed, file=logo_file, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, ephemeral=True)

    def create_mini_embed(self, name_or_id, lang):
        if lang not in self.languages:
            return None, None

        texts = self.languages[lang]

        # Versuche, name_or_id als ID zu behandeln
        try:
            unit_id = int(name_or_id)
            # Finde die Einheit in der units-Liste anhand der ID
            matching_unit = next(
                (unit for unit in self.units if unit["id"] == unit_id), None)
            if not matching_unit:
                return None, None
            # Hole den Einheitentext
            matching_unit_text = next(
                (unit for unit in texts["units"] if unit["id"] == unit_id), None)
            if not matching_unit_text:
                return None, None
        except ValueError:
            # Ist keine ID, behandle es als Namen
            input_words = helpers.normalize_name(name_or_id)
            permutations = [' '.join(p) for i in range(1, len(input_words) + 1)
                            for p in itertools.permutations(input_words, i)]

            unit_found = False
            matching_unit_text = None

            # Suche in der gewählten Sprache
            for permuted_name in permutations:
                for unit in texts["units"]:
                    unit_name_normalized = ' '.join(
                        helpers.normalize_name(unit["name"]))
                    if permuted_name in unit_name_normalized:
                        matching_unit_text = unit
                        unit_found = True
                        break
                if unit_found:
                    break

            # Wenn nicht gefunden, suche in anderen Sprachen
            if not unit_found:
                for other_lang, other_texts in self.languages.items():
                    if other_lang == lang:
                        continue
                    for permuted_name in permutations:
                        for unit in other_texts["units"]:
                            unit_name_normalized = ' '.join(
                                helpers.normalize_name(unit["name"]))
                            if permuted_name in unit_name_normalized:
                                matching_unit_text = unit
                                lang = other_lang  # Sprache wechseln
                                texts = other_texts
                                unit_found = True
                                break
                        if unit_found:
                            break
                    if unit_found:
                        break

            if not unit_found:
                return None, None

            unit_id = matching_unit_text["id"]
            matching_unit = next(
                (unit for unit in self.units if unit["id"] == unit_id), None)
            if not matching_unit:
                return None, None

        unit_name, unit_description, talents = helpers.get_text_data(
            unit_id, lang, self.languages)
        stats = matching_unit.get("stats", {})

        # Stat Labels laden
        stat_labels = texts.get('stat_labels', {})

        # Fraktionsdaten ermitteln
        faction_id = matching_unit.get("faction_id")
        faction_data = helpers.get_faction_data(faction_id, self.pictures)
        embed_color_hex = faction_data.get("color", "#3498db")
        embed_color = int(embed_color_hex.strip("#"), 16)
        # Suchen nach 'icon' für das Emoji
        faction_emoji_name = faction_data.get("icon", "")
        faction_emoji = self.emojis.get(
            faction_emoji_name, {}).get("syntax", "")

        # Typ-Namen erhalten
        type_id = matching_unit.get("type_id")
        type_name = helpers.get_category_name(
            "types", type_id, lang, self.languages)

        # Geschwindigkeit ermitteln
        speed_id = matching_unit.get("speed_id")
        speed_name = helpers.get_category_name(
            "speeds", speed_id, lang, self.languages)

        # Stats vorbereiten
        row1_stats = []
        row2_stats = []
        row3_stats = []
        extra_stats = []

        # Erste Reihe: Kosten und Typ
        cost = matching_unit.get("cost", "N/A")
        row1_stats.append({
            "name": f"{self.emojis.get('wcr_cost', {}).get('syntax', '')} {stat_labels.get('cost', 'Kosten')}",
            "value": str(cost),
            "inline": True
        })

        row1_stats.append({
            "name": f"{self.emojis.get('wcr_type', {}).get('syntax', '')} {stat_labels.get('type_id', 'Typ')}",
            "value": type_name,
            "inline": True
        })

        # Zweite Reihe: Gesundheit und Geschwindigkeit
        health = stats.get("health")
        if health is not None:
            row2_stats.append({
                "name": f"{self.emojis.get('wcr_health', {}).get('syntax', '')} {stat_labels.get('health', 'Gesundheit')}",
                "value": str(health),
                "inline": True
            })

        if speed_name:
            row2_stats.append({
                "name": f"{self.emojis.get('wcr_speed', {}).get('syntax', '')} {stat_labels.get('speed_id', 'Geschwindigkeit')}",
                "value": speed_name,
                "inline": True
            })

        # Dritte Reihe: Schaden, Angriffsgeschwindigkeit, DPS
        is_elemental = 8 in matching_unit.get("traits_ids", [])

        if "damage" in stats or "area_damage" in stats:
            if "damage" in stats:
                damage_value = stats["damage"]
                if is_elemental:
                    damage_label = stat_labels.get(
                        'damage', 'Elementarschaden')
                    damage_emoji = self.emojis.get(
                        'wcr_damage_ele', {}).get('syntax', '')
                else:
                    damage_label = stat_labels.get('damage', 'Schaden')
                    damage_emoji = self.emojis.get(
                        'wcr_damage', {}).get('syntax', '')
            elif "area_damage" in stats:
                damage_value = stats["area_damage"]
                if is_elemental:
                    damage_label = stat_labels.get(
                        'area_damage', 'Elementarflächenschaden')
                    damage_emoji = self.emojis.get(
                        'wcr_damage_ele', {}).get('syntax', '')
                else:
                    damage_label = stat_labels.get(
                        'area_damage', 'Flächenschaden')
                    damage_emoji = self.emojis.get(
                        'wcr_damage', {}).get('syntax', '')
            row3_stats.append({
                "name": f"{damage_emoji} {damage_label}",
                "value": str(damage_value),
                "inline": True
            })

        attack_speed = stats.get("attack_speed")
        if attack_speed is not None:
            row3_stats.append({
                "name": f"{self.emojis.get('wcr_attack_speed', {}).get('syntax', '')} {stat_labels.get('attack_speed', 'Angriffsgeschwindigkeit')}",
                "value": str(attack_speed),
                "inline": True
            })

        dps = stats.get("dps")
        if dps is not None:
            row3_stats.append({
                "name": f"{self.emojis.get('wcr_dps', {}).get('syntax', '')} {stat_labels.get('dps', 'DPS')}",
                "value": str(dps),
                "inline": True
            })

        # Übrige Stats sammeln
        used_stats_keys = {'damage', 'area_damage',
                           'attack_speed', 'dps', 'health'}

        for stat_key, emoji_name in [("range", "wcr_range"), ("duration", "wcr_duration"), ("healing", "wcr_healing"), ("radius", "wcr_radius"), ("lvl_advantage", "wcr_advantage"), ("percent_dmg", "wcr_percent_dmg"), ("percent_dps", "wcr_percent_dps"), ("fan_damage", "wcr_fan_damage"), ("crash_damage", "wcr_crash_damage"), ("area_healing", "wcr_area_healing"), ("dwarf_dmg", "wcr_damage"), ("bear_dmg", "wcr_damage"), ("dwarf_dps", "wcr_dps"), ("bear_dps", "wcr_dps"), ("dwarf_health", "wcr_health"), ("bear_health", "wcr_health"), ("dwarf_range", "wcr_range")]:
            if stat_key in stats and stat_key not in used_stats_keys:
                label = stat_labels.get(stat_key, stat_key.capitalize())
                extra_stats.append({
                    "name": f"{self.emojis.get(emoji_name, {}).get('syntax', '')} {label}",
                    "value": str(stats[stat_key]),
                    "inline": True
                })
                used_stats_keys.add(stat_key)

        # Embed erstellen
        embed = discord.Embed(
            title=f"{faction_emoji} {unit_name}",
            description=unit_description,
            color=embed_color
        )

        # Kleiner Absatz nach der Beschreibung
        embed.description += "\n"
        embed.description += "\n **Stats**"

        # Stats hinzufügen
        if row1_stats:
            for stat in row1_stats:
                embed.add_field(
                    name=stat["name"], value=stat["value"], inline=stat.get("inline", True))
            # Fülle die Reihe auf, wenn weniger als 3 Felder
            while len(row1_stats) < 3:
                embed.add_field(name="\u200b", value="\u200b", inline=True)
                row1_stats.append(None)

        if row2_stats:
            for stat in row2_stats:
                embed.add_field(
                    name=stat["name"], value=stat["value"], inline=stat.get("inline", True))
            while len(row2_stats) < 3:
                embed.add_field(name="\u200b", value="\u200b", inline=True)
                row2_stats.append(None)

        if row3_stats:
            for stat in row3_stats:
                embed.add_field(
                    name=stat["name"], value=stat["value"], inline=stat.get("inline", True))
            while len(row3_stats) < 3:
                embed.add_field(name="\u200b", value="\u200b", inline=True)
                row3_stats.append(None)

        # Übrige Stats hinzufügen, jeweils bis zu drei pro Reihe
        if extra_stats:
            for i in range(0, len(extra_stats), 3):
                group = extra_stats[i:i+3]
                for stat in group:
                    embed.add_field(
                        name=stat["name"], value=stat["value"], inline=stat.get("inline", True))
                # Fülle die Reihe auf, wenn weniger als 3 Felder
                while len(group) < 3:
                    embed.add_field(name="\u200b", value="\u200b", inline=True)
                    group.append(None)

        # Talente hinzufügen
        if talents:
            # Kleiner Abstand vor den Talenten
            embed.add_field(name="\u200b", value="**Talents**", inline=False)
            for talent in talents[:3]:
                talent_name = talent.get("name", "Unbekanntes Talent")
                talent_description = talent.get(
                    "description", "Beschreibung fehlt")
                embed.add_field(name=talent_name,
                                value=talent_description, inline=True)
            # Falls weniger als 3 Talente, Reihe auffüllen
            if len(talents[:3]) % 3 != 0:
                for _ in range(3 - (len(talents[:3]) % 3)):
                    embed.add_field(name="\u200b", value="\u200b", inline=True)

        # Traits hinzufügen
        traits_ids = matching_unit.get("traits_ids", [])
        traits = []
        all_traits = texts.get("categories", {}).get("traits", [])
        for trait_id in traits_ids:
            trait = next((t for t in all_traits if t["id"] == trait_id), None)
            if trait:
                traits.append(trait["name"])

        if traits:
            embed.add_field(name=stat_labels.get('traits', 'Traits'),
                            value=', '.join(traits), inline=False)

        # Setze das Thumbnail (Pose)
        pose_url = helpers.get_pose_url(unit_id, self.pictures)
        if pose_url:
            embed.set_thumbnail(url=pose_url)

        # Logo hinzufügen
        logo_filename = 'LotusGaming.png'
        logo_path = os.path.join('data', 'media', logo_filename)
        if os.path.exists(logo_path):
            embed.set_footer(
                text='a service brought to you by Lotus Gaming', icon_url=f'attachment://{logo_filename}')
            logo_file = discord.File(logo_path, filename=logo_filename)
        else:
            embed.set_footer(text='a service brought to you by Lotus Gaming')
            logo_file = None

        return embed, logo_file

    async def send_mini_embed(self, interaction, unit_id, lang):
        try:
            embed, logo_file = self.create_mini_embed(unit_id, lang)
            if embed is None:
                await interaction.followup.send(
                    f"Details für Mini mit ID '{unit_id}' nicht gefunden.",
                    ephemeral=True
                )
            else:
                if logo_file:
                    await interaction.followup.send(embed=embed, file=logo_file, ephemeral=True)
                else:
                    await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(
                f"Fehler beim Senden des Embeds für unit_id {unit_id}: {e}", exc_info=True)
            await interaction.followup.send("Ein Fehler ist aufgetreten.", ephemeral=True)
