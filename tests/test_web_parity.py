"""The browser version (web/index.html) must give the same answers as the Python engine."""

import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from rcslab import CODES, ONE_WAY_SUPPORTS, Concrete, Steel
from rcslab.boq import one_way_boq, two_way_boq
from rcslab.one_way import OneWayInput, design_one_way
from rcslab.two_way import TwoWayInput, design_two_way

HTML = Path(__file__).resolve().parents[1] / "web" / "index.html"
SUPPORT_KEYS = {v.name: k for k, v in ONE_WAY_SUPPORTS.items()}
CODE_KEYS = {"eit": "EIT / ACI 318-99 (1.4D + 1.7L)", "aci19": "ACI 318-19 (1.2D + 1.6L)"}

ONE_WAY_CASES = [
    ("simple", 3.0, 15, 100, 200, 0, "eit", 240, 4000),
    ("one_end", 4.0, 13, 150, 300, 0, "aci19", 280, 3000),
    ("one_end_2", 3.5, 12, 100, 250, 0, "eit", 210, 4000),
    ("both_ends", 4.5, 12, 120, 400, 0, "eit", 320, 5000),
    ("cantilever", 1.5, 15, 100, 300, 250, "aci19", 240, 2400),
]
TWO_WAY_CASES = [
    (4, 5, 12, True, True, True, True, "eit"),
    (5, 4, 12, True, False, True, False, "eit"),
    (3, 6, 10, False, False, False, False, "aci19"),
    (4.2, 4.8, 11, True, False, False, False, "eit"),
    (2, 5, 12, True, True, False, True, "eit"),
]


def run_js(payload: dict) -> dict:
    engine = re.search(r"<script data-engine>(.*?)</script>", HTML.read_text(), re.S).group(1)
    driver = engine + """
const P = JSON.parse(process.argv[1]); const out = { ow: [], tw: [] };
for (const [sup, L, h, sdl, ll, P_, code, fc, fy] of P.ow) {
  const c = RC.concrete(fc), s = RC.steel(fy);
  const r = RC.designOneWay({ span: L, h, support: sup, sdl, ll, cover: 2, mainBar: "DB12", pEnd: P_, xi: 2 }, c, s, RC.CODES[code]);
  const q = RC.oneWayBoq(r, 4, 0.07);
  out.ow.push({ wu: r.wu, hMin: r.hMin, Mu: r.flexure.map(f => f.Mu), sp: r.flexure.map(f => f.spacing), tsp: r.temp.spacing,
    Vu: r.shear.Vu, dL: r.deflection.dL, dLong: r.deflection.dLong, ok: r.ok, steel: q.total });
}
for (const [x, y, h, e1, e2, e3, e4, code] of P.tw) {
  const c = RC.concrete(240), s = RC.steel(4000);
  const r = RC.designTwoWay({ x, y, h, sdl: 100, ll: 300, cover: 2, bar: "DB12", e1, e2, e3, e4 }, c, s, RC.CODES[code]);
  const q = RC.twoWayBoq(r, 0.07);
  out.tw.push({ cs: r.cs, m: r.m, Mu: [...r.fShort, ...r.fLong].map(f => f.Mu), sp: [...r.fShort, ...r.fLong].map(f => f.spacing),
    Vu: r.shear.Vu, ok: r.ok, steel: q.total });
}
console.log(JSON.stringify(out));
"""
    res = subprocess.run(["node", "-e", driver, json.dumps(payload)], capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_engine_matches_python():
    js = run_js({"ow": ONE_WAY_CASES, "tw": TWO_WAY_CASES})
    for case, got in zip(ONE_WAY_CASES, js["ow"]):
        sup, L, h, sdl, ll, p, code, fc, fy = case
        r = design_one_way(
            OneWayInput(L, h, SUPPORT_KEYS[sup], sdl, ll, 2.0, "DB12", p, 2.0),
            Concrete(fc), Steel(fy), CODES[CODE_KEYS[code]],
        )
        assert got["wu"] == pytest.approx(r.wu)
        assert got["hMin"] == pytest.approx(r.h_min)
        assert got["Mu"] == pytest.approx([f.Mu for f in r.flexure])
        assert got["sp"] == [f.spacing for f in r.flexure]
        assert got["tsp"] == r.temp.spacing
        assert got["Vu"] == pytest.approx(r.shear.Vu)
        assert got["dL"] == pytest.approx(r.deflection.delta_L)
        assert got["dLong"] == pytest.approx(r.deflection.delta_long)
        assert got["ok"] == r.ok
        assert got["steel"] == pytest.approx(one_way_boq(r, 4, 0.07).steel_total)
    for case, got in zip(TWO_WAY_CASES, js["tw"]):
        x, y, h, e1, e2, e3, e4, code = case
        r = design_two_way(TwoWayInput(x, y, h, 100, 300, e1, e2, e3, e4, 2.0, "DB12"),
                           Concrete(240), Steel(4000), CODES[CODE_KEYS[code]])
        assert got["cs"] == r.case
        assert got["m"] == pytest.approx(r.m)
        assert got["Mu"] == pytest.approx([f.Mu for f in r.flexure_short + r.flexure_long])
        assert got["sp"] == [f.spacing for f in r.flexure_short + r.flexure_long]
        assert got["Vu"] == pytest.approx(r.shear.Vu)
        assert got["ok"] == r.ok
        if r.is_two_way:
            assert got["steel"] == pytest.approx(two_way_boq(r, 0.07).steel_total)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_schedule_rows_match_python():
    from rcslab.schedule import COLUMNS, one_way_row, two_way_row

    engine = re.search(r"<script data-engine>(.*?)</script>", HTML.read_text(), re.S).group(1)
    driver = engine + """
const P = JSON.parse(process.argv[1]); const out = [];
const c = RC.concrete(240), s = RC.steel(4000), code = RC.CODES.eit;
for (const [sup, L, h, p] of P.ow) {
  const r = RC.designOneWay({ span: L, h, support: sup, sdl: 100, ll: 300, cover: 2, mainBar: "DB12", pEnd: p, xi: 2 }, c, s, code);
  out.push(RC.oneWayRow("S", r, 4));
}
for (const [x, y, e1, e2, e3, e4] of P.tw) {
  const r = RC.designTwoWay({ x, y, h: 12, sdl: 100, ll: 300, cover: 2, bar: "DB12", e1, e2, e3, e4 }, c, s, code);
  out.push(RC.twoWayRow("S", r));
}
console.log(JSON.stringify(out));
"""
    ow = [("simple", 3.0, 15, 0), ("one_end", 4.0, 14, 0), ("both_ends", 4.0, 12, 0), ("cantilever", 1.5, 15, 200)]
    tw = [(4, 5, True, True, True, True), (5, 4, True, False, True, True), (3, 4, False, False, False, True)]
    res = subprocess.run(["node", "-e", driver, json.dumps({"ow": ow, "tw": tw})], capture_output=True, text=True, check=True)
    js = json.loads(res.stdout)
    conc, steel, code = Concrete(240), Steel(4000), CODES[CODE_KEYS["eit"]]
    py = [
        one_way_row("S", design_one_way(OneWayInput(L, h, SUPPORT_KEYS[sup], 100, 300, 2.0, "DB12", p), conc, steel, code), 4)
        for sup, L, h, p in ow
    ] + [
        two_way_row("S", design_two_way(TwoWayInput(x, y, 12, 100, 300, *edges, 2.0, "DB12"), conc, steel, code))
        for x, y, *edges in tw
    ]
    for got, want in zip(js, py):
        for k in COLUMNS:
            assert got[k] == getattr(want, k), k
        assert got["ok"] == want.ok
