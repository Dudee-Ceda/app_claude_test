"""Slab reinforcement schedule in the office drawing layout (S-08-5-xx: SLAB / SLAB TYPE / SECTION ...)."""

from dataclasses import asdict

from .detailing import NA, SlabDetail
from .materials import BARS

COLUMNS = {
    "mark": "SLAB",
    "slab_type": "SLAB TYPE",
    "section": "SECTION",
    "span": "SPAN (mm)",
    "t": "T (mm)",
    "l1": "L1 (mm)",
    "l2": "L2 (mm)",
    "camber": "CAMBER (mm)",
    "b1": "Bottom Reinforcement 1",
    "b2": "Bottom Reinforcement 2",
    "t1": "Top Reinforcement 1",
    "t2": "Top Reinforcement 2",
    "t3": "Top Reinforcement 3",
    "t4": "Top Reinforcement 4",
    "t5": "Top Reinforcement 5",
    "t6": "Top Reinforcement 6",
}
# relative PDF column widths, in COLUMNS order
PDF_COL_WIDTHS = (9, 8, 11, 9, 7, 8, 8, 11, 15, 15, 15, 15, 15, 15, 15, 15)

# development length Ld in bar diameters, per the type details (SD30 taken as SD40)
LD_FACTOR = {"SR24": 40, "SD30": 36, "SD40": 36, "SD50": 45}


def drawing_callout(bar: str, spacing_cm: float) -> str:
    """Compact callout, e.g. DB12@0.20, RB9@0.225 (used in the report text)."""
    s = f"{spacing_cm / 100:.3f}".rstrip("0")
    if len(s.split(".")[1]) < 2:
        s += "0"
    return f"{bar}@{s}"


def schedule_records(mark: str, detail: SlabDetail) -> list[dict]:
    """Two records (CROSS, LONG) for one slab, keyed like COLUMNS."""
    return [{"mark": mark, "slab_type": detail.slab_type} | asdict(row) for row in detail.rows()]


def lap_length(bar: str) -> float:
    """Tension lap length in m: 40db for DB, 48db + hooks for RB."""
    db = BARS[bar][0]
    factor = 48 if bar.startswith("RB") else 40
    return max(0.30, factor * db / 100)


def schedule_notes(fc: float, grade: str, cover: float, bars: list[str]) -> list[str]:
    used = sorted(set(bars), key=lambda b: BARS[b][0])
    ld = LD_FACTOR.get(grade, 36)
    lds = ", ".join(f"{b} ≥ {max(0.30, ld * BARS[b][0] / 100):.2f} m" for b in used)
    laps = ", ".join(f"{b} ≥ {lap_length(b):.2f} m" for b in used)
    return [
        f"คอนกรีต f'c = {fc:.0f} ksc (ทรงกระบอก), เหล็กเสริม {grade}, ระยะหุ้มคอนกรีต {cover * 10:.0f} mm",
        "ตำแหน่งเหล็กและรูปตัดตามแบบมาตรฐาน RC SLAB TYPE A–L (S-08-1-01 ถึง S-08-1-05)",
        "CROSS = รูปตัดทิศทางสั้น (ทิศทางหลักของพื้นทางเดียว), LONG = รูปตัดทิศทางยาว",
        "L1, L2 วัดจากผิวที่รองรับ: L1 = Ln/4 ที่ขอบไม่ต่อเนื่อง, L2 = Ln/3 ข้างละที่รองรับต่อเนื่อง (ปัดขึ้น 100 mm); "
        "พื้นยื่น L2 = ระยะตัดเหล็กเสริมพิเศษ Top 3",
        "ระยะห่างเหล็กทุกตำแหน่งในแผ่นเดียวกันหารลงตัวกับระยะ Module (300, 250 หรือ 200 mm) "
        "เหล็กทุกชุดจึงตรงแนวกันทุกระยะ Module และเหล็กเสริมพิเศษแทรกกึ่งกลางได้พอดี",
        f"ระยะฝังยึดเต็มที่ (Fully developed) Ld ≥ {ld}d สำหรับ {grade}: {lds}",
        f"ระยะทาบเหล็ก: {laps} (RB ต้องงอขอ)",
        "พื้นแต่ละแผ่นใช้เหล็กขนาดเดียวกันทั้งแผ่น ระยะห่างไม่เกิน 300 mm",
        "ค่าเหล็กเป็นของแถบกลาง (Middle strip); แถบเสาของพื้นสองทางใช้ระยะห่าง 1.5 เท่าได้ แต่ไม่เกิน 300 mm",
        f"ช่อง {NA} = ไม่มีเหล็กตำแหน่งนี้ (ช่องขีดฆ่าในแบบ)",
    ]
