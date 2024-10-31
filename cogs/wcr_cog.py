import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import itertools

# Hauptserver-ID aus der Umgebungsvariablen lesen
SERVER_ID = os.getenv('server_id')
if SERVER_ID is None:
    raise ValueError("Environment variable 'server_id' is not set.")
MAIN_SERVER_ID = int(SERVER_ID)


class WCRCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.units = self.load_units()
        self.languages = self.load_languages()
        self.pictures = self.load_pictures()
        self.emojis = self.load_emojis()

    def load_units(self):
        # Pfad zu 'units.json' bestimmen
        current_dir = os.path.dirname(os.path.abspath(__file__))
        units_path = os.path.join(
            current_dir, '..', 'data', 'wcr', 'units.json')
        units_path = os.path.normpath(units_path)

        with open(units_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Rückgabe der Einheitenliste
        return data['units']

    def load_languages(self):
        languages = {}
        # Pfad zum 'locals'-Verzeichnis bestimmen
        current_dir = os.path.dirname(os.path.abspath(__file__))
        locals_dir = os.path.join(
            current_dir, '..', 'data', 'wcr', 'locals')
        locals_dir = os.path.normpath(locals_dir)

        for lang_file in os.listdir(locals_dir):
            if lang_file.endswith('.json'):
                lang_code = lang_file.split('.')[0]
                with open(os.path.join(locals_dir, lang_file), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                languages[lang_code] = data
        return languages

    def load_pictures(self):
        # Pfad zu 'pictures.json' bestimmen
        current_dir = os.path.dirname(os.path.abspath(__file__))
        pictures_path = os.path.join(
            current_dir, '..', 'data', 'wcr', 'pictures.json')
        pictures_path = os.path.normpath(pictures_path)

        with open(pictures_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data

    def load_emojis(self):
        # Pfad zu 'emojis.json' bestimmen
        current_dir = os.path.dirname(os.path.abspath(__file__))
        emojis_path = os.path.join(
            current_dir, '..', 'data', 'emojis.json')
        emojis_path = os.path.normpath(emojis_path)

        with open(emojis_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data

    def get_text_data(self, unit_id, lang):
        texts = self.languages.get(lang, self.languages["de"])
        # Einheit in der Sprachdatei anhand der ID suchen
        unit_text = next(
            (unit for unit in texts["units"] if unit["id"] == unit_id), {})
        return unit_text.get("name", "Unbekannt"), unit_text.get("description", "Beschreibung fehlt"), unit_text.get("talents", [])

    def get_pose_url(self, unit_id):
        """Gibt die Pose-URL des Minis zurück, falls vorhanden."""
        unit_pictures = self.pictures.get("units", [])
        unit_picture = next(
            (pic for pic in unit_pictures if pic["id"] == unit_id), {})
        return unit_picture.get("pose", "")

    def get_faction_data(self, faction_id):
        """Gibt die Fraktionsdaten basierend auf der faction_id zurück."""
        factions = self.pictures.get("categories", {}).get("factions", [])
        faction_data = next(
            (faction for faction in factions if faction["id"] == faction_id), {})
        return faction_data

    def get_category_name(self, category, category_id, lang):
        """Gibt den Namen eines Kategorie-Elements basierend auf seiner ID zurück."""
        categories = self.languages.get(
            lang, {}).get("categories", {}).get(category, [])
        category_item = next(
            (item for item in categories if item["id"] == category_id), {})
        return category_item.get("name", "Unbekannt")

    def get_faction_icon(self, faction_id):
        faction_data = self.get_faction_data(faction_id)
        return faction_data.get("icon", "")

    def normalize_name(self, name):
        return ''.join(c for c in name if c.isalnum() or c.isspace()).lower().split()

    @app_commands.command(name="name", description="Zeigt Details zu einem Mini basierend auf dem Namen an.")
    @app_commands.guilds(discord.Object(id=MAIN_SERVER_ID))
    @app_commands.describe(name="Name des Minis", lang="Sprache")
    async def name(self, interaction: discord.Interaction, name: str, lang: str = "de"):
        print(f"Befehl /name ausgeführt mit Name: {name} und Sprache: {lang}")
        # Defer the response if processing might take time
        await interaction.response.defer()
        embed = self.create_mini_embed(name, lang)
        if embed is None:
            await interaction.followup.send(f"Mini mit Namen '{name}' nicht gefunden.")
        else:
            await interaction.followup.send(embed=embed)

    def create_mini_embed(self, name_or_id, lang):
        if lang not in self.languages:
            return None

        # Normalisiere den eingegebenen Namen oder verwende die ID
        input_words = self.normalize_name(str(name_or_id))
        permutations = [' '.join(p) for i in range(1, len(input_words) + 1)
                        for p in itertools.permutations(input_words, i)]

        unit_found = False
        matching_unit_text = None

        # Suche in der gewählten Sprache
        texts = self.languages[lang]
        for permuted_name in permutations:
            for unit in texts["units"]:
                unit_name_normalized = ' '.join(
                    self.normalize_name(unit["name"]))
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
                            self.normalize_name(unit["name"]))
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
            return None

        # Finde die Einheit in der units-Liste anhand der ID
        unit_id = matching_unit_text["id"]
        matching_unit = next(
            (unit for unit in self.units if unit["id"] == unit_id), None)

        if not matching_unit:
            return None

        unit_name, unit_description, talents = self.get_text_data(
            unit_id, lang)
        stats = matching_unit.get("stats", {})

        # Stat Labels laden
        stat_labels = texts.get('stat_labels', {})

        # Fraktionsdaten ermitteln
        faction_id = matching_unit.get("faction_id")
        faction_data = self.get_faction_data(faction_id)
        embed_color_hex = faction_data.get("color", "#3498db")
        embed_color = int(embed_color_hex.strip("#"), 16)
        # Suchen nach 'icon' für das Emoji
        faction_emoji_name = faction_data.get("icon", "")
        faction_emoji = self.emojis.get(
            faction_emoji_name, {}).get("syntax", "")

        # Typ-Namen erhalten
        type_id = matching_unit.get("type_id")
        type_name = self.get_category_name("types", type_id, lang)

        # Geschwindigkeit ermitteln
        speed_id = matching_unit.get("speed_id")
        speed_name = self.get_category_name("speeds", speed_id, lang)

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
        pose_url = self.get_pose_url(unit_id)
        if pose_url:
            embed.set_thumbnail(url=pose_url)

        # Logo hinzufügen
        logo_filename = 'LotusGaming.png'
        logo_path = os.path.join('data', 'media', logo_filename)
        if os.path.exists(logo_path):
            embed.set_footer(
                text='a service brought to you by Lotus Gaming', icon_url=f'attachment://{logo_filename}')
        else:
            embed.set_footer(text='a service brought to you by Lotus Gaming')

        return embed

    # Autocomplete-Funktionen
    async def cost_autocomplete(self, interaction: discord.Interaction, current: str):
        costs = sorted(set(unit["cost"] for unit in self.units))
        return [
            app_commands.Choice(name=str(c), value=str(c))
            for c in costs if current.lower() in str(c).lower()
        ]

    async def speed_autocomplete(self, interaction: discord.Interaction, current: str):
        speeds = self.languages['en']['categories']['speeds']
        return [
            app_commands.Choice(name=s['name'], value=str(s['id']))
            for s in speeds if current.lower() in s['name'].lower()
        ]

    async def faction_autocomplete(self, interaction: discord.Interaction, current: str):
        factions = self.languages['en']['categories']['factions']
        return [
            app_commands.Choice(name=f['name'], value=str(f['id']))
            for f in factions if current.lower() in f['name'].lower()
        ]

    async def type_autocomplete(self, interaction: discord.Interaction, current: str):
        types = self.languages['en']['categories']['types']
        return [
            app_commands.Choice(name=t['name'], value=str(t['id']))
            for t in types if current.lower() in t['name'].lower()
        ]

    async def trait_autocomplete(self, interaction: discord.Interaction, current: str):
        traits = self.languages['en']['categories']['traits']
        return [
            app_commands.Choice(name=t['name'], value=str(t['id']))
            for t in traits if current.lower() in t['name'].lower()
        ]

    @app_commands.command(name="filter", description="Filtert Minis basierend auf verschiedenen Kriterien.")
    @app_commands.guilds(discord.Object(id=MAIN_SERVER_ID))
    @app_commands.describe(
        cost="Kosten des Minis",
        speed="Geschwindigkeit des Minis",
        faction="Fraktion des Minis",
        type="Typ des Minis",
        trait="Merkmal des Minis",
        lang="Sprache"
    )
    @app_commands.autocomplete(
        cost=cost_autocomplete,
        speed=speed_autocomplete,
        faction=faction_autocomplete,
        type=type_autocomplete,
        trait=trait_autocomplete
    )
    async def filter(self, interaction: discord.Interaction, cost: str = None, speed: str = None,
                     faction: str = None, type: str = None, trait: str = None, lang: str = "de"):
        print(f"Befehl /filter ausgeführt mit Parametern: cost={cost}, speed={
              speed}, faction={faction}, type={type}, trait={trait}, lang={lang}")

        if lang not in self.languages:
            await interaction.response.send_message("Sprache nicht unterstützt. Verfügbar: " + ", ".join(self.languages.keys()))
            return

        texts = self.languages[lang]

        # Starte mit allen Einheiten
        filtered_units = self.units

        # Wende Filter an, wenn Parameter angegeben sind
        if cost is not None:
            filtered_units = [
                u for u in filtered_units if str(u.get("cost")) == cost]

        if speed is not None:
            filtered_units = [u for u in filtered_units if str(
                u.get("speed_id")) == speed]

        if faction is not None:
            filtered_units = [u for u in filtered_units if str(
                u.get("faction_id")) == faction]

        if type is not None:
            filtered_units = [u for u in filtered_units if str(
                u.get("type_id")) == type]

        if trait is not None:
            filtered_units = [u for u in filtered_units if int(
                trait) in u.get("traits_ids", [])]

        if not filtered_units:
            await interaction.response.send_message("Keine Minis gefunden, die den angegebenen Kriterien entsprechen.")
            return

        # Begrenze die Anzahl der Ergebnisse
        if len(filtered_units) > 25:
            await interaction.response.send_message("Zu viele Ergebnisse. Bitte verfeinere deine Filter.")
            return

        # Erstelle die Optionen für das Dropdown-Menü
        options = []
        for unit in filtered_units:
            unit_id = unit["id"]
            unit_text = next(
                (u for u in texts["units"] if u["id"] == unit_id), {})
            unit_name = unit_text.get("name", "Unbekannt")

            # Fraktions-Emoji abrufen
            faction_emoji = self.emojis.get(
                self.get_faction_icon(unit["faction_id"]), {}).get("syntax", "")

            options.append(discord.SelectOption(label=unit_name,
                           value=str(unit_id), emoji=faction_emoji))

        # Erstelle das Dropdown-Menü
        view = MiniSelectView(options, self, lang)

        await interaction.response.send_message("Gefundene Minis:", view=view)

    async def send_mini_embed(self, interaction, unit_id, lang):
        embed = self.create_mini_embed(unit_id, lang)
        if embed is None:
            await interaction.followup.send(f"Details für Mini mit ID '{unit_id}' nicht gefunden.")
        else:
            await interaction.followup.send(embed=embed)


class MiniSelectView(discord.ui.View):
    def __init__(self, options, cog, lang):
        super().__init__(timeout=60)
        self.add_item(MiniSelect(options))
        self.cog = cog
        self.lang = lang


class MiniSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Wähle ein Mini aus", options=options, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        unit_id = int(self.values[0])
        await interaction.response.defer()
        await self.view.cog.send_mini_embed(interaction, unit_id, self.view.lang)


async def setup(bot):
    await bot.add_cog(WCRCog(bot))
