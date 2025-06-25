import pytest
from lotus_bot.cogs.wcr.duel import DuelCalculator


def test_scale_stat():
    calc = DuelCalculator()
    assert calc.scale_stat(100, 1) == 100
    assert calc.scale_stat(100, 2) == pytest.approx(110)
    assert calc.scale_stat(100, 5) == pytest.approx(140)


def test_spell_total_damage(wcr_data):
    calc = DuelCalculator()
    units = wcr_data["units"]
    if isinstance(units, dict) and "units" in units:
        units = units["units"]
    blizzard = next(u for u in units if u["id"] == "7")

    stats_lvl1 = calc.scaled_stats(blizzard, 1)
    stats_lvl2 = calc.scaled_stats(blizzard, 2)

    dmg1 = calc.spell_total_damage(blizzard, stats_lvl1)
    dmg2 = calc.spell_total_damage(blizzard, stats_lvl2)

    assert dmg1 == pytest.approx(500)
    assert dmg2 == pytest.approx(550)


def test_duel_result_equal_damage_spells(wcr_data):
    calc = DuelCalculator()
    units = wcr_data["units"]
    if isinstance(units, dict) and "units" in units:
        units = units["units"]
    spell_a = next(u for u in units if u["id"] == "10")
    spell_b = next(u for u in units if u["id"] == "36")

    assert calc.duel_result(spell_a, 1, spell_b, 1) is None
