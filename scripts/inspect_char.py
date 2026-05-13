"""One-off diagnostic: ask the Blizzard API about specific Classic Era 1x chars.

Usage (with prod env via Railway):
    railway run --service lotus-discord-bot -- python scripts/inspect_char.py Voidok
    railway run --service lotus-discord-bot -- python scripts/inspect_char.py Voidok --full

`--full` dumps every endpoint we can reach for the character. Default dumps
only the summary fields the bot actually uses.
"""

from __future__ import annotations

import asyncio
import json
import sys

from lotus_bot.cogs.wow.api import (
    fetch_character_equipment,
    fetch_character_profile,
    WoWAPIError,
)

REALM = "soulseeker"


def _strip_links(value):
    """Recursively drop noisy `_links` and `key` fields from a payload."""
    if isinstance(value, dict):
        return {
            k: _strip_links(v)
            for k, v in value.items()
            if k not in {"_links", "key", "media"}
        }
    if isinstance(value, list):
        return [_strip_links(item) for item in value]
    return value


async def safe_fetch(label, coro):
    try:
        result = await coro
        return result
    except WoWAPIError as exc:
        return f"<WoWAPIError status={exc.status}: {exc}>"
    except Exception as exc:
        return f"<{type(exc).__name__}: {exc}>"


async def main(name: str, full: bool) -> None:
    print(f"\n========== /profile/wow/character/{REALM}/{name.lower()} ==========")
    profile = await safe_fetch("profile", fetch_character_profile(REALM, name))
    if isinstance(profile, dict):
        print(json.dumps(_strip_links(profile), ensure_ascii=False, indent=2))
    else:
        print(profile)

    if not full:
        return

    print(
        f"\n========== /profile/wow/character/{REALM}/{name.lower()}/equipment =========="
    )
    equipment = await safe_fetch("equipment", fetch_character_equipment(REALM, name))
    if isinstance(equipment, dict):
        print(json.dumps(_strip_links(equipment), ensure_ascii=False, indent=2))
    else:
        print(equipment)


if __name__ == "__main__":
    args = sys.argv[1:]
    full = "--full" in args
    args = [a for a in args if not a.startswith("--")]
    target = args[0] if args else "Voidok"
    asyncio.run(main(target, full))
