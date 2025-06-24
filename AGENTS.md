# AGENTS.md

## Slash Commands
- Use guild-based slash commands with `bot.tree.add_command(..., guild=bot.main_guild)` + sync().
- Remove global slash commands.

## Hosting & Environment
- Hosted on Railway; env vars via CLI.
- Persisted data in `data/pers/` (ignored).
