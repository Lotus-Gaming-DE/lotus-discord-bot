import pytest

from lotus_bot.cogs.wow import api


class FakeResponse:
    def __init__(self, status=200, payload=None, text="error"):
        self.status = status
        self.payload = payload or {}
        self._text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self):
        return self.payload

    async def text(self):
        return self._text


class FakeSession:
    """Stub for aiohttp.ClientSession.

    `get_responses` is a queue of FakeResponse objects consumed in order
    by successive .get() calls — used to simulate retry sequences.
    """

    post_response = FakeResponse(payload={"access_token": "token"})
    get_response = FakeResponse(payload={})
    get_responses: list = []
    post_calls: list = []
    get_calls: list = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def post(self, *args, **kwargs):
        FakeSession.post_calls.append((args, kwargs))
        return FakeSession.post_response

    def get(self, *args, **kwargs):
        FakeSession.get_calls.append((args, kwargs))
        if FakeSession.get_responses:
            return FakeSession.get_responses.pop(0)
        return FakeSession.get_response


@pytest.fixture(autouse=True)
def fake_session(monkeypatch):
    FakeSession.post_response = FakeResponse(payload={"access_token": "token"})
    FakeSession.get_response = FakeResponse(payload={})
    FakeSession.get_responses = []
    FakeSession.post_calls = []
    FakeSession.get_calls = []
    monkeypatch.setattr(api.aiohttp, "ClientSession", FakeSession)
    monkeypatch.setenv("BLIZZARD_CLIENT_ID", "client")
    monkeypatch.setenv("BLIZZARD_CLIENT_SECRET", "secret")
    api.reset_token_cache()
    # Skip retry sleeps so tests stay fast.
    monkeypatch.setattr(api.asyncio, "sleep", _no_sleep)


async def _no_sleep(_):
    return None


@pytest.mark.asyncio
async def test_fetch_access_token_success():
    token = await api.fetch_access_token()

    assert token == "token"
    assert FakeSession.post_calls[0][0][0] == api.TOKEN_URL


@pytest.mark.asyncio
async def test_fetch_access_token_rejects_missing_credentials(monkeypatch):
    monkeypatch.delenv("BLIZZARD_CLIENT_ID")

    with pytest.raises(RuntimeError, match="credentials"):
        await api.fetch_access_token()


@pytest.mark.asyncio
async def test_fetch_access_token_rejects_http_error_and_missing_token():
    FakeSession.post_response = FakeResponse(status=500, text="nope")
    with pytest.raises(RuntimeError, match="HTTP 500"):
        await api.fetch_access_token()

    api.reset_token_cache()
    FakeSession.post_response = FakeResponse(payload={})
    with pytest.raises(RuntimeError, match="access_token"):
        await api.fetch_access_token()


@pytest.mark.asyncio
async def test_token_cache_skips_refetch():
    FakeSession.post_response = FakeResponse(
        payload={"access_token": "token", "expires_in": 3600}
    )
    await api.fetch_access_token()
    await api.fetch_access_token()
    await api.fetch_access_token()
    # Only one OAuth round-trip even with three calls.
    assert len(FakeSession.post_calls) == 1


@pytest.mark.asyncio
async def test_fetch_guild_roster_success_and_invalid_members():
    FakeSession.get_response = FakeResponse(payload={"members": [{"character": {}}]})
    members = await api.fetch_guild_roster("soulseeker", "black-lotus")

    assert members == [{"character": {}}]
    args, kwargs = FakeSession.get_calls[0]
    assert args[0].endswith("/data/wow/guild/soulseeker/black-lotus/roster")
    assert kwargs["params"]["namespace"] == api.DEFAULT_NAMESPACE

    FakeSession.get_response = FakeResponse(payload={"members": {}})
    assert await api.fetch_guild_roster("soulseeker", "black-lotus") == []


@pytest.mark.asyncio
async def test_fetch_character_profile_success_and_error():
    FakeSession.get_response = FakeResponse(payload={"name": "Voidok"})
    assert await api.fetch_character_profile("soulseeker", "Voidok") == {
        "name": "Voidok"
    }

    FakeSession.get_response = FakeResponse(status=404, text="missing")
    with pytest.raises(api.WoWAPIError) as exc_info:
        await api.fetch_character_profile("soulseeker", "Voidok")
    assert exc_info.value.status == 404


@pytest.mark.asyncio
async def test_fetch_character_equipment_uses_equipment_endpoint():
    FakeSession.get_response = FakeResponse(payload={"equipped_items": []})

    result = await api.fetch_character_equipment("soulseeker", "Voidok")

    assert result == {"equipped_items": []}
    args, kwargs = FakeSession.get_calls[0]
    assert args[0].endswith("/profile/wow/character/soulseeker/voidok/equipment")
    assert kwargs["params"]["namespace"] == api.DEFAULT_NAMESPACE


@pytest.mark.asyncio
async def test_request_retries_on_5xx_then_succeeds():
    FakeSession.get_responses = [
        FakeResponse(status=503, text="upstream"),
        FakeResponse(status=502, text="bad gateway"),
        FakeResponse(payload={"name": "Voidok"}),
    ]
    result = await api.fetch_character_profile("soulseeker", "Voidok")
    assert result == {"name": "Voidok"}
    # 3 attempts in total.
    assert len(FakeSession.get_calls) == 3


@pytest.mark.asyncio
async def test_request_does_not_retry_on_4xx():
    FakeSession.get_responses = [FakeResponse(status=404, text="missing")]
    with pytest.raises(api.WoWAPIError) as exc_info:
        await api.fetch_character_profile("soulseeker", "Voidok")
    assert exc_info.value.status == 404
    assert len(FakeSession.get_calls) == 1


@pytest.mark.asyncio
async def test_request_gives_up_after_max_retries():
    FakeSession.get_responses = [
        FakeResponse(status=500, text="err"),
        FakeResponse(status=500, text="err"),
        FakeResponse(status=500, text="err"),
    ]
    with pytest.raises(api.WoWAPIError) as exc_info:
        await api.fetch_character_profile("soulseeker", "Voidok")
    assert exc_info.value.status == 500
    assert len(FakeSession.get_calls) == api.RETRY_ATTEMPTS
