import math

import pytest

from beam.analysis import PointLoad, analyze
from beam import design as dsg

L, w, P, EI = 600.0, 20.0, 5000.0, 1e10


@pytest.mark.parametrize(
    "beam_type, Mpos, Mneg, defl",
    [
        ("simple", w * L**2 / 8, 0.0, 5 * w * L**4 / (384 * EI)),
        ("cantilever", 0.0, w * L**2 / 2, w * L**4 / (8 * EI)),
        ("fixed_fixed", w * L**2 / 24, w * L**2 / 12, w * L**4 / (384 * EI)),
        ("propped", 9 * w * L**2 / 128, w * L**2 / 8, w * L**4 / (185 * EI)),
    ],
)
def test_udl_closed_form(beam_type, Mpos, Mneg, defl):
    r = analyze(L, beam_type, w, EI=EI)
    assert max(r.M.max(), 0) == pytest.approx(Mpos, rel=1e-3, abs=1e-6)
    assert max(-r.M.min(), 0) == pytest.approx(Mneg, rel=1e-3, abs=1e-6)
    assert r.defl.max() == pytest.approx(defl, rel=5e-3)


def test_point_load_simple():
    r = analyze(L, "simple", 0.0, [PointLoad(200.0, P)], EI=EI)
    a, b = 200.0, 400.0
    assert r.M.max() == pytest.approx(P * a * b / L, rel=1e-6)
    assert r.reactions["left"][0] == pytest.approx(P * b / L, rel=1e-6)


def test_flexure_design_textbook():
    # คาน 30x60 cm, fc'=240, fy=4000, Mu = 25 t-m
    sec = dsg.Section(b=30, h=60, cover=4, stirrup="RB9", fc=240, fy=4000, fyt=2400)
    r = dsg.design_flexure(sec, 25e5, "DB20", "DB20")
    assert r.ok and not r.doubly
    assert r.phiMn >= 25e5
    assert r.As_prov >= r.As_req
    assert 10 < r.As_req < 15


def test_doubly_reinforced_triggered():
    sec = dsg.Section(b=25, h=40, cover=3, stirrup="RB9", fc=240, fy=4000, fyt=2400)
    r = dsg.design_flexure(sec, 20e5, "DB25", "DB20")
    assert r.doubly
    assert r.As_comp_req > 0


def test_shear_design():
    sec = dsg.Section(b=30, h=60, cover=4, stirrup="RB9", fc=240, fy=4000, fyt=2400)
    r = dsg.design_shear(sec, 25000, 54)
    assert r.ok
    assert r.phiVn >= 25000
    assert r.s_use <= r.s_max
    assert math.isclose(r.phiVc, 0.85 * 0.53 * math.sqrt(240) * 30 * 54)
