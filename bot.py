# bot.py
import discord
from discord.ext import commands
import os
import json
import logging

# Setze das Logging-Level und das Format
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s:%(name)s: %(message)s')

logger = logging.getLogger('bot')

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True


class MyBot(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(command_prefix='§', intents=intents, **kwargs)
        self.main_server_id = os.getenv('server_id')

        if self.main_server_id is None:
            logger.error(
                "Die Environment-Variable 'server_id' wurde nicht gefunden.")
            exit(1)

    async def setup_hook(self):
        # Lade alle Cogs (Dateien + Unterverzeichnisse mit __init__.py)
        for filename in os.listdir('./cogs'):
            filepath = os.path.join('./cogs', filename)
            if filename.endswith('.py'):
                extension = f'cogs.{filename[:-3]}'
                try:
                    await self.load_extension(extension)
                    logger.info(f'Extension {extension} geladen.')
                except Exception as e:
                    logger.error(
                        f'Fehler beim Laden der Extension {extension}: {e}', exc_info=True)
            elif os.path.isdir(filepath) and not filename.startswith('__'):
                if '__init__.py' in os.listdir(filepath):
                    extension = f'cogs.{filename}'
                    try:
                        await self.load_extension(extension)
                        logger.info(f'Extension {extension} geladen.')
                    except Exception as e:
                        logger.error(
                            f'Fehler beim Laden der Extension {extension}: {e}', exc_info=True)
                else:
                    logger.warning(
                        f'Verzeichnis {filepath} enthält keine __init__.py und wird ignoriert.')
            else:
                logger.warning(f'Ignoriere {filepath}')

        # Emojis laden und Slash-Befehle aktualisieren
        await self.load_emojis_and_sync_commands()

    async def load_emojis_and_sync_commands(self):
        try:
            guild_id = int(self.main_server_id)
            guild = self.get_guild(guild_id) or await self.fetch_guild(guild_id)

            # Emojis laden
            if guild:
                emojis_data = {}
                for emoji in guild.emojis:
                    emojis_data[emoji.name] = {
                        "id": emoji.id,
                        "animated": emoji.animated,
                        "syntax": f"{'<a:' if emoji.animated else '<:'}{emoji.name}:{emoji.id}>"
                    }

                os.makedirs("data", exist_ok=True)
                with open("data/emojis.json", "w", encoding="utf-8") as f:
                    json.dump(emojis_data, f, indent=4, ensure_ascii=False)

                logger.info("✅ Emojis gespeichert in 'data/emojis.json'.")
            else:
                logger.warning(
                    f"⚠️ Hauptserver mit ID {self.main_server_id} nicht gefunden.")

            # 🔴 Globale Slash-Befehle löschen
            self.tree.clear_commands(guild=None)
            await self.tree.sync(guild=None)
            logger.info("🌐 Globale Slash-Befehle gelöscht.")

            # 🧹 Guild-spezifische Slash-Befehle löschen
            guild_obj = discord.Object(id=guild_id)
            self.tree.clear_commands(guild=guild_obj)
            logger.info(f"🧹 Slash-Befehle für Guild {guild_id} gelöscht.")

            # 🔁 Danach neu synchronisieren
            await self.tree.sync(guild=guild_obj)
            logger.info(
                f"🔁 Slash-Befehle für Server {guild_id} neu registriert.")

        except Exception as e:
            logger.error(
                f"❌ Fehler beim Laden der Emojis/Synchronisieren der Befehle:\n{e}", exc_info=True)

    async def on_ready(self):
        logger.info(f'✅ Bot ist online als {self.user}.')

    async def on_message(self, message):
        if message.author.bot:
            return
        await self.process_commands(message)


if __name__ == '__main__':
    bot_token = os.getenv('bot_key')
    if bot_token is None:
        logger.error(
            "❌ Bot Token nicht gefunden – Environment-Variable 'bot_key' fehlt.")
    else:
        bot = MyBot()
        bot.run(bot_token)
