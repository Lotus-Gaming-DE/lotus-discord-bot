import discord
from discord.ext import commands
import asyncio
import os

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)


async def load_cogs():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            await bot.load_extension(f'cogs.{filename[:-3]}')


@bot.event
async def on_ready():
    print(f'Bot ist online als {bot.user}')


async def main():
    async with bot:
        await load_cogs()
        await bot.start('MTI5MDc4NTg3OTM5MjI2MDE3OA.GhJmct.m81o4hzI2Dw9lNJ2hzVPaQStp6sVD_Yzpjq4A4')

asyncio.run(main())
