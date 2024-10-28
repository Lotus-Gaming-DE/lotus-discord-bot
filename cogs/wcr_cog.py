import discord
from discord import app_commands
from discord.ext import commands
import json
import requests
import os


class WCRCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.units = self.load_units()
        self.languages = self.load_languages()
        self.pictures = self.load_pictures()
        self.emojis = self.load_emojis()

    # (Hier bleiben die load_* Methoden unverändert)

    def get_text_data(self, unit_id, lang):
        texts = self.languages.get(lang, self.languages["de"])
        unit_text = texts["units"].get(str(unit_id), {})
        return unit_text.get("name", "Unbekannt"), unit_text.get("description", "Beschreibung fehlt"), unit_text.get("talents", {})

    def get_pose_url(self, unit_id):
        """Gibt die pose-URL des Minis zurück, falls vorhanden."""
        return self.pictures["units"].get(str(unit_id), {}).get("pose", "")

    @app_commands.command(name="name", description="Zeigt Details zu einem Mini basierend auf dem Namen an.")
    async def name(self, interaction: discord.Interaction, name: str, lang: str = "de"):
        print(f"Befehl /name ausgeführt mit Name: {name} und Sprache: {lang}")

        if lang not in self.languages:
            await interaction.response.send_message("Sprache nicht unterstützt. Verfügbar: de, en.")
            return

        # Suche nach dem Namen in der Sprachdatei
        matching_unit = None
        for unit_id, unit_data in self.languages[lang]["units"].items():
            if unit_data["name"].lower() == name.lower():
                matching_unit = next(
                    (u for u in self.units if str(u["id"]) == unit_id), None)
                break

        if not matching_unit:
            await interaction.response.send_message(f"Mini mit Namen '{name}' nicht gefunden.")
            return

        unit_name, unit_description, talents = self.get_text_data(
            matching_unit["id"], lang)
        stats = matching_unit["stats"]

        # Erstelle dynamisch die Felder für vorhandene Statistiken
        fields = [
            (f"{self.emojis.get('wcr_cost', {}).get('syntax', '')
                } Kosten", str(matching_unit.get("cost", "N/A"))),
            (f"{self.emojis.get('wcr_speed', {}).get('syntax', '')
                } Geschwindigkeit", str(matching_unit.get("speed_id", "N/A"))),
        ]

        # Füge nur Statistiken hinzu, die tatsächlich einen Wert haben
        if stats.get("health"):
            fields.append((f"{self.emojis.get('wcr_health', {}).get(
                'syntax', '')} Gesundheit", str(stats["health"])))
        if stats.get("damage"):
            fields.append((f"{self.emojis.get('wcr_damage', {}).get(
                'syntax', '')} Schaden", str(stats["damage"])))
        if stats.get("dps"):
            fields.append(
                (f"{self.emojis.get('wcr_dps', {}).get('syntax', '')} DPS", str(stats["dps"])))
        if stats.get("attack_speed"):
            fields.append((f"{self.emojis.get('wcr_attack_speed', {}).get(
                'syntax', '')} Angriffsgeschwindigkeit", str(stats["attack_speed"])))
        if stats.get("range"):
            fields.append((f"{self.emojis.get('wcr_range', {}).get(
                'syntax', '')} Reichweite", str(stats["range"])))
        if stats.get("duration"):
            fields.append((f"{self.emojis.get('wcr_duration', {}).get(
                'syntax', '')} Dauer", str(stats["duration"])))

        # Inline-Felder für Talente vorbereiten und Bilder als Anhang hinzufügen
        files = []
        inline_fields = []
        for i, (talent_id, talent_data) in enumerate(talents.items()):
            if i >= 3:
                break  # Begrenzt auf maximal 3 Talente
            talent_name = talent_data.get("name", "Unbekanntes Talent")
            talent_description = talent_data.get(
                "description", "Beschreibung fehlt")
            talent_image_url = self.pictures["units"].get(
                str(matching_unit["id"]), {}).get(f"talent_{talent_id}", "")

            if talent_image_url:
                # Lade das Bild herunter und speichere es temporär
                image_data = requests.get(talent_image_url).content
                filename = f"temp_talent_image_{i}.png"
                with open(filename, "wb") as f:
                    f.write(image_data)
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

        if self.get_pose_url(matching_unit["id"]):
            embed.set_thumbnail(url=self.get_pose_url(matching_unit["id"]))

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
