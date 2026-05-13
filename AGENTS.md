# AGENTS.md

Guidelines for AI agents (Claude, Codex, etc.) working on this project.

## Project Overview

Discord bot for the WoW Classic Hardcore guild "Black Lotus" on EU server Soulseeker.
Written entirely by AI agents — no human writes code directly.
Hosted on Railway. Python 3.13, discord.py 2.x.

## Repository Layout

```
src/lotus_bot/          Main bot package
  bot.py                Entry point, loads cogs
  cogs/
    wow/                WoW Classic cog — roster sync, daily digest, champion points
    quiz/               Quiz system — WoW + WCR questions, duels, scheduler
    champion/           Points leaderboard
    wcr/                Warcraft Rumble cog
    ptcgp/              Pokémon TCG Pocket cog
data/
  wow/classic_hc/       Static WoW data (items.json, instance_drops.json, …)
  quiz/templates/       Question templates (wow.json, wcr.json)
tests/                  pytest test suite — mirrors src/ structure
scripts/                One-off utility scripts (WoW data import, etc.)
```

## Code Conventions

- Python 3.13, async/await throughout
- All slash commands are guild-scoped: `bot.tree.add_command(..., guild=bot.main_guild)` + sync
- Persistent data goes in `data/pers/` (gitignored)
- Logs go in `logs/` (gitignored)
- No global slash commands

## Tooling

- Formatter: **black 26.3.1** — run `python -m black src/` after every change
- Linter: **ruff** — configured in `pyproject.toml`
- Tests: `pytest` — run from project root
- Pre-commit: all hooks defined in `.pre-commit-config.yaml`

## Environment Variables

See `.env.example` for the full list. Key vars:
- `DISCORD_TOKEN` — bot token
- `server_id` — Discord guild ID
- `BLIZZARD_CLIENT_ID` / `BLIZZARD_CLIENT_SECRET` — Battle.net API
- `RAILWAY_TOKEN` — Railway deployment

## Hosting

- Deployed on Railway (production)
- Env vars managed via Railway dashboard or CLI
- Logs accessible via `railway logs` or GitHub Actions artifacts

## WoW Cog Notes

- Classic Era 1x namespace: `profile-classic1x-eu`
- The `/professions` and `/reputations` Blizzard API endpoints return 404 for Classic Era 1x
- Item levels are resolved via a local lookup (data/wow/classic_hc/items.json) — the equipment API does not return iLvl
- Daily digest posts at 09:00 Europe/Berlin time
