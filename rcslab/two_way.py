"""Two-way slab design — ACI 318-63 Method 2 (moment coefficient method).

This is the method used in common Thai practice (EIT). Moments in the middle
strip: M = C · wu · S², with S the short span. Column-strip moments may be
taken as 2/3 of the middle-strip values.
"""

from dataclasses import dataclass, field

import numpy as np

from .flexure import FlexureResult, ShearResult, check_shear, design_flexure
from .materials import Concrete, DesignCode, Steel, bar_dia

M_RATIOS = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]

# case -> {"neg_cont", "neg_disc", "pos"} -> short-span coefficients at M_RATIOS.
# Long-span coefficients equal the m = 1.0 value for every m.
TWO_WAY_CASES: dict[int, dict[str, list[float] | None]] = {
    1: {  # interior panel
        "neg_cont": [0.033, 0.040, 0.048, 0.055, 0.063, 0.083],
        "neg_disc": None,
        "pos": [0.025, 0.030, 0.036, 0.041, 0.047, 0.062],
    },
    2: {  # one edge discontinuous
        "neg_cont": [0.041, 0.048, 0.055, 0.062, 0.069, 0.085],
        "neg_disc": [0.021, 0.024, 0.027, 0.031, 0.035, 0.042],
        "pos": [0.031, 0.036, 0.041, 0.047, 0.052, 0.064],
    },
    3: {  # two edges discontinuous
        "neg_cont": [0.049, 0.057, 0.064, 0.071, 0.078, 0.090],
        "neg_disc": [0.025, 0.028, 0.032, 0.036, 0.039, 0.045],
        "pos": [0.037, 0.043, 0.048, 0.054, 0.059, 0.068],
    },
    4: {  # three edges discontinuous
        "neg_cont": [0.058, 0.066, 0.074, 0.082, 0.090, 0.098],
        "neg_disc": [0.029, 0.033, 0.037, 0.041, 0.045, 0.049],
        "pos": [0.044, 0.050, 0.056, 0.062, 0.068, 0.074],
    },
    5: {  # four edges discontinuous
        "neg_cont": None,
        "neg_disc": [0.033, 0.038, 0.043, 0.047, 0.053, 0.055],
        "pos": [0.050, 0.057, 0.064, 0.072, 0.080, 0.083],
    },
}

CASE_NAMES = {
    1: "Case 1 — แผ่นพื้นภายใน (ต่อเนื่องทั้ง 4 ด้าน)",
    2: "Case 2 — ไม่ต่อเนื่อง 1 ด้าน",
    3: "Case 3 — ไม่ต่อเนื่อง 2 ด้าน",
    4: "Case 4 — ไม่ต่อเนื่อง 3 ด้าน",
    5: "Case 5 — ไม่ต่อเนื่องทั้ง 4 ด้าน",
}


def coefficient(case: int, kind: str, m: float, direction: str) -> float:
    """Method 2 coefficient. direction is 'short' or 'long'."""
    values = TWO_WAY_CASES[case][kind]
    if values is None:
        return 0.0
    if direction == "long":
        return values[0]
    m = min(max(m, 0.5), 1.0)
    # np.interp needs ascending x
    return float(np.interp(m, M_RATIOS[::-1], values[::-1]))


@dataclass
class TwoWayInput:
    short_span: float  # m, S
    long_span: float  # m, L
    h: float  # cm
    sdl: float  # kg/m²
    ll: float  # kg/m²
    # continuity of each edge (True = continuous)
    long_edge_1: bool = True  # edges of length L (supports for short-span moment)
    long_edge_2: bool = True
    short_edge_1: bool = True  # edges of length S (supports for long-span moment)
    short_edge_2: bool = True
    cover: float = 2.0
    bar: str = "DB12"

    @property
    def case(self) -> int:
        discontinuous = 4 - sum([self.long_edge_1, self.long_edge_2, self.short_edge_1, self.short_edge_2])
        return discontinuous + 1


@dataclass
class TwoWayResult:
    inp: TwoWayInput
    S: float
    L: float
    m: float
    case: int
    sw: float
    wd: float
    wu: float
    h_min: float
    h_ok: bool
    d_short: float
    d_long: float
    coefs: dict[str, float]
    moments: dict[str, float]
    flexure_short: list[FlexureResult]
    flexure_long: list[FlexureResult]
    shear: ShearResult
    beam_load_short_edge: float  # kg/m on beams along the short edges
    beam_load_long_edge: float  # kg/m on beams along the long edges
    notes: list[str] = field(default_factory=list)

    @property
    def is_two_way(self) -> bool:
        return self.m >= 0.5

    @property
    def ok(self) -> bool:
        return (
            self.is_two_way
            and self.h_ok
            and self.shear.ok
            and all(f.ok for f in self.flexure_short + self.flexure_long)
        )


def design_two_way(inp: TwoWayInput, conc: Concrete, steel: Steel, code: DesignCode) -> TwoWayResult:
    # Normalise so S is always the short span; swap edge flags with it.
    if inp.short_span <= inp.long_span:
        S, L = inp.short_span, inp.long_span
        long_edges = (inp.long_edge_1, inp.long_edge_2)
        short_edges = (inp.short_edge_1, inp.short_edge_2)
    else:
        S, L = inp.long_span, inp.short_span
        long_edges = (inp.short_edge_1, inp.short_edge_2)
        short_edges = (inp.long_edge_1, inp.long_edge_2)
    m = S / L
    case = inp.case

    sw = conc.unit_weight * inp.h / 100
    wd = sw + inp.sdl
    wu = code.dl_factor * wd + code.ll_factor * inp.ll

    h_min = max(2 * (S + L) * 100 / 180, 9.0)
    h_ok = inp.h >= h_min - 1e-9

    db = bar_dia(inp.bar)
    d_short = inp.h - inp.cover - db / 2
    d_long = d_short - db
    s_max = min(3 * inp.h, 45.0)

    coefs: dict[str, float] = {}
    moments: dict[str, float] = {}

    def add(key: str, kind: str, direction: str) -> None:
        c = coefficient(case, kind, m, direction)
        coefs[key] = c
        moments[key] = c * wu * S**2

    # Short span (moments at the long edges)
    add("S: +M กลางช่วง", "pos", "short")
    if any(long_edges):
        add("S: -M ขอบต่อเนื่อง", "neg_cont", "short")
    if not all(long_edges):
        add("S: -M ขอบไม่ต่อเนื่อง", "neg_disc", "short")
    # Long span (moments at the short edges)
    add("L: +M กลางช่วง", "pos", "long")
    if any(short_edges):
        add("L: -M ขอบต่อเนื่อง", "neg_cont", "long")
    if not all(short_edges):
        add("L: -M ขอบไม่ต่อเนื่อง", "neg_disc", "long")

    flex_short, flex_long = [], []
    for key, Mu in moments.items():
        if key.startswith("S:"):
            flex_short.append(design_flexure(key, Mu, d_short, inp.h, inp.bar, s_max, conc, steel, code))
        else:
            flex_long.append(design_flexure(key, Mu, d_long, inp.h, inp.bar, s_max, conc, steel, code))

    beam_short = wu * S / 3
    beam_long = wu * S / 3 * (3 - m**2) / 2
    shear = check_shear(max(beam_short, beam_long), d_short, conc, code)

    notes = []
    if m < 0.5:
        notes.append(f"m = S/L = {m:.2f} < 0.5 — ควรออกแบบเป็นพื้นทางเดียว (One-way slab)")
    if not h_ok:
        notes.append(f"ความหนาน้อยกว่า h,min = {h_min:.1f} cm (เส้นรอบรูป/180, ≥ 9 cm)")
    if not shear.ok:
        notes.append("กำลังรับแรงเฉือนไม่พอ — เพิ่มความหนาพื้น")
    notes.append("ค่าที่ได้เป็นของแถบกลาง (Middle strip); แถบเสา (Column strip) ใช้ 2/3 ของค่าแถบกลางได้")
    notes.append(
        "ถ้าโมเมนต์ลบสองข้างของคานไม่เท่ากัน ให้ใช้ค่าที่มากกว่า หรือกระจายโมเมนต์ส่วนต่างตามสติฟเนส"
    )

    return TwoWayResult(
        inp=inp,
        S=S,
        L=L,
        m=m,
        case=case,
        sw=sw,
        wd=wd,
        wu=wu,
        h_min=h_min,
        h_ok=h_ok,
        d_short=d_short,
        d_long=d_long,
        coefs=coefs,
        moments=moments,
        flexure_short=flex_short,
        flexure_long=flex_long,
        shear=shear,
        beam_load_short_edge=beam_short,
        beam_load_long_edge=beam_long,
        notes=notes,
    )
