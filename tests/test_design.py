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


# --------------------------------------------------------------------------- deflection
from rcslab.boq import STEEL_DENSITY, one_way_boq, two_way_boq  # noqa: E402
from rcslab.deflection import cracked_inertia, effective_inertia, one_way_deflection  # noqa: E402
from rcslab.report_pdf import markdown_to_pdf  # noqa: E402


def test_uncracked_simple_span_deflection():
    # tiny load -> Ie = Ig, Δ = 5wL⁴/384EIg
    df = one_way_deflection("simple", 3.0, 15, 12.4, 2.83, 10, 10, 0, 8, CONC, SD40)
    Ig = 100 * 15**3 / 12
    assert df.Ie_DL == pytest.approx(Ig)
    assert df.delta_DL == pytest.approx(5 * 0.2 * 300**4 / (384 * CONC.Ec * Ig))
    assert df.limit_L == pytest.approx(300 / 360)


def test_cracked_inertia_and_ie_bounds():
    n = SD40.Es / CONC.Ec
    Icr = cracked_inertia(2.83, 12.4, n)
    x = (-n * 2.83 + math.sqrt((n * 2.83) ** 2 + 200 * n * 2.83 * 12.4)) / 100
    assert 100 * x**2 / 2 == pytest.approx(n * 2.83 * (12.4 - x))
    Ig = 100 * 15**3 / 12
    assert Icr < effective_inertia(2e5, 1e5, Ig, Icr) < Ig


def test_cantilever_end_load_increases_moment_and_deflection():
    a = design_one_way(OneWayInput(1.5, 15, CANT, 100, 200), CONC, SD40, CODE)
    b = design_one_way(OneWayInput(1.5, 15, CANT, 100, 200, p_end=300), CONC, SD40, CODE)
    assert b.moments["-M ที่ยึดแน่น"] - a.moments["-M ที่ยึดแน่น"] == pytest.approx(1.4 * 300 * 1.5)
    assert b.shear.Vu - a.shear.Vu == pytest.approx(1.4 * 300)
    assert b.deflection.delta_D > a.deflection.delta_D
    assert b.deflection.limit_L == pytest.approx(300 / 360)  # 2L for cantilever


def test_thin_slab_passes_when_deflection_ok():
    res = design_one_way(OneWayInput(3.0, 13, SIMPLE, 50, 150), CONC, SD40, CODE)
    assert not res.h_ok
    assert res.ok == res.deflection.ok


# --------------------------------------------------------------------------- BOQ
def test_one_way_boq():
    res = design_one_way(OneWayInput(3.0, 15, SIMPLE, 100, 200), CONC, SD40, CODE)
    boq = one_way_boq(res, 4.0, waste=0.0)
    assert boq.concrete == pytest.approx(3 * 4 * 0.15)
    main = boq.items[0]
    assert main.count == math.floor(400 / main.spacing) + 1
    assert main.length == pytest.approx(3.2)
    assert main.weight == pytest.approx(main.count * 3.2 * 1.131 * STEEL_DENSITY)
    assert boq.steel_net == pytest.approx(sum(i.weight for i in boq.items))


def test_two_way_boq_items():
    r = design_two_way(TwoWayInput(4, 5, 12, 100, 200, True, False, True, False), CONC, SD40, CODE)
    boq = two_way_boq(r, waste=0.1)
    assert len(boq.items) == 6
    assert boq.area == 20
    assert boq.steel_total == pytest.approx(boq.steel_net * 1.1)


def test_pdf_render():
    pdf = markdown_to_pdf("# หัวข้อ\n\n## ส่วน\n- φMn = 1,000 kg-m ✅ ผ่าน **DB12 @ 0.20 m**\n\n| a | b |\n|---|---|\n| 1 | 2 |\n")
    assert pdf[:4] == b"%PDF" and len(pdf) > 1000


# --------------------------------------------------------------------------- schedule
from rcslab.detailing import NA, cut_length, detail_one_way, detail_two_way, suggested_camber  # noqa: E402
from rcslab.flexure import module_spacings  # noqa: E402
from rcslab.schedule import COLUMNS, drawing_callout, lap_length, schedule_records  # noqa: E402


def test_module_spacings_divide_module():
    assert module_spacings(30) == [30, 15, 10, 7.5, 5]
    assert module_spacings(25) == [25, 12.5, 5]
    assert module_spacings(20) == [20, 10, 5]


def _spacings_on_module(flex, module):
    return all(abs(module / f.spacing - round(module / f.spacing)) < 1e-9 for f in flex)


def test_harmonized_spacings_share_one_module():
    cases = [
        design_two_way(TwoWayInput(9, 10.5, 25, 100, 500, True, False, True, True, bar="DB16"), CONC, SD40, CODE),
        design_two_way(TwoWayInput(6, 8, 20, 150, 400, True, False, False, True), CONC, SD40, CODE),
    ]
    for r in cases:
        flex = r.flexure_short + r.flexure_long + [r.temp]
        assert r.module in (30, 25, 20) and _spacings_on_module(flex, r.module)
        assert all(f.As_prov >= f.As_design - 1e-9 and f.spacing <= 30 for f in flex)
        assert r.ok
    for sup in ONE_WAY_SUPPORTS:
        r = design_one_way(OneWayInput(3.0, 15, sup, 100, 300), CONC, SD40, CODE)
        assert _spacings_on_module(r.flexure + [r.temp], r.module)


def test_cut_lengths_and_camber():
    assert cut_length(5.7, 4) == pytest.approx(1.5)  # 1425 mm -> 1500
    assert cut_length(5.7, 3) == pytest.approx(1.9)
    assert suggested_camber(None, 9.0) == 20 and suggested_camber(None, 6.0) == 10
    assert suggested_camber(12.1, 4) == 15 and suggested_camber(2, 4) == 10


def test_two_way_schedule_rows_mirror_each_other():
    tw = design_two_way(TwoWayInput(6, 8, 20, 150, 400, True, False, False, True), CONC, SD40, CODE)
    cross, long = schedule_records("SA1", detail_two_way(tw, "A"))
    assert (cross["section"], long["section"]) == ("CROSS", "LONG")
    assert cross["span"] == "6,000" and long["span"] == "8,000" and cross["t"] == "200"
    # even positions in one section are the other section's odd positions
    assert cross["b2"] == long["b1"] and long["b2"] == cross["b1"]
    assert cross["t2"] == long["t1"] and cross["t4"] == long["t3"]
    assert cross["t5"] == NA  # Type A: no full-length top mesh
    assert cross["l1"] == "1,500" and cross["l2"] == "1,900"
    b_cross, _ = schedule_records("SA2", detail_two_way(tw, "B"))
    assert b_cross["t5"].startswith("DB12 @") and b_cross["t6"].startswith("DB12 @")
    assert set(cross) == set(COLUMNS)


def test_one_way_and_cantilever_rows():
    ow = design_one_way(OneWayInput(3.0, 15, SIMPLE, 100, 200), CONC, SD40, CODE)
    cross, long = schedule_records("S2", detail_one_way(ow, 4.0, "C"))
    assert cross["slab_type"] == "C" and cross["t3"] == NA and cross["t1"] != NA  # simple span: edge top bars only
    assert cross["b2"] == long["b1"] and long["t2"] == cross["t1"]
    assert cross["l1"] == "700"  # (3.0 - 0.3) / 4 = 675 -> 700
    cant = design_one_way(OneWayInput(2.0, 20, CANT, 100, 200, p_end=400), CONC, SD40, CODE)
    det = detail_one_way(cant, None, "G")
    cross, long = schedule_records("S3", det)
    assert cross["t1"] == NA and cross["l1"] == NA and long["b1"] == NA and long["span"] == "VARIES"
    main = cant.flexure[0]
    # basic (Top 5) + extra (Top 3) cover the support moment, both on the slab module
    total = 100 * 1.131 / det.cant_basic.spacing + (100 * 1.131 / det.cant_extra.spacing if det.cant_extra else 0)
    assert total >= main.As_design - 1e-9
    assert det.cant_extra is None or (cant.module / det.cant_extra.spacing) % 1 == 0
    assert det.l2_cross is None or 0 < det.l2_cross <= 2.0


def test_drawing_callout():
    assert drawing_callout("DB12", 20) == "DB12@0.20"
    assert drawing_callout("RB9", 22.5) == "RB9@0.225"


def test_lap_length():
    assert lap_length("DB12") == pytest.approx(0.48)
    assert lap_length("RB6") == pytest.approx(0.30)


def test_one_bar_size_per_slab():
    for sup in ONE_WAY_SUPPORTS:
        res = design_one_way(OneWayInput(2.0, 15, sup, 100, 200, main_bar="DB10"), CONC, SD40, CODE)
        assert {f.bar for f in res.flexure + [res.temp]} == {"DB10"}
        assert {i.bar for i in one_way_boq(res, 3.0).items} == {"DB10"}


def test_one_way_boq_counts_every_support():
    both = next(k for k, v in ONE_WAY_SUPPORTS.items() if v.name == "both_ends")
    res = design_one_way(OneWayInput(3.0, 12, both, 100, 200), CONC, SD40, CODE)
    top = next(i for i in one_way_boq(res, 4.0).items if i.description.startswith("เหล็กบน"))
    assert top.count == 2 * (math.floor(400 / top.spacing) + 1)  # two continuous supports
    res = design_one_way(OneWayInput(3.0, 15, SIMPLE, 100, 200), CONC, SD40, CODE)
    assert any("× 2 ด้าน" in i.description for i in one_way_boq(res, 4.0).items)


def test_spacing_never_exceeds_30cm():
    for sup in ONE_WAY_SUPPORTS:
        for bar in ("DB12", "DB16", "DB20"):
            res = design_one_way(OneWayInput(2.0, 20, sup, 50, 100, main_bar=bar), CONC, SD40, CODE)
            assert max(f.spacing for f in res.flexure + [res.temp]) <= 30
    tw = design_two_way(TwoWayInput(3, 3.5, 20, 50, 100, bar="DB16"), CONC, SD40, CODE)
    assert max(f.spacing for f in tw.flexure_short + tw.flexure_long) == 30
