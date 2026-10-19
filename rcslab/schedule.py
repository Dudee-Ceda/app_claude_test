"""Slab reinforcement schedule (ตารางเหล็กพื้น) in the layout used on Thai structural drawings."""

from dataclasses import asdict, dataclass

from .materials import BARS
from .one_way import ONE_WAY_SUPPORTS, OneWayResult
from .two_way import TwoWayResult

NONE = "—"

COLUMNS = {
    "mark": "พื้น",
    "kind": "ประเภท",
    "t": "หนา (m)",
    "size": "ขนาด (m)",
    "load": "SDL / LL (kg/m²)",
    "short_bot": "ทิศทางสั้น: ล่าง",
    "short_top_cont": "ทิศทางสั้น: บน ขอบต่อเนื่อง",
    "short_top_disc": "ทิศทางสั้น: บน ขอบไม่ต่อเนื่อง",
    "long_bot": "ทิศทางยาว: ล่าง",
    "long_top_cont": "ทิศทางยาว: บน ขอบต่อเนื่อง",
    "long_top_disc": "ทิศทางยาว: บน ขอบไม่ต่อเนื่อง",
    "remark": "หมายเหตุ",
}


@dataclass
class ScheduleRow:
    mark: str
    kind: str
    t: str
    size: str
    load: str
    short_bot: str
    short_top_cont: str
    short_top_disc: str
    long_bot: str
    long_top_cont: str
    long_top_disc: str
    remark: str
    ok: bool = True

    def as_dict(self) -> dict:
        return asdict(self)


# relative PDF column widths, in COLUMNS order
PDF_COL_WIDTHS = (8, 13, 9, 19, 15, 20, 20, 20, 20, 20, 20, 44)


def drawing_callout(bar: str, spacing_cm: float) -> str:
    """Compact callout as written on drawings, e.g. DB12@0.20, RB9@0.225."""
    s = f"{spacing_cm / 100:.3f}".rstrip("0")
    if len(s.split(".")[1]) < 2:
        s += "0"
    return f"{bar}@{s}"


def _callout(flex, kind: str) -> str:
    f = next((f for f in flex if kind in f.label), None)
    return drawing_callout(f.bar, f.spacing) if f else NONE


def one_way_row(mark: str, res: OneWayResult, width: float) -> ScheduleRow:
    inp = res.inp
    name = ONE_WAY_SUPPORTS[inp.support].name
    temp = drawing_callout(res.temp.bar, res.temp.spacing)
    if name == "cantilever":
        return ScheduleRow(
            mark, "พื้นยื่น", f"{inp.h / 100:.2f}", f"ยื่น {inp.span:.2f} × {width:.2f}", f"{inp.sdl:.0f} / {inp.ll:.0f}",
            temp, _callout(res.flexure, "-M ที่ยึดแน่น"), NONE,
            temp, temp, NONE,
            "เหล็กหลักอยู่บน ยึดฝังเข้าช่วงในยาวเท่าระยะยื่น; เหล็กล่างเป็นเหล็กกันร้าว"
            + (f"; P ปลาย {inp.p_end:.0f} kg/m" if inp.p_end else ""),
            res.ok,
        )
    remark = {
        "simple": "ช่วงเดียว",
        "one_end": "ต่อเนื่องปลายเดียว",
        "one_end_2": "ต่อเนื่องปลายเดียว (2 ช่วง)",
        "both_ends": "ต่อเนื่องสองปลาย",
    }[name]
    top_cont = _callout(res.flexure, "-M ที่รองรับต่อเนื่อง")
    top_disc = _callout(res.flexure, "-M ที่รองรับไม่ต่อเนื่อง")
    return ScheduleRow(
        mark, "ทางเดียว", f"{inp.h / 100:.2f}", f"{inp.span:.2f} × {width:.2f}", f"{inp.sdl:.0f} / {inp.ll:.0f}",
        _callout(res.flexure, "+M"), top_cont, top_disc,
        temp, temp if top_cont != NONE else NONE, temp if top_disc != NONE else NONE,
        remark + "; ทิศทางยาว = เหล็กกันร้าว (บนวางใต้เหล็กบนทิศทางสั้น)", res.ok,
    )


def two_way_row(mark: str, res: TwoWayResult) -> ScheduleRow:
    inp = res.inp
    return ScheduleRow(
        mark, "สองทาง", f"{inp.h / 100:.2f}", f"{res.S:.2f} × {res.L:.2f}", f"{inp.sdl:.0f} / {inp.ll:.0f}",
        _callout(res.flexure_short, "+M"), _callout(res.flexure_short, "ขอบต่อเนื่อง"),
        _callout(res.flexure_short, "ขอบไม่ต่อเนื่อง"),
        _callout(res.flexure_long, "+M"), _callout(res.flexure_long, "ขอบต่อเนื่อง"),
        _callout(res.flexure_long, "ขอบไม่ต่อเนื่อง"),
        f"Case {res.case}, m = {res.m:.2f}; เหล็กทิศทางยาววางชั้นใน", res.ok,
    )


def lap_length(bar: str) -> float:
    """Tension lap length in m used on the schedule notes: 40db for DB, 48db + hooks for RB."""
    db = BARS[bar][0]
    factor = 48 if bar.startswith("RB") else 40
    return max(0.30, factor * db / 100)


def schedule_notes(fc: float, grade: str, cover: float, bars: list[str]) -> list[str]:
    laps = ", ".join(f"{b} ≥ {lap_length(b):.2f} m" for b in sorted(set(bars), key=lambda b: BARS[b][0]))
    return [
        f"คอนกรีต f'c = {fc:.0f} ksc (ทรงกระบอก), เหล็กเสริม {grade}, ระยะหุ้มคอนกรีต {cover:.1f} cm",
        "เหล็กล่างยาวตลอดช่วง ฝังเข้าคานอย่างน้อย 0.10 m",
        "เหล็กบนยื่นจากขอบคาน 0.30L (L = ช่วงสั้นสำหรับพื้นสองทาง, ช่วงพื้นสำหรับพื้นทางเดียว)",
        "พื้นสองทาง: เหล็กทิศทางสั้นวางชั้นนอก (ล่างสุด/บนสุด) เหล็กทิศทางยาววางชั้นใน",
        f"ระยะทาบเหล็ก: {laps} (RB ต้องงอขอ)",
        "ค่าในตารางเป็นแถบกลาง (Middle strip); แถบเสาของพื้นสองทางใช้ระยะห่าง 1.5 เท่าของแถบกลางได้ แต่ไม่เกิน 0.30 m และต้องไม่น้อยกว่า As,min",
        "พื้นยื่น: เหล็กหลักอยู่บน ยึดฝังเข้าช่วงในยาวไม่น้อยกว่าระยะยื่น",
        "พื้นแต่ละแผ่นใช้เหล็กขนาดเดียวกันทั้งแผ่น ทั้งเหล็กหลักและเหล็กกันร้าว ระยะห่างเหล็กทุกตำแหน่งไม่เกิน 0.30 m",
        "พื้นทางเดียว: เหล็กกันร้าวบนวางตั้งฉากใต้เหล็กบน ตลอดช่วงที่มีเหล็กบน",
        "ช่อง — หมายถึงพื้นแผ่นนั้นไม่มีขอบประเภทนั้น",
    ]
