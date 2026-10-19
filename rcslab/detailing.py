"""Detailing for the office slab schedule (CEDA standard details RC SLAB TYPE A–L, S-08-1-01..05).

Bar positions follow the type details. In each section (CROSS = short/main span, LONG = the
other direction) odd numbers are bars running in the plane of the section and even numbers are
the bars at right angles to them:

    BOTTOM 1 / 2   bottom bars, this direction / other direction
    TOP 1 / 2      top bars at a discontinuous (edge) support, cut at L1 from the support face
    TOP 3 / 4      top bars over a continuous support, cut at L2 each side
    TOP 5 / 6      top bars over the full span (Types B, D, F and cantilevers)

Types: A two-way; B two-way + full top mesh; C, E one-way; D, F one-way + full top mesh;
G–L cantilever (G into a beam, H into a column or wall, I–L with back span).
"""

from dataclasses import dataclass, field
import math

from .flexure import B, FlexureResult, pick_module_spacing
from .materials import bar_area, bar_dia
from .one_way import ONE_WAY_SUPPORTS, OneWayResult
from .two_way import TwoWayResult

NA = "—"  # cell crossed out on the drawing schedule
TWO_WAY_TYPES = ("A", "B")
ONE_WAY_TYPES = ("C", "D", "E", "F")
CANTILEVER_TYPES = ("G", "H", "I", "J", "K", "L")
MESH_TYPES = {"B", "D", "F"}
TYPE_LABELS = {
    "A": "A — พื้นสองทาง เหล็กบนเฉพาะที่รองรับ",
    "B": "B — พื้นสองทาง + เหล็กบนตลอดช่วง",
    "C": "C — พื้นทางเดียว เหล็กบนเฉพาะที่รองรับ",
    "D": "D — พื้นทางเดียว + เหล็กบนตลอดช่วง",
    "E": "E — พื้นทางเดียว (ตามแบบ S-08-1-03)",
    "F": "F — พื้นทางเดียว + เหล็กบนตลอดช่วง (ตามแบบ S-08-1-03)",
    "G": "G — พื้นยื่น ฝังในคาน",
    "H": "H — พื้นยื่น ฝังในเสาหรือผนัง",
    "I": "I — พื้นยื่นมีช่วงใน (ตามแบบ S-08-1-04)",
    "J": "J — พื้นยื่นมีช่วงใน (ตามแบบ S-08-1-04)",
    "K": "K — พื้นยื่นจากผนัง (ตามแบบ S-08-1-04)",
    "L": "L — พื้นยื่นจากผนัง (ตามแบบ S-08-1-05)",
}


def callout(bar: str, spacing_cm: float) -> str:
    """Schedule callout in mm, e.g. DB12 @ 300 mm."""
    return f"{bar} @ {spacing_cm * 10:.0f} mm"


def cut_length(clear_span_m: float, divisor: float) -> float:
    """Top-bar cut-off (m) = Ln / divisor, rounded up to 100 mm."""
    return math.ceil(max(clear_span_m, 0.0) * 1000 / divisor / 100 - 1e-9) * 0.1


def suggested_camber(delta_dead_mm: float | None, short_span_m: float) -> int:
    """Camber (mm): computed dead-load deflection rounded up to 5 mm, at least 10 mm;
    two-way slabs (no deflection computed) use 10 mm, or 20 mm from 8 m short span."""
    if delta_dead_mm is None:
        return 20 if short_span_m >= 8 else 10
    return max(10, math.ceil(delta_dead_mm / 5 - 1e-9) * 5)


@dataclass
class Position:
    """One bar position on the schedule."""

    bar: str
    spacing: float  # cm

    @property
    def text(self) -> str:
        return callout(self.bar, self.spacing)


def _pos(f: FlexureResult | None) -> Position | None:
    return Position(f.bar, f.spacing) if f else None


@dataclass
class SectionRow:
    section: str  # CROSS / LONG
    span: str  # mm or VARIES
    t: str
    l1: str
    l2: str
    camber: str
    b1: str = NA
    b2: str = NA
    t1: str = NA
    t2: str = NA
    t3: str = NA
    t4: str = NA
    t5: str = NA
    t6: str = NA


@dataclass
class SlabDetail:
    """Detailing of one slab: schedule rows plus the numbers the BOQ needs."""

    kind: str  # two_way / one_way / cantilever
    slab_type: str
    h: float  # cm
    module: float  # cm
    camber: int  # mm
    bar: str
    ok: bool
    # bars by direction: keys b (bottom), t_disc, t_cont, mesh; values Position or None
    cross: dict = field(default_factory=dict)
    long: dict = field(default_factory=dict)
    span_cross: float = 0.0  # m
    span_long: float | None = None  # m (None = varies)
    l1_cross: float | None = None  # m
    l2_cross: float | None = None
    l1_long: float | None = None
    l2_long: float | None = None
    cant_extra: Position | None = None  # cantilever TOP 3 (extra bars over the support)
    cant_basic: Position | None = None  # cantilever TOP 5 (full length)
    notes: list[str] = field(default_factory=list)

    def rows(self) -> list[SectionRow]:
        t = f"{self.h * 10:.0f}"
        mm = lambda v: NA if v is None else f"{v * 1000:,.0f}"  # noqa: E731
        txt = lambda p: p.text if p else NA  # noqa: E731
        camber = f"{self.camber}" if self.camber else NA
        if self.kind == "cantilever":
            extra = self.cant_extra
            dist = txt(self.cross["dist"])
            cross = SectionRow(
                "CROSS", mm(self.span_cross), t, NA, mm(self.l2_cross), camber,
                b1=dist, b2=dist, t3=txt(extra), t4=dist if extra else NA,
                t5=txt(self.cant_basic), t6=dist,
            )
            long = SectionRow("LONG", "VARIES" if self.span_long is None else mm(self.span_long), t, NA, NA, NA)
            return [cross, long]
        rows = []
        for name, this, other, span, l1, l2 in (
            ("CROSS", self.cross, self.long, self.span_cross, self.l1_cross, self.l2_cross),
            ("LONG", self.long, self.cross, self.span_long, self.l1_long, self.l2_long),
        ):
            row = SectionRow(
                name, "VARIES" if span is None else mm(span), t, mm(l1), mm(l2), camber,
                b1=txt(this["b"]), b2=txt(other["b"]),
                t1=txt(this["t_disc"]), t3=txt(this["t_cont"]),
            )
            # even positions: the perpendicular bars there (the other direction's own top bars,
            # or distribution bars where that direction has none)
            row.t2 = txt(other["t_disc"] or other["dist"]) if this["t_disc"] else NA
            row.t4 = txt(other["t_cont"] or other["dist"]) if this["t_cont"] else NA
            if self.slab_type in MESH_TYPES:
                row.t5, row.t6 = txt(this["mesh"]), txt(other["mesh"])
            rows.append(row)
        return rows


def _pick(flex: list[FlexureResult], key: str) -> FlexureResult | None:
    return next((f for f in flex if key in f.label), None)


def detail_two_way(res: TwoWayResult, slab_type: str = "A", support_width: float = 0.30) -> SlabDetail:
    slab_type = slab_type if slab_type in TWO_WAY_TYPES else "A"
    temp = _pos(res.temp)
    d = SlabDetail(
        "two_way", slab_type, res.inp.h, res.module, suggested_camber(None, res.S), res.inp.bar, res.ok,
        span_cross=res.S, span_long=res.L,
    )
    for direction, flex, span in (("cross", res.flexure_short, res.S), ("long", res.flexure_long, res.L)):
        bars = {
            "b": _pos(_pick(flex, "+M")),
            "t_disc": _pos(_pick(flex, "ขอบไม่ต่อเนื่อง")),
            "t_cont": _pos(_pick(flex, "ขอบต่อเนื่อง")),
            "mesh": temp,
            "dist": temp,
        }
        setattr(d, direction, bars)
        Ln = span - support_width
        setattr(d, f"l1_{direction}", cut_length(Ln, 4) if bars["t_disc"] else None)
        setattr(d, f"l2_{direction}", cut_length(Ln, 3) if bars["t_cont"] else None)
    return d


def detail_one_way(
    res: OneWayResult, width: float | None, slab_type: str = "", support_width: float = 0.30
) -> SlabDetail:
    inp = res.inp
    name = ONE_WAY_SUPPORTS[inp.support].name
    temp = _pos(res.temp)
    dl = res.deflection
    camber = suggested_camber((1 + dl.lam) * dl.delta_D * 10, inp.span)
    L = inp.span
    if name == "cantilever":
        slab_type = slab_type if slab_type in CANTILEVER_TYPES else "G"
        d = SlabDetail(
            "cantilever", slab_type, inp.h, res.module, camber, inp.main_bar, res.ok,
            span_cross=L, span_long=width,
        )
        d.cross = {"dist": temp}
        main = res.flexure[0]
        # TOP 5 = As,min mesh over the full length; TOP 3 = extra bars over the support for the rest
        basic = res.temp
        d.cant_basic = temp
        need = main.As_design - basic.As_prov
        if need > 1e-9:
            s = pick_module_spacing(need, inp.main_bar, main.s_max, res.module)
            if s is None:  # extra bars cannot fit the module; fall back to the full design spacing
                s = main.spacing
            d.cant_extra = Position(inp.main_bar, s)
            # cut-off: where the basic bars alone carry Mu(a) = wu·a²/2 + Pu·a (a from the free end)
            wu, pu = res.wu, (res.moments[main.label] - res.wu * L**2 / 2) / L
            a = (-pu + math.sqrt(pu**2 + 2 * wu * basic.phiMn)) / wu
            x = max(L - a, 0.0)
            ext = max(main.d, 12 * bar_dia(inp.main_bar)) / 100
            d.l2_cross = min(math.ceil((x + ext) * 10 - 1e-9) / 10, L)
        return d

    slab_type = slab_type if slab_type in ONE_WAY_TYPES else "C"
    d = SlabDetail(
        "one_way", slab_type, inp.h, res.module, camber, inp.main_bar, res.ok,
        span_cross=L, span_long=width,
    )
    d.cross = {
        "b": _pos(_pick(res.flexure, "+M")),
        "t_disc": _pos(_pick(res.flexure, "ไม่ต่อเนื่อง")),
        "t_cont": _pos(_pick(res.flexure, "-M ที่รองรับต่อเนื่อง")),
        "mesh": temp,
        "dist": temp,
    }
    # long direction carries only temperature bars; at the top they sit wherever the main top bars are
    d.long = {
        "b": temp,
        "t_disc": temp if d.cross["t_disc"] else None,
        "t_cont": temp if d.cross["t_cont"] else None,
        "mesh": temp,
        "dist": temp,
    }
    Ln = L - support_width
    d.l1_cross = cut_length(Ln, 4) if d.cross["t_disc"] else None
    d.l2_cross = cut_length(Ln, 3) if d.cross["t_cont"] else None
    return d
