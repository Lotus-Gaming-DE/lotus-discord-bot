import os
from typing import Any

import aiohttp

from lotus_bot.log_setup import get_logger

logger = get_logger(__name__)

TOKEN_URL = "https://oauth.battle.net/token"
API_BASE = "https://eu.api.blizzard.com"
DEFAULT_NAMESPACE = "profile-classic1x-eu"
DEFAULT_LOCALE = "de_DE"


class WoWAPIError(RuntimeError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


async def fetch_access_token() -> str:
    """Fetch a Battle.net client credentials token."""
    client_id = os.getenv("BLIZZARD_CLIENT_ID")
    client_secret = os.getenv("BLIZZARD_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("Battle.net API credentials are not configured.")

    auth = aiohttp.BasicAuth(client_id, client_secret)
    async with aiohttp.ClientSession() as session:
        async with session.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=auth,
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(
                    f"Battle.net token request failed: HTTP {resp.status} {text}"
                )
            data = await resp.json()

    token = data.get("access_token")
    if not token:
        raise RuntimeError("Battle.net token response did not include access_token.")
    return str(token)


async def fetch_guild_roster(
    realm_slug: str,
    guild_slug: str,
    *,
    namespace: str = DEFAULT_NAMESPACE,
    locale: str = DEFAULT_LOCALE,
) -> list[dict[str, Any]]:
    """Fetch a WoW Classic guild roster from the Battle.net API."""
    token = await fetch_access_token()
    url = f"{API_BASE}/data/wow/guild/{realm_slug}/{guild_slug}/roster"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"namespace": namespace, "locale": locale}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(
                    f"Guild roster request failed: HTTP {resp.status} {text}"
                )
            data = await resp.json()

    members = data.get("members", [])
    if not isinstance(members, list):
        logger.warning("[WoW API] Guild roster response did not contain a member list.")
        return []
    return members


async def fetch_character_profile(
    realm_slug: str,
    character_name: str,
    *,
    namespace: str = DEFAULT_NAMESPACE,
    locale: str = DEFAULT_LOCALE,
) -> dict[str, Any]:
    """Fetch a WoW Classic character profile.

    Classic profile endpoints can be flaky. Callers should treat failures as an
    unknown state instead of blocking roster processing.
    """
    token = await fetch_access_token()
    url = f"{API_BASE}/profile/wow/character/{realm_slug}/{character_name.lower()}"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"namespace": namespace, "locale": locale}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise WoWAPIError(
                    f"Character profile request failed: HTTP {resp.status} {text}",
                    status=resp.status,
                )
            data = await resp.json()

    return data if isinstance(data, dict) else {}


async def fetch_character_reputations(
    realm_slug: str,
    character_name: str,
    *,
    namespace: str = DEFAULT_NAMESPACE,
    locale: str = DEFAULT_LOCALE,
) -> dict[str, Any]:
    """Fetch a character's reputation summary.

    This endpoint is not guaranteed to exist for Classic Era namespaces. Callers
    must treat failures as a disabled/unknown reputation state.
    """
    token = await fetch_access_token()
    url = (
        f"{API_BASE}/profile/wow/character/"
        f"{realm_slug}/{character_name.lower()}/reputations"
    )
    headers = {"Authorization": f"Bearer {token}"}
    params = {"namespace": namespace, "locale": locale}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise WoWAPIError(
                    f"Character reputations request failed: HTTP {resp.status} {text}",
                    status=resp.status,
                )
            data = await resp.json()

    return data if isinstance(data, dict) else {}
