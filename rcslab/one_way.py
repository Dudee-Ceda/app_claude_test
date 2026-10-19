"""One-way slab design using ACI approximate moment coefficients."""

from dataclasses import dataclass, field

from .deflection import DeflectionResult, one_way_deflection
from .flexure import B, FlexureResult, ShearResult, check_shear, design_flexure
from .materials import Concrete, DesignCode, Steel, bar_dia


@dataclass(frozen=True)
class OneWaySupport:
    name: str
    h_div: float  # ACI 318 Table 9.5(a): h_min = L / h_div
    pos: float  # +M = wL² / pos  (0 = none)
    neg_cont: float  # -M at continuous support = wL² / neg_cont
    neg_disc: float  # -M at discontinuous (integral) support
    shear: float  # Vu = shear · wL / 2


ONE_WAY_SUPPORTS: dict[str, OneWaySupport] = {
    "ช่วงเดียว วางบนที่รองรับธรรมดา (Simply supported)": OneWaySupport("simple", 20, 8, 0, 0, 1.0),
    "ต่อเนื่องปลายเดียว — ช่วงริม, มากกว่า 2 ช่วง (One end continuous)": OneWaySupport(
        "one_end", 24, 11, 10, 24, 1.15
    ),
    "ต่อเนื่องปลายเดียว — 2 ช่วง (Two spans)": OneWaySupport("one_end_2", 24, 11, 9, 24, 1.15),
    "ต่อเนื่องสองปลาย (Both ends continuous)": OneWaySupport("both_ends", 28, 16, 11, 0, 1.0),
    "พื้นยื่น (Cantilever)": OneWaySupport("cantilever", 10, 0, 2, 0, 2.0),
}


@dataclass
class OneWayInput:
    span: float  # m, clear span
    h: float  # cm
    support: str
    sdl: float  # kg/m², superimposed dead load
    ll: float  # kg/m²
    cover: float = 2.0  # cm
    main_bar: str = "DB12"
    temp_bar: str = "RB9"
    p_end: float = 0.0  # kg/m, dead line load at the free end (cantilever only)
    xi: float = 2.0  # long-term deflection factor (ACI: 2.0 for ≥ 5 years)


@dataclass
class OneWayResult:
    inp: OneWayInput
    sw: float
    wd: float
    wu: float
    h_min: float
    h_ok: bool
    d: float
    moments: dict[str, float]
    flexure: list[FlexureResult]
    temp: FlexureResult
    shear: ShearResult
    deflection: DeflectionResult
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        # ACI: thickness below h,min is acceptable when computed deflections are within limits
        return (self.h_ok or self.deflection.ok) and self.shear.ok and all(f.ok for f in self.flexure) and self.temp.ok


def design_one_way(inp: OneWayInput, conc: Concrete, steel: Steel, code: DesignCode) -> OneWayResult:
    sup = ONE_WAY_SUPPORTS[inp.support]
    L = inp.span
    sw = conc.unit_weight * inp.h / 100
    wd = sw + inp.sdl
    wu = code.dl_factor * wd + code.ll_factor * inp.ll  # kg/m² = kg/m per 1 m strip

    fy_mod = 0.4 + steel.fy / 7000  # fy in ksc (≈ 0.4 + fy[MPa]/700)
    h_min = L * 100 / sup.h_div * fy_mod
    h_ok = inp.h >= h_min - 1e-9

    d = inp.h - inp.cover - bar_dia(inp.main_bar) / 2
    s_max = min(3 * inp.h, 45.0)
    s_temp = min(5 * inp.h, 45.0)

    cantilever = sup.name == "cantilever"
    p_u = code.dl_factor * inp.p_end if cantilever else 0.0

    moments: dict[str, float] = {}
    if sup.pos:
        moments["+M กลางช่วง"] = wu * L**2 / sup.pos
    if sup.neg_cont:
        label = "-M ที่ยึดแน่น" if cantilever else "-M ที่รองรับต่อเนื่อง"
        moments[label] = wu * L**2 / sup.neg_cont + p_u * L
    if sup.neg_disc:
        moments["-M ที่รองรับไม่ต่อเนื่อง"] = wu * L**2 / sup.neg_disc

    flexure = [
        design_flexure(k, m, d, inp.h, inp.main_bar, s_max, conc, steel, code) for k, m in moments.items()
    ]
    temp = design_flexure("เหล็กกันร้าว (Temp.)", 0.0, d, inp.h, inp.temp_bar, s_temp, conc, steel, code)

    Vu = sup.shear * wu * L / 2 + p_u
    shear = check_shear(Vu, d, conc, code)

    crit = flexure[0]  # +M for spans, -M at the fixed end for a cantilever
    deflection = one_way_deflection(
        "one_end" if sup.name == "one_end_2" else sup.name,
        L,
        inp.h,
        d,
        crit.As_prov,
        wd,
        inp.ll,
        inp.p_end if cantilever else 0.0,
        sup.neg_cont if cantilever else sup.pos,
        conc,
        steel,
        inp.xi,
    )

    notes = []
    if not h_ok:
        verdict = "การแอ่นตัวอยู่ในเกณฑ์ จึงใช้ได้" if deflection.ok else "การแอ่นตัวเกินเกณฑ์ — เพิ่มความหนา"
        notes.append(f"ความหนาน้อยกว่า h,min = {h_min:.1f} cm (ACI 318 Table 9.5a) — {verdict}")
    if not shear.ok:
        notes.append("กำลังรับแรงเฉือนไม่พอ — เพิ่มความหนาพื้น")
    if not deflection.ok:
        notes.append("การแอ่นตัวเกินเกณฑ์ L/360 หรือ L/240")
    if cantilever:
        notes.append("พื้นยื่น: เกณฑ์การแอ่นตัวเทียบกับช่วงเทียบเท่า 2L; เหล็กหลักอยู่บน ต้องยึดฝังเข้าช่วงในอย่างน้อย L")
    return OneWayResult(inp, sw, wd, wu, h_min, h_ok, d, moments, flexure, temp, shear, deflection, notes)


__all__ = ["B", "OneWayInput", "OneWayResult", "design_one_way", "ONE_WAY_SUPPORTS"]
