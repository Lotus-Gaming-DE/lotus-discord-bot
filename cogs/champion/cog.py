import discord
from discord.ext import commands
import os
import json
from datetime import datetime


class ChampionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        os.makedirs("data/champion", exist_ok=True)
        self.points_file = "data/champion/points.json"
        self.points = self.load_points()

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
        user_id = str(user_id)

        if user_id not in self.points:
            self.points[user_id] = {
                "total": 0,
                "history": []
            }

        self.points[user_id]["total"] += delta
        self.points[user_id]["history"].append({
            "delta": delta,
            "reason": reason,
            "date": now
        })

        self.save_points()
        return self.points[user_id]["total"]
