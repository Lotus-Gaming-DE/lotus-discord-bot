import discord
from discord.ext import commands, tasks
import random
import json
import asyncio


class QuizCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.SCORES_FILE = './data/scores.json'
        self.QUESTIONS_FILE = './data/questions.json'
        self.user_scores = self.load_scores()
        self.questions_by_area = self.load_questions()
        self.areas_config = {
            'warcraft_rumble': {
                'channel_id': 1290804058281607189,  # Ersetze mit deiner Kanal-ID
                'interval_hours': 0.1,
            },
            'diablo_iv': {
                'channel_id': 1290804058281607189,  # Ersetze mit deiner Kanal-ID
                'interval_hours': 0.1,
            },
            # Weitere Bereiche hinzufügen
        }
        # Starte die Tasks für alle Bereiche
        for area in self.areas_config:
            self.start_quiz_task(area)

    def load_scores(self):
        try:
            with open(self.SCORES_FILE, 'r') as f:
                user_scores = json.load(f)
                user_scores = {int(k): v for k, v in user_scores.items()}
        except FileNotFoundError:
            user_scores = {}
        return user_scores

    def save_scores(self):
        with open(self.SCORES_FILE, 'w') as f:
            json.dump(self.user_scores, f)

    def load_questions(self):
        try:
            with open(self.QUESTIONS_FILE, 'r', encoding='utf-8') as f:
                questions_by_area = json.load(f)
        except FileNotFoundError:
            print(f"Die Datei {self.QUESTIONS_FILE} wurde nicht gefunden.")
            questions_by_area = {}
        return questions_by_area

    def start_quiz_task(self, area):
        config = self.areas_config[area]
        interval = config['interval_hours']

        @tasks.loop(hours=interval)
        async def quiz_loop():
            await self.run_quiz(area)

        @quiz_loop.before_loop
        async def before_quiz():
            await self.bot.wait_until_ready()

        quiz_loop.start()

    async def run_quiz(self, area):
        config = self.areas_config[area]
        channel = self.bot.get_channel(config['channel_id'])
        if channel is None:
            print(f"Konnte Kanal mit ID {config['channel_id']} nicht finden.")
            return

        questions = self.questions_by_area.get(area)
        if not questions:
            print(f"Keine Fragen für den Bereich '{area}' gefunden.")
            return

        frage = random.choice(questions)
        question_message = await channel.send(frage['frage'])

        def check(m):
            return (
                m.channel == channel and
                m.author != self.bot.user and
                m.reference and
                m.reference.message_id == question_message.id
            )

        while True:
            try:
                antwort = await self.bot.wait_for('message', timeout=60.0, check=check)
                if antwort.content.strip().lower() == frage['antwort'].strip().lower():
                    await channel.send(f'Richtig, {antwort.author.mention}!')
                    user_id = antwort.author.id
                    self.user_scores[user_id] = self.user_scores.get(
                        user_id, 0) + 1
                    self.save_scores()
                    break
                else:
                    await channel.send(f'Leider falsch, {antwort.author.mention}. Versuche es erneut!')
            except asyncio.TimeoutError:
                await channel.send('Zeit abgelaufen! Keine korrekte Antwort wurde gegeben.')
                break

    @commands.command()
    async def punkte(self, ctx):
        user_id = ctx.author.id
        score = self.user_scores.get(user_id, 0)
        await ctx.send(f'Du hast insgesamt {score} Punkt(e), {ctx.author.name}.')

    @commands.command()
    async def rangliste(self, ctx):
        sorted_scores = sorted(self.user_scores.items(),
                               key=lambda x: x[1], reverse=True)
        message = '🏆 **Rangliste:**\n'
        for user_id, score in sorted_scores[:10]:
            user = await self.bot.fetch_user(user_id)
            message += f'{user.name}: {score} Punkt(e)\n'
        await ctx.send(message)


async def setup(bot):
    await bot.add_cog(QuizCog(bot))
