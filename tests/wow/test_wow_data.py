from lotus_bot.cogs.wow.data import parse_roster_member


def test_parse_roster_member_with_character_id():
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


def test_parse_roster_member_fallback_key():
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


def test_parse_roster_member_rejects_incomplete_entry():
    assert parse_roster_member({"character": {"name": "NoRealm", "level": 1}}) is None
