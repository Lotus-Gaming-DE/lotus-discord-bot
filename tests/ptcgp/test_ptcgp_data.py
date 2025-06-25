import pytest

from lotus_bot.cogs.ptcgp.data import PTCGPData


CARD_EN = {
    "id": "1",
    "name": "Pikachu",
    "hp": 60,
    "types": ["Electric"],
    "image": "http://example.com/pika_en.png",
    "attacks": [{"name": "Thunder"}],
    "rarity": "Common",
    "set": {"name": "Base"},
}

CARD_DE = {
    "id": "1",
    "name": "Pikachu",
    "hp": 60,
    "types": ["Elektro"],
    "image": "http://example.com/pika_de.png",
    "attacks": [{"name": "Donner"}],
    "rarity": "Gewöhnlich",
    "set": {"name": "Basis"},
}


@pytest.mark.asyncio
async def test_replace_and_fetch(tmp_path):
    db_path = tmp_path / "cards.db"
    data = PTCGPData(str(db_path))

    await data.replace_all([CARD_EN], [CARD_DE])

    card = await data.get_card("1")
    assert card["en"]["name"] == "Pikachu"
    assert card["de"]["attacks"][0]["name"] == "Donner"

    counts = await data.count_cards()
    assert counts == {"en": 1, "de": 1}

    await data.close()
