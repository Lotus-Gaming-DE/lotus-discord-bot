import pytest
from cogs.wcr.duel import DuelCalculator


def test_scale_stat():
    calc = DuelCalculator()
    assert calc.scale_stat(100, 1) == 100
    assert calc.scale_stat(100, 2) == pytest.approx(110)
    assert calc.scale_stat(100, 5) == pytest.approx(140)
