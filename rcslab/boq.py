"""Bill of quantities (concrete, formwork, reinforcement) for one slab panel.

Bar lengths are estimates for take-off, not detailing:
- bottom bars run the full span plus 0.10 m embedment at each end;
- top bars over a support extend 0.3 × span (two-way: 0.3 × short span) into the
  panel plus 0.15 m anchorage beyond the support face;
- cantilever top bars run the overhang plus an equal back-span anchorage.
"""

from dataclasses import dataclass, field
import math

from .flexure import FlexureResult
from .materials import bar_area
from .one_way import ONE_WAY_SUPPORTS, OneWayResult
from .two_way import TwoWayResult

STEEL_DENSITY = 0.785  # kg/m per cm² of bar area (7850 kg/m³)
EMBED = 0.10  # m
ANCHOR = 0.15  # m
TOP_EXT = 0.30  # fraction of span


@dataclass
class BarItem:
    description: str
    bar: str
    spacing: float  # cm
    count: int
    length: float  # m, each

    @property
    def total_length(self) -> float:
        return self.count * self.length

    @property
    def weight(self) -> float:
        return self.total_length * bar_area(self.bar) * STEEL_DENSITY


@dataclass
class BOQ:
    area: float  # m²
    h: float  # cm
    waste: float  # fraction for laps & waste
    items: list[BarItem] = field(default_factory=list)

    @property
    def concrete(self) -> float:
        return self.area * self.h / 100

    @property
    def formwork(self) -> float:
        return self.area

    @property
    def steel_net(self) -> float:
        return sum(i.weight for i in self.items)

    @property
    def steel_total(self) -> float:
        return self.steel_net * (1 + self.waste)

    def by_bar(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for i in self.items:
            out[i.bar] = out.get(i.bar, 0.0) + i.weight * (1 + self.waste)
        return out

    @property
    def steel_ratio(self) -> float:
        """kg of steel per m³ of concrete."""
        return self.steel_total / self.concrete if self.concrete else 0.0


def count_bars(width_m: float, spacing_cm: float) -> int:
    return math.floor(width_m * 100 / spacing_cm + 1e-9) + 1


def _item(desc: str, f: FlexureResult, run_width: float, length: float, sides: int = 1) -> BarItem:
    return BarItem(desc, f.bar, f.spacing, sides * count_bars(run_width, f.spacing), length)


def one_way_boq(res: OneWayResult, width: float, waste: float = 0.05) -> BOQ:
    """width: panel dimension perpendicular to the span (m)."""
    L = res.inp.span
    sup = ONE_WAY_SUPPORTS[res.inp.support]
    boq = BOQ(area=L * width, h=res.inp.h, waste=waste)
    by_label = {f.label: f for f in res.flexure}
    temp = res.temp
    if sup.name == "cantilever":
        boq.items.append(_item("เหล็กบน (หลัก) พื้นยื่น", by_label["-M ที่ยึดแน่น"], width, 2 * L))
        boq.items.append(_item("เหล็กกันร้าวบน (ใต้เหล็กหลัก)", temp, 2 * L, width))
        boq.items.append(_item("เหล็กล่างทิศทางสั้น (กันร้าว)", temp, width, L + EMBED))
        boq.items.append(_item("เหล็กล่างทิศทางยาว (กันร้าว)", temp, L, width))
        return boq
    ext = TOP_EXT * L + ANCHOR
    boq.items.append(_item("เหล็กล่าง (หลัก)", by_label["+M กลางช่วง"], width, L + 2 * EMBED))
    boq.items.append(_item("เหล็กล่างทิศทางยาว (กันร้าว)", temp, L, width))
    for label, sides in (("-M ที่รองรับต่อเนื่อง", sup.n_cont), ("-M ที่รองรับไม่ต่อเนื่อง", sup.n_disc)):
        if label in by_label and sides:
            where = label[3:] + (f" ({sides} ด้าน)" if sides > 1 else "")
            boq.items.append(_item(f"เหล็กบน {where}", by_label[label], width, ext, sides))
            boq.items.append(_item(f"เหล็กกันร้าวบน {where}", temp, TOP_EXT * L, width, sides))
    return boq


def two_way_boq(res: TwoWayResult, waste: float = 0.05) -> BOQ:
    inp = res.inp
    X, Y = inp.short_span, inp.long_span  # panel dimensions as entered (X, Y)
    swapped = X > Y
    fx = res.flexure_long if swapped else res.flexure_short  # bars running in X
    fy = res.flexure_short if swapped else res.flexure_long  # bars running in Y

    def pick(flex: list[FlexureResult], kind: str) -> FlexureResult:
        return next(f for f in flex if kind in f.label)

    ext = TOP_EXT * res.S + ANCHOR
    boq = BOQ(area=X * Y, h=inp.h, waste=waste)
    boq.items.append(_item("เหล็กล่าง แนว X", pick(fx, "+M"), Y, X + 2 * EMBED))
    boq.items.append(_item("เหล็กล่าง แนว Y", pick(fy, "+M"), X, Y + 2 * EMBED))
    # edges 1, 2 (length Y) carry X-direction top bars; edges 3, 4 (length X) carry Y bars
    for name, cont, flex, edge_len in (
        ("ขอบ 1", inp.long_edge_1, fx, Y),
        ("ขอบ 2", inp.long_edge_2, fx, Y),
        ("ขอบ 3", inp.short_edge_1, fy, X),
        ("ขอบ 4", inp.short_edge_2, fy, X),
    ):
        f = pick(flex, "ขอบต่อเนื่อง" if cont else "ขอบไม่ต่อเนื่อง")
        boq.items.append(_item(f"เหล็กบน {name} ({'ต่อเนื่อง' if cont else 'ไม่ต่อเนื่อง'})", f, edge_len, ext))
    return boq
