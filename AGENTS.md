# Developer Guidelines

- Use **guild-based** slash commands only. Register command groups with `bot.tree.add_command(..., guild=bot.main_guild)` and sync via `await bot.tree.sync(guild=bot.main_guild)`.
- The bot operates on a **German-only** Discord server. All user-facing strings
  and documentation should default to **German**. Support for other languages is
  optional and requires explicit maintainer approval.
- Do not register global commands. Remove obsolete global commands with
  `self.tree.clear_commands(guild=None)` if needed.
- The bot is hosted on **Railway**. Environment variables like `bot_key` and `server_id` are provided there.
- Unit tests run locally without these variables. Use `monkeypatch.setenv` to simulate them, as shown in `tests/conftest.py`.
- A fixture `patch_logged_task` is provided for tests to replace `create_logged_task` with a dummy. Use it instead of duplicating patch code.
- Implement `cog_unload()` in every cog that starts background tasks or loops. Track created tasks and cancel them in this method.
- Tests must call `cog.cog_unload()` (or otherwise close the bot) to ensure no tasks keep the event loop alive.
- The CI workflow runs `flake8` for linting. Ensure your code passes the linter before committing.
- Run `flake8` and `pytest` locally before committing to catch issues early.
- When features change or new ones are added, update tests as needed and keep the `README.md` in sync.
- If new environment variables are introduced, update `.env.example` and document them.
- Persisted data lives in `data/pers/` and should not be committed.
