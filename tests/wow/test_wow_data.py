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


async def test_ghost_members_filters_and_orders_by_level(tmp_path):
    data = WoWData(str(tmp_path / "wow.db"))
    alive = roster_member(name="Alive", key="id:alive")
    ghost_high = RosterMember(
        character_key="id:gh",
        character_id=2,
        name="HighGhost",
        realm_slug="soulseeker",
        level=42,
        class_id=4,
        race_id=8,
        faction="HORDE",
        guild_rank=1,
        is_ghost=True,
    )
    ghost_low = RosterMember(
        character_key="id:gl",
        character_id=3,
        name="LowGhost",
        realm_slug="soulseeker",
        level=12,
        class_id=4,
        race_id=8,
        faction="HORDE",
        guild_rank=1,
        is_ghost=True,
    )
    await data.replace_snapshot([alive, ghost_low, ghost_high])

    ghosts_list = await data.ghost_members()

    # Only dead chars, sorted by level descending.
    assert [g.name for g in ghosts_list] == ["HighGhost", "LowGhost"]
    assert all(g.is_ghost for g in ghosts_list)
    await data.close()


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


async def test_known_recipe_lifecycle_and_duplicate_blocking(tmp_path):
    data = WoWData(str(tmp_path / "wow.db"))
    member = roster_member()
    await data.replace_snapshot([member])
    claim, _ = await data.create_claim(member, 42)
    await data.set_character_profession(claim, "alchemy", 250)

    assert await data.add_known_recipes(member.character_key, "alchemy", ["spell.2335"])
    assert (
        await data.add_known_recipes(member.character_key, "alchemy", ["spell.2335"])
    ) == 0
    assert await data.known_recipe_spell_ids(member.character_key) == {"spell.2335"}

    recipes = await data.known_recipes_for_character(member.character_key)
    assert len(recipes) == 1
    assert recipes[0].spell_id == "spell.2335"
    assert recipes[0].profession_id == "alchemy"

    crafters = await data.find_crafters_with_known_recipe("alchemy", 200, "spell.2335")
    assert crafters[0].character_name == "Lyxendra"

    assert await data.remove_known_recipe(member.character_key, "spell.2335")
    assert not await data.remove_known_recipe(member.character_key, "spell.2335")
    await data.close()


async def test_known_recipe_empty_insert_is_noop(tmp_path):
    data = WoWData(str(tmp_path / "wow.db"))

    assert await data.add_known_recipes("id:missing", "alchemy", []) == 0
    assert await data.last_scan_at() is None
    await data.close()


async def test_known_recipes_survive_claim_remove_but_are_hidden(tmp_path):
    data = WoWData(str(tmp_path / "wow.db"))
    member = roster_member()
    await data.replace_snapshot([member])
    claim, _ = await data.create_claim(member, 42)
    await data.set_character_profession(claim, "alchemy", 250)
    await data.add_known_recipes(member.character_key, "alchemy", ["spell.2335"])

    await data.remove_claim(member.character_key)

    assert await data.known_recipe_spell_ids(member.character_key) == {"spell.2335"}
    assert await data.find_crafters_with_known_recipe("alchemy", 1, "spell.2335") == []
    await data.close()
