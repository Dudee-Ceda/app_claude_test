"""One-way slab design using ACI approximate moment coefficients."""

from dataclasses import dataclass, field

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
    "ต่อเนื่องปลายเดียว (One end continuous)": OneWaySupport("one_end", 24, 11, 10, 24, 1.15),
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
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.h_ok and self.shear.ok and all(f.ok for f in self.flexure) and self.temp.ok


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

    moments: dict[str, float] = {}
    if sup.pos:
        moments["+M กลางช่วง"] = wu * L**2 / sup.pos
    if sup.neg_cont:
        label = "-M ที่ยึดแน่น" if sup.name == "cantilever" else "-M ที่รองรับต่อเนื่อง"
        moments[label] = wu * L**2 / sup.neg_cont
    if sup.neg_disc:
        moments["-M ที่รองรับไม่ต่อเนื่อง"] = wu * L**2 / sup.neg_disc

    flexure = [
        design_flexure(k, m, d, inp.h, inp.main_bar, s_max, conc, steel, code) for k, m in moments.items()
    ]
    temp = design_flexure("เหล็กกันร้าว (Temp.)", 0.0, d, inp.h, inp.temp_bar, s_temp, conc, steel, code)

    Vu = sup.shear * wu * L / 2
    shear = check_shear(Vu, d, conc, code)

    notes = []
    if not h_ok:
        notes.append(f"ความหนาน้อยกว่า h,min = {h_min:.1f} cm (ACI 318 Table 9.5a) — ต้องตรวจสอบการแอ่นตัว")
    if not shear.ok:
        notes.append("กำลังรับแรงเฉือนไม่พอ — เพิ่มความหนาพื้น")
    if sup.name == "one_end":
        notes.append("ช่วงริม: +M = wL²/11, -M ที่รองรับภายใน = wL²/10 (มากกว่า 2 ช่วง; กรณี 2 ช่วงใช้ wL²/9), -M ปลายริม = wL²/24")
    return OneWayResult(inp, sw, wd, wu, h_min, h_ok, d, moments, flexure, temp, shear, notes)


__all__ = ["B", "OneWayInput", "OneWayResult", "design_one_way", "ONE_WAY_SUPPORTS"]
