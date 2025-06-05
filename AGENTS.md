# Developer Guidelines

- Use **guild-based** slash commands only. Register command groups with `bot.tree.add_command(..., guild=bot.main_guild)` and sync via `await bot.tree.sync(guild=bot.main_guild)`.
- Do not register global commands. Remove obsolete global commands with `self.tree.clear_commands()` if needed.
- The bot is hosted on **Railway**. Environment variables like `bot_key` and `server_id` are provided there.
- Unit tests run locally without these variables. Use `monkeypatch.setenv` to simulate them, as shown in `tests/conftest.py`.
