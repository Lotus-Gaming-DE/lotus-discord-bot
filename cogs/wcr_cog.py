import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import urllib.request  # Verwenden Sie urllib.request statt requests


class WCRCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.units = self.load_units()
        self.languages = self.load_languages()
        self.pictures = self.load_pictures()
        self.emojis = self.load_emojis()

    def load_units(self):
        # Bestimmen Sie den Pfad zu 'units.json'
        current_dir = os.path.dirname(os.path.abspath(__file__))
        units_path = os.path.join(
            current_dir, '..', 'data', 'wcr', 'units.json')
        units_path = os.path.normpath(units_path)

        with open(units_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Die Einheitenliste unter dem Schlüssel 'units' zurückgeben
        return data['units']

    def load_languages(self):
        languages = {}
        # Bestimmen Sie den Pfad zum 'locals'-Verzeichnis
        current_dir = os.path.dirname(os.path.abspath(__file__))
        locals_dir = os.path.join(current_dir, '..', 'data', 'wcr', 'locals')
        locals_dir = os.path.normpath(locals_dir)

        for lang_file in os.listdir(locals_dir):
            if lang_file.endswith('.json'):
                lang_code = lang_file.split('.')[0]
                with open(os.path.join(locals_dir, lang_file), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                languages[lang_code] = data
        return languages

    def load_pictures(self):
        # Bestimmen Sie den Pfad zu 'pictures.json'
        current_dir = os.path.dirname(os.path.abspath(__file__))
        pictures_path = os.path.join(
            current_dir, '..', 'data', 'wcr', 'pictures.json')
        pictures_path = os.path.normpath(pictures_path)

        with open(pictures_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data

    def load_emojis(self):
        # Bestimmen Sie den Pfad zu 'emojis.json'
        current_dir = os.path.dirname(os.path.abspath(__file__))
        emojis_path = os.path.join(
            current_dir, '..', 'data', 'wcr', 'emojis.json')
        emojis_path = os.path.normpath(emojis_path)

        with open(emojis_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data

    def get_text_data(self, unit_id, lang):
        texts = self.languages.get(lang, self.languages["de"])
        # Suche die Einheit in der Sprachdatei anhand der ID
        unit_text = next(
            (unit for unit in texts["units"] if unit["id"] == unit_id), {})
        return unit_text.get("name", "Unbekannt"), unit_text.get("description", "Beschreibung fehlt"), unit_text.get("talents", [])

    def get_pose_url(self, unit_id):
        """Gibt die pose-URL des Minis zurück, falls vorhanden."""
        unit_pictures = self.pictures.get("units", [])
        unit_picture = next(
            (pic for pic in unit_pictures if pic["id"] == unit_id), {})
        return unit_picture.get("pose", "")

    @app_commands.command(name="name", description="Zeigt Details zu einem Mini basierend auf dem Namen an.")
    async def name(self, interaction: discord.Interaction, name: str, lang: str = "de"):
        print(f"Befehl /name ausgeführt mit Name: {name} und Sprache: {lang}")

        if lang not in self.languages:
            await interaction.response.send_message("Sprache nicht unterstützt. Verfügbar: " + ", ".join(self.languages.keys()))
            return

        # Suche nach dem Namen in der Sprachdatei
        texts = self.languages[lang]
        matching_unit_text = next(
            (unit for unit in texts["units"] if unit["name"].lower() == name.lower()), None)

        if not matching_unit_text:
            await interaction.response.send_message(f"Mini mit Namen '{name}' nicht gefunden.")
            return

        # Finde die Einheit in der units-Liste anhand der ID
        unit_id = matching_unit_text["id"]
        matching_unit = next(
            (unit for unit in self.units if unit["id"] == unit_id), None)

        if not matching_unit:
            await interaction.response.send_message(f"Details für Mini mit ID '{unit_id}' nicht gefunden.")
            return

        unit_name, unit_description, talents = self.get_text_data(
            unit_id, lang)
        stats = matching_unit.get("stats", {})

        # Erstelle dynamisch die Felder für vorhandene Statistiken
        fields = [
            (f"{self.emojis.get('wcr_cost', {}).get('syntax', '')} Kosten",
             str(matching_unit.get("cost", "N/A"))),
            (f"{self.emojis.get('wcr_speed', {}).get('syntax', '')} Geschwindigkeit",
             str(matching_unit.get("speed_id", "N/A"))),
        ]

        # Füge nur Statistiken hinzu, die tatsächlich einen Wert haben
        for stat_key, emoji_name in [("health", "wcr_health"), ("damage", "wcr_damage"), ("dps", "wcr_dps"),
                                     ("attack_speed", "wcr_attack_speed"), ("range", "wcr_range"), ("duration", "wcr_duration")]:
            if stats.get(stat_key):
                fields.append(
                    (f"{self.emojis.get(emoji_name, {}).get('syntax', '')} {stat_key.capitalize()}", str(stats[stat_key])))

        # Inline-Felder für Talente vorbereiten und Bilder als Anhang hinzufügen
        files = []
        inline_fields = []
        for i, talent in enumerate(talents):
            if i >= 3:
                break  # Begrenzt auf maximal 3 Talente
            talent_name = talent.get("name", "Unbekanntes Talent")
            talent_description = talent.get(
                "description", "Beschreibung fehlt")
            # Suche nach dem Talentbild
            unit_pictures = self.pictures.get("units", [])
            unit_picture = next(
                (pic for pic in unit_pictures if pic["id"] == unit_id), {})
            talent_image_url = unit_picture.get(f"talent_{i+1}", "")

            if talent_image_url:
                # Lade das Bild herunter und speichere es temporär
                filename = f"temp_talent_image_{i}.png"
                urllib.request.urlretrieve(talent_image_url, filename)
                files.append(discord.File(filename, filename=filename))
                inline_fields.append(
                    (f"{talent_name}", f"{talent_description}\n[Bild]({filename})"))
            else:
                inline_fields.append((talent_name, talent_description))

        # Erstelle das Embed und sende es
        embed = discord.Embed(
            title=unit_name,
            description=unit_description,
            color=0x3498db
        )

        pose_url = self.get_pose_url(unit_id)
        if pose_url:
            embed.set_thumbnail(url=pose_url)

        for name, value in fields:
            embed.add_field(name=name, value=value, inline=False)
        for name, value in inline_fields:
            embed.add_field(name=name, value=value, inline=True)

        await interaction.response.send_message(embed=embed, files=files)

        # Entferne die temporären Dateien nach dem Senden
        for file in files:
            os.remove(file.filename)


async def setup(bot):
    await bot.add_cog(WCRCog(bot))
