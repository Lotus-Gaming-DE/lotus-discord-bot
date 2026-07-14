import random

from lotus_bot.cogs.wow.duo_logic import (
    TEAM_NAME_POOL,
    TIME_WINDOWS,
    decode_windows,
    encode_windows,
    format_windows,
    overlap_keys,
    pick_team_name,
    rank_candidates,
)


def test_encode_windows_is_canonical_and_filters_invalid():
    # Unknown keys dropped, duplicates collapsed, order follows TIME_WINDOWS.
    encoded = encode_windows(["spaet", "wd_abend", "bogus", "wd_abend"])
    assert encoded == "wd_abend,spaet"


def test_decode_round_trips_and_ignores_junk():
    assert decode_windows("wd_abend,spaet") == ["wd_abend", "spaet"]
    assert decode_windows("") == []
    assert decode_windows(None) == []
    assert decode_windows("bogus,wd_vormittag") == ["wd_vormittag"]


def test_format_windows_labels_and_dash():
    assert format_windows(["wd_abend"]) == TIME_WINDOWS["wd_abend"]
    assert format_windows([]) == "—"


def test_overlap_keys_intersection_in_canonical_order():
    a = ["wd_abend", "we_abend", "spaet"]
    b = ["spaet", "wd_abend", "we_tag"]
    assert overlap_keys(a, b) == ["wd_abend", "spaet"]


def test_rank_candidates_orders_by_overlap_then_level_then_name():
    my_windows = ["wd_abend", "we_abend"]
    my_level = 30
    others = [
        # (user_id, name, level, windows)
        (1, "Zena", 31, ["wd_abend"]),  # overlap 1, dist 1
        (2, "Arno", 60, ["wd_abend", "we_abend"]),  # overlap 2, dist 30
        (3, "Bela", 33, ["wd_abend", "we_abend"]),  # overlap 2, dist 3
        (4, "Cara", 30, ["wd_vormittag"]),  # overlap 0
    ]
    ranked = rank_candidates(my_windows, my_level, others)
    # Best overlap first; within same overlap, closer level first.
    assert [c.discord_user_id for c in ranked] == [3, 2, 1, 4]
    assert ranked[0].overlap_count == 2
    assert ranked[-1].overlap_count == 0


def test_pick_team_name_avoids_used():
    used = set(TEAM_NAME_POOL[:-1])  # only the last name is free
    name = pick_team_name(used, rng=random.Random(0))
    assert name == TEAM_NAME_POOL[-1]


def test_pick_team_name_falls_back_to_numbered_when_pool_exhausted():
    used = set(TEAM_NAME_POOL)
    name = pick_team_name(used, rng=random.Random(1))
    assert name.endswith(" 2")
    base = name[: -len(" 2")]
    assert base in TEAM_NAME_POOL
