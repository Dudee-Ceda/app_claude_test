import math

import pytest

from rcslab import CODES, Concrete, Steel
from rcslab.flexure import design_flexure, rho_balanced
from rcslab.one_way import ONE_WAY_SUPPORTS, OneWayInput, design_one_way
from rcslab.two_way import TwoWayInput, coefficient, design_two_way

CODE = CODES["EIT / ACI 318-99 (1.4D + 1.7L)"]
CONC = Concrete(240)
SD40 = Steel(4000)
SIMPLE = next(k for k, v in ONE_WAY_SUPPORTS.items() if v.name == "simple")
CANT = next(k for k, v in ONE_WAY_SUPPORTS.items() if v.name == "cantilever")


def test_rho_balanced_sd40_fc240():
    # 0.85·0.85·240/4000 · 6120/10120 = 0.02622
    assert rho_balanced(CONC, SD40) == pytest.approx(0.02622, rel=1e-3)


def test_flexure_hand_calc():
    # Mu = 1000 kg-m, d = 9.4 cm -> Rn = 100000/(0.9·100·88.36) = 12.574 ksc
    r = design_flexure("x", 1000, 9.4, 12, "DB12", 36, CONC, SD40, CODE)
    assert r.Rn == pytest.approx(12.574, rel=1e-3)
    rho = 0.85 * 240 / 4000 * (1 - math.sqrt(1 - 2 * 12.574 / (0.85 * 240)))
    assert r.rho_req == pytest.approx(rho, rel=1e-3)
    assert r.As_prov >= r.As_design
    assert r.phiMn >= 1000
    assert r.spacing % 2.5 == 0
    assert r.ok


def test_as_min_governs_for_small_moment():
    r = design_flexure("x", 50, 9.4, 12, "RB9", 36, CONC, SD40, CODE)
    assert r.As_design == pytest.approx(0.0018 * 100 * 12)
    assert r.spacing <= 36


def test_overloaded_section_fails():
    r = design_flexure("x", 20000, 9.4, 12, "DB12", 36, CONC, SD40, CODE)
    assert not r.ok


def test_one_way_simple_span():
    res = design_one_way(OneWayInput(3.0, 15, SIMPLE, 100, 200), CONC, SD40, CODE)
    wu = 1.4 * (360 + 100) + 1.7 * 200
    assert res.wu == pytest.approx(wu)
    assert res.moments["+M กลางช่วง"] == pytest.approx(wu * 9 / 8)
    assert res.h_min == pytest.approx(300 / 20 * (0.4 + 4000 / 7000))
    assert res.ok


def test_one_way_cantilever_thickness():
    res = design_one_way(OneWayInput(1.5, 10, CANT, 100, 200), CONC, SD40, CODE)
    assert res.h_min == pytest.approx(150 / 10 * (0.4 + 4000 / 7000))
    assert not res.h_ok


def test_method2_coefficients():
    assert coefficient(1, "pos", 1.0, "short") == pytest.approx(0.025)
    assert coefficient(2, "neg_cont", 0.75, "short") == pytest.approx((0.055 + 0.062) / 2)
    assert coefficient(5, "pos", 0.3, "short") == pytest.approx(0.083)  # clamp to m = 0.5
    assert coefficient(3, "pos", 0.6, "long") == pytest.approx(0.037)
    assert coefficient(5, "neg_cont", 0.8, "short") == 0.0


def test_two_way_case_and_swap():
    a = design_two_way(TwoWayInput(4, 5, 12, 100, 200, True, False, True, False), CONC, SD40, CODE)
    b = design_two_way(TwoWayInput(5, 4, 12, 100, 200, True, False, True, False), CONC, SD40, CODE)
    assert a.case == 3 and b.case == 3
    assert a.S == b.S == 4 and a.m == pytest.approx(0.8)
    assert a.moments == pytest.approx(b.moments)
    assert a.moments["S: +M กลางช่วง"] == pytest.approx(0.048 * a.wu * 16)
    assert a.h_min == pytest.approx(1800 / 180)


def test_two_way_beam_loads_square():
    r = design_two_way(TwoWayInput(4, 4, 12, 100, 200), CONC, SD40, CODE)
    assert r.case == 1
    assert r.beam_load_short_edge == pytest.approx(r.beam_load_long_edge)
    assert r.d_long == pytest.approx(r.d_short - 1.2)
    assert r.ok


def test_two_way_flags_one_way_ratio():
    r = design_two_way(TwoWayInput(2, 5, 12, 100, 200), CONC, SD40, CODE)
    assert not r.is_two_way and not r.ok
