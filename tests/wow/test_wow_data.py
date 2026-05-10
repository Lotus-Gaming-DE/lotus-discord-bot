import pytest

from lotus_bot.cogs.wow.data import RosterMember, WoWData, parse_roster_member

pytestmark = pytest.mark.asyncio


def roster_member(name="Lyxendra", key="id:123"):
    return RosterMember(
        character_key=key,
        character_id=123,
        name=name,
        realm_slug="soulseeker",
        level=44,
        class_id=4,
        race_id=8,
        faction="HORDE",
        guild_rank=1,
    )


async def test_parse_roster_member_with_character_id():
    member = parse_roster_member(
        {
            "character": {
                "id": 123,
                "name": "Lyxendra",
                "level": 44,
                "realm": {"slug": "soulseeker"},
                "playable_class": {"id": 4},
                "playable_race": {"id": 8},
                "faction": {"type": "HORDE"},
            },
            "rank": 1,
        }
    )

    assert member.character_key == "id:123"
    assert member.name == "Lyxendra"
    assert member.level == 44
    assert member.class_id == 4
    assert member.race_id == 8
    assert member.faction == "HORDE"
    assert member.guild_rank == 1


async def test_parse_roster_member_fallback_key():
    member = parse_roster_member(
        {
            "character": {
                "name": "Noid",
                "level": 30,
                "realm": {"slug": "soulseeker"},
            }
        }
    )

    assert member.character_key == "realm:soulseeker:name:noid"


async def test_parse_roster_member_rejects_incomplete_entry():
    assert parse_roster_member({"character": {"name": "NoRealm", "level": 1}}) is None


async def test_claim_lifecycle_and_case_insensitive_lookup(tmp_path):
    data = WoWData(str(tmp_path / "wow.db"))
    member = roster_member()
    await data.replace_snapshot([member])

    found = await data.find_roster_member_by_name("lyxendra")
    assert found == member

    claim, created = await data.create_claim(member, 42)
    assert created is True
    assert claim.character_name == "Lyxendra"
    assert claim.status == "unverified"

    same_claim, created = await data.create_claim(member, 43)
    assert created is False
    assert same_claim.discord_user_id == 42

    await data.verify_claim(member.character_key, 99)
    verified = await data.get_claim(member.character_key)
    assert verified.status == "verified"
    assert verified.verified_by == 99

    assert await data.release_claim(member.character_key, 43) is False
    assert await data.release_claim(member.character_key, 42) is True
    assert await data.get_claim(member.character_key) is None
    await data.close()


async def test_claim_listing_and_review_message_lookup(tmp_path):
    data = WoWData(str(tmp_path / "wow.db"))
    member = roster_member()
    await data.replace_snapshot([member])
    claim, _ = await data.create_claim(member, 42)
    await data.set_claim_review_message(claim.character_key, 555)

    by_message = await data.get_claim_by_review_message(555)
    assert by_message.character_key == claim.character_key
    by_name = await data.get_claim_by_name("lyxendra")
    assert by_name == by_message
    assert await data.claims_for_user(42) == [by_message]
    assert await data.list_claims("unverified") == [by_message]
    assert await data.list_claims("verified") == []

    await data.remove_claim(claim.character_key)
    assert await data.list_claims() == []
    await data.close()


async def test_character_profession_lifecycle(tmp_path):
    data = WoWData(str(tmp_path / "wow.db"))
    member = roster_member()
    await data.replace_snapshot([member])
    claim, _ = await data.create_claim(member, 42)

    profile = await data.set_character_profession(claim, "alchemy", 250, "TrÃ¤nke")
    assert profile.character_name == "Lyxendra"
    assert profile.profession_id == "alchemy"
    assert profile.skill_level == 250
    assert profile.specialization == "TrÃ¤nke"

    updated = await data.set_character_profession(claim, "alchemy", 300, None)
    assert updated.skill_level == 300
    assert updated.specialization is None

    assert await data.professions_for_user(42) == [updated]
    assert await data.list_professions("alchemy") == [updated]
    assert await data.find_crafters("alchemy", 275) == [updated]
    assert await data.find_crafters("alchemy", 301) == []

    assert await data.remove_character_profession(member.character_key, "alchemy")
    assert await data.professions_for_user(42) == []
    await data.close()


async def test_character_profession_rejects_invalid_skill(tmp_path):
    data = WoWData(str(tmp_path / "wow.db"))
    member = roster_member()
    await data.replace_snapshot([member])
    claim, _ = await data.create_claim(member, 42)

    with pytest.raises(ValueError):
        await data.set_character_profession(claim, "alchemy", 0)
    with pytest.raises(ValueError):
        await data.set_character_profession(claim, "alchemy", 301)
    await data.close()


async def test_character_profession_hidden_after_claim_remove(tmp_path):
    data = WoWData(str(tmp_path / "wow.db"))
    member = roster_member()
    await data.replace_snapshot([member])
    claim, _ = await data.create_claim(member, 42)
    await data.set_character_profession(claim, "alchemy", 250)

    await data.remove_claim(member.character_key)

    assert await data.list_professions() == []
    assert await data.find_crafters("alchemy", 1) == []
    await data.close()
