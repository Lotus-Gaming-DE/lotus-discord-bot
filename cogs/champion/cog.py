import discord
from discord.ext import commands
import os
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)  # z. B. 'cogs.champion.cog'


class ChampionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        os.makedirs("data/champion", exist_ok=True)
        self.points_file = "data/champion/points.json"
        self.points = self.load_points()

        # Absteigend sortiert
        self.roles = [
            ("Ultimate Champion", 750),
            ("Epic Champion", 500),
            ("Renowned Champion", 300),
            ("Seasoned Champion", 150),
            ("Emerging Champion", 50)
        ]

    def load_points(self):
        if not os.path.exists(self.points_file):
            with open(self.points_file, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=4)
            return {}
        with open(self.points_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_points(self):
        with open(self.points_file, "w", encoding="utf-8") as f:
            json.dump(self.points, f, indent=4, ensure_ascii=False)

    def get_current_role(self, score):
        for role_name, threshold in self.roles:
            if score >= threshold:
                return role_name
        return None

    def update_user_score(self, user_id, delta, reason):
        now = datetime.utcnow().isoformat()
        user_id_str = str(user_id)

        if user_id_str not in self.points:
            self.points[user_id_str] = {
                "total": 0,
                "history": []
            }

        self.points[user_id_str]["total"] += delta
        self.points[user_id_str]["history"].append({
            "delta": delta,
            "reason": reason,
            "date": now
        })

        self.save_points()

        # Neue Gesamtpunktzahl
        new_total = self.points[user_id_str]["total"]

        # Rolle aktualisieren (asynchron)
        self.bot.loop.create_task(
            self._apply_champion_role(user_id, new_total)
        )

        return new_total

    async def _apply_champion_role(self, user_id, score):
        guild = discord.utils.get(
            self.bot.guilds, id=int(os.getenv("server_id")))
        if not guild:
            logger.warning("[ChampionCog] Guild nicht gefunden.")
            return

        member = guild.get_member(int(user_id))
        if not member:
            logger.info(
                f"[ChampionCog] Member {user_id} nicht auf dem Server.")
            return

        target_role_name = self.get_current_role(score)
        if not target_role_name:
            logger.info(
                f"[ChampionCog] Keine Champion-Rolle für {member.display_name} bei {score} Punkten.")
            return

        current_roles = [r.name for r in member.roles]
        if target_role_name in current_roles:
            return  # schon korrekt

        # Alle Champion-Rollen entfernen
        roles_to_remove = [
            discord.utils.get(guild.roles, name=role_name)
            for role_name, _ in self.roles
            if role_name in current_roles
        ]
        await member.remove_roles(*filter(None, roles_to_remove))

        # Zielrolle hinzufügen
        target_role = discord.utils.get(guild.roles, name=target_role_name)
        if target_role:
            await member.add_roles(target_role)
            logger.info(
                f"[ChampionCog] Rolle '{target_role_name}' an {member.display_name} vergeben (Score: {score}).")
        else:
            logger.warning(
                f"[ChampionCog] Rolle '{target_role_name}' nicht gefunden.")
