import asyncio
import os
import random
import time
from contextlib import asynccontextmanager
from typing import Any

import aiohttp

from lotus_bot.log_setup import get_logger

logger = get_logger(__name__)

TOKEN_URL = "https://oauth.battle.net/token"
API_BASE = "https://eu.api.blizzard.com"
DEFAULT_NAMESPACE = "profile-classic1x-eu"
DEFAULT_LOCALE = "de_DE"

# Refresh the cached OAuth token this many seconds before its declared expiry.
TOKEN_REFRESH_BUFFER_SECONDS = 5 * 60
# Retry policy for transient (5xx / network) failures.
RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 0.5  # exponential backoff: 0.5s, 1.5s, 4.5s


class WoWAPIError(RuntimeError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class _TokenCache:
    """Process-wide Battle.net OAuth token cache.

    Battle.net tokens are valid for ~24h. Re-fetching on every API call wastes
    a TLS handshake plus an OAuth round-trip per request — a single scan would
    otherwise hit the token endpoint 100+ times.
    """

    def __init__(self) -> None:
        self.token: str | None = None
        self.expires_at: float = 0.0
        self.lock = asyncio.Lock()


_token_cache = _TokenCache()


def reset_token_cache() -> None:
    """Drop the cached token. Intended for tests."""
    _token_cache.token = None
    _token_cache.expires_at = 0.0


async def fetch_access_token(
    session: aiohttp.ClientSession | None = None,
) -> str:
    """Fetch (or reuse) a Battle.net client credentials token."""
    now = time.monotonic()
    if (
        _token_cache.token
        and _token_cache.expires_at - TOKEN_REFRESH_BUFFER_SECONDS > now
    ):
        return _token_cache.token

    async with _token_cache.lock:
        now = time.monotonic()
        if (
            _token_cache.token
            and _token_cache.expires_at - TOKEN_REFRESH_BUFFER_SECONDS > now
        ):
            return _token_cache.token

        client_id = os.getenv("BLIZZARD_CLIENT_ID")
        client_secret = os.getenv("BLIZZARD_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise RuntimeError("Battle.net API credentials are not configured.")

        auth = aiohttp.BasicAuth(client_id, client_secret)
        async with _session_or_owned(session) as sess:
            async with sess.post(
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
            raise RuntimeError(
                "Battle.net token response did not include access_token."
            )
        expires_in = int(data.get("expires_in") or 0) or 3600
        _token_cache.token = str(token)
        _token_cache.expires_at = time.monotonic() + expires_in
        return _token_cache.token


@asynccontextmanager
async def wow_api_session():
    """Context manager yielding a single shared aiohttp session.

    Use this in `scan()` so all Blizzard calls within one scan share TCP/TLS
    pooling and a single token fetch.
    """
    async with aiohttp.ClientSession() as session:
        yield session


@asynccontextmanager
async def _session_or_owned(session: aiohttp.ClientSession | None):
    if session is not None:
        yield session
        return
    async with aiohttp.ClientSession() as owned:
        yield owned


async def _get_json_with_retry(
    session: aiohttp.ClientSession,
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, str],
    not_found_returns_none: bool = False,
    error_label: str,
) -> dict[str, Any] | None:
    """GET ``url`` with exponential backoff on 5xx / connection errors.

    4xx responses are not retried — they indicate the caller's problem
    (auth, 404, bad params) and retrying won't change the answer.
    """
    last_exc: Exception | None = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            async with session.get(url, headers=headers, params=params) as resp:
                if 200 <= resp.status < 300:
                    data = await resp.json()
                    return data if isinstance(data, dict) else {}
                if resp.status == 404 and not_found_returns_none:
                    return None
                if resp.status >= 500:
                    text = await resp.text()
                    last_exc = WoWAPIError(
                        f"{error_label}: HTTP {resp.status} {text}",
                        status=resp.status,
                    )
                else:
                    text = await resp.text()
                    raise WoWAPIError(
                        f"{error_label}: HTTP {resp.status} {text}",
                        status=resp.status,
                    )
        except aiohttp.ClientError as exc:
            last_exc = exc

        if attempt + 1 < RETRY_ATTEMPTS:
            delay = RETRY_BASE_DELAY * (3**attempt) + random.uniform(0, 0.25)
            logger.info(
                "[WoW API] Transient failure (%s); retry %d/%d in %.2fs",
                last_exc,
                attempt + 1,
                RETRY_ATTEMPTS - 1,
                delay,
            )
            await asyncio.sleep(delay)

    if isinstance(last_exc, WoWAPIError):
        raise last_exc
    raise WoWAPIError(f"{error_label}: {last_exc}", status=None)


async def fetch_guild_roster(
    realm_slug: str,
    guild_slug: str,
    *,
    namespace: str = DEFAULT_NAMESPACE,
    locale: str = DEFAULT_LOCALE,
    session: aiohttp.ClientSession | None = None,
) -> list[dict[str, Any]]:
    """Fetch a WoW Classic guild roster from the Battle.net API."""
    async with _session_or_owned(session) as sess:
        token = await fetch_access_token(sess)
        url = f"{API_BASE}/data/wow/guild/{realm_slug}/{guild_slug}/roster"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"namespace": namespace, "locale": locale}
        data = await _get_json_with_retry(
            sess,
            url,
            headers=headers,
            params=params,
            error_label="Guild roster request failed",
        )

    members = (data or {}).get("members", [])
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
    session: aiohttp.ClientSession | None = None,
) -> dict[str, Any]:
    """Fetch a WoW Classic character profile.

    Classic profile endpoints can be flaky. Callers should treat failures as an
    unknown state instead of blocking roster processing.
    """
    async with _session_or_owned(session) as sess:
        token = await fetch_access_token(sess)
        url = f"{API_BASE}/profile/wow/character/{realm_slug}/{character_name.lower()}"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"namespace": namespace, "locale": locale}
        data = await _get_json_with_retry(
            sess,
            url,
            headers=headers,
            params=params,
            error_label="Character profile request failed",
        )
    return data or {}


async def fetch_character_equipment(
    realm_slug: str,
    character_name: str,
    *,
    namespace: str = DEFAULT_NAMESPACE,
    locale: str = DEFAULT_LOCALE,
    session: aiohttp.ClientSession | None = None,
) -> dict[str, Any]:
    """Fetch a character's equipped items.

    Classic profile detail endpoints are not guaranteed to be available. Callers
    should treat failures as missing gear data.
    """
    async with _session_or_owned(session) as sess:
        token = await fetch_access_token(sess)
        url = (
            f"{API_BASE}/profile/wow/character/"
            f"{realm_slug}/{character_name.lower()}/equipment"
        )
        headers = {"Authorization": f"Bearer {token}"}
        params = {"namespace": namespace, "locale": locale}
        data = await _get_json_with_retry(
            sess,
            url,
            headers=headers,
            params=params,
            error_label="Character equipment request failed",
        )
    return data or {}
