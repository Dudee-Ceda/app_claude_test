"""Bill of quantities (concrete, formwork, reinforcement) for one slab panel.

Bar lengths follow the schedule detailing (rcslab.detailing) and are estimates for take-off:
- bottom bars run the full span plus 0.10 m embedment at each end;
- top bars run L1 (edge) or L2 (continuous support) from the support face plus 0.15 m anchorage;
- Types B, D, F add a full-length top mesh; cantilever top bars anchor one overhang length back.
"""

from dataclasses import dataclass, field
import math

from .detailing import MESH_TYPES, Position, SlabDetail, detail_one_way, detail_two_way
from .flexure import FlexureResult
from .materials import bar_area
from .one_way import ONE_WAY_SUPPORTS, OneWayResult
from .two_way import TwoWayResult

STEEL_DENSITY = 0.785  # kg/m per cm² of bar area (7850 kg/m³)
EMBED = 0.10  # m
ANCHOR = 0.15  # m


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


def _item(desc: str, f: FlexureResult | Position, run_width: float, length: float, sides: int = 1) -> BarItem:
    return BarItem(desc, f.bar, f.spacing, sides * count_bars(run_width, f.spacing), length)


def one_way_boq(
    res: OneWayResult, width: float, waste: float = 0.05, slab_type: str = "", support_width: float = 0.30
) -> BOQ:
    """width: panel dimension perpendicular to the span (m)."""
    L = res.inp.span
    sup = ONE_WAY_SUPPORTS[res.inp.support]
    det = detail_one_way(res, width, slab_type, support_width)
    boq = BOQ(area=L * width, h=res.inp.h, waste=waste)
    temp = res.temp
    if sup.name == "cantilever":
        boq.items.append(_item("เหล็กบนตลอดความยาว (Top 5)", det.cant_basic, width, 2 * L))
        if det.cant_extra:
            boq.items.append(_item("เหล็กบนเสริมพิเศษ (Top 3)", det.cant_extra, width, det.l2_cross + L))
        boq.items.append(_item("เหล็กบนตั้งฉาก (Top 6)", temp, 2 * L, width))
        boq.items.append(_item("เหล็กล่างทิศทางยื่น (Bottom 1)", temp, width, L + EMBED))
        boq.items.append(_item("เหล็กล่างตั้งฉาก (Bottom 2)", temp, L, width))
        return boq
    c = det.cross
    boq.items.append(_item("เหล็กล่างทิศทางหลัก (Bottom 1)", c["b"], width, L + 2 * EMBED))
    boq.items.append(_item("เหล็กล่างทิศทางรอง (Bottom 2)", temp, L, width))
    mesh = det.slab_type in MESH_TYPES
    for key, cut, sides, name in (
        ("t_disc", det.l1_cross, sup.n_disc, "ขอบไม่ต่อเนื่อง (Top 1)"),
        ("t_cont", det.l2_cross, sup.n_cont, "ที่รองรับต่อเนื่อง (Top 3)"),
    ):
        if c[key] and sides:
            where = name + (f" × {sides} ด้าน" if sides > 1 else "")
            boq.items.append(_item(f"เหล็กบน {where}", c[key], width, cut + ANCHOR, sides))
            if not mesh:
                boq.items.append(_item(f"เหล็กบนตั้งฉาก {where}", temp, cut, width, sides))
    if mesh:
        boq.items.append(_item("เหล็กบนตลอดช่วง ทิศทางหลัก (Top 5)", temp, width, L + 2 * EMBED))
        boq.items.append(_item("เหล็กบนตลอดช่วง ทิศทางรอง (Top 6)", temp, L, width))
    return boq


def two_way_boq(res: TwoWayResult, waste: float = 0.05, slab_type: str = "A", support_width: float = 0.30) -> BOQ:
    inp = res.inp
    X, Y = inp.short_span, inp.long_span  # panel dimensions as entered (X, Y)
    det = detail_two_way(res, slab_type, support_width)
    swapped = X > Y  # then X is the long direction
    dx, dy = (det.long, det.cross) if swapped else (det.cross, det.long)
    cut_x = (det.l1_long, det.l2_long) if swapped else (det.l1_cross, det.l2_cross)
    cut_y = (det.l1_cross, det.l2_cross) if swapped else (det.l1_long, det.l2_long)
    boq = BOQ(area=X * Y, h=inp.h, waste=waste)
    boq.items.append(_item("เหล็กล่าง แนว X", dx["b"], Y, X + 2 * EMBED))
    boq.items.append(_item("เหล็กล่าง แนว Y", dy["b"], X, Y + 2 * EMBED))
    # edges 1, 2 (length Y) carry X-direction top bars; edges 3, 4 (length X) carry Y bars
    for name, cont, bars, cuts, edge_len in (
        ("ขอบ 1", inp.long_edge_1, dx, cut_x, Y),
        ("ขอบ 2", inp.long_edge_2, dx, cut_x, Y),
        ("ขอบ 3", inp.short_edge_1, dy, cut_y, X),
        ("ขอบ 4", inp.short_edge_2, dy, cut_y, X),
    ):
        pos = bars["t_cont"] if cont else bars["t_disc"]
        cut = cuts[1] if cont else cuts[0]
        label = "ต่อเนื่อง, Top 3" if cont else "ไม่ต่อเนื่อง, Top 1"
        boq.items.append(_item(f"เหล็กบน {name} ({label})", pos, edge_len, cut + ANCHOR))
    if det.slab_type in MESH_TYPES:
        boq.items.append(_item("เหล็กบนตลอดช่วง แนว X (Top 5/6)", res.temp, Y, X + 2 * EMBED))
        boq.items.append(_item("เหล็กบนตลอดช่วง แนว Y (Top 5/6)", res.temp, X, Y + 2 * EMBED))
    return boq
