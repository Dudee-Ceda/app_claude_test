"""ออกแบบคานคอนกรีตเสริมเหล็กด้วยวิธีกำลัง (Strength Design Method)

อ้างอิงมาตรฐาน วสท. 011008-21 / ACI 318 ในหน่วย ksc (kg/cm²)
หน่วย: kg, cm
"""
from __future__ import annotations

import math
from dataclasses import dataclass

ES = 2.04e6  # ksc
EPS_CU = 0.003

REBAR_DIAMETERS = {  # ชื่อ: เส้นผ่านศูนย์กลาง (mm)
    "RB6": 6, "RB9": 9, "DB10": 10, "DB12": 12, "DB16": 16,
    "DB20": 20, "DB25": 25, "DB28": 28, "DB32": 32,
}

STEEL_GRADES = {"SR24": 2400, "SD30": 3000, "SD40": 4000, "SD50": 5000}

LOAD_COMBOS = {
    "1.4D + 1.7L (วสท./ACI 318-99)": (1.4, 1.7, 0.90, 0.85),
    "1.2D + 1.6L (ACI 318-19)": (1.2, 1.6, 0.90, 0.75),
}


def bar_area(name: str) -> float:
    d = REBAR_DIAMETERS[name] / 10.0
    return math.pi * d * d / 4.0


def bar_dia_cm(name: str) -> float:
    return REBAR_DIAMETERS[name] / 10.0


def beta1(fc: float) -> float:
    if fc <= 280:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (fc - 280) / 70)


def ec(fc: float) -> float:
    return 15100 * math.sqrt(fc)


def rho_balanced(fc: float, fy: float) -> float:
    return 0.85 * beta1(fc) * fc / fy * (EPS_CU * ES) / (EPS_CU * ES + fy)


def rho_at_strain(fc: float, fy: float, eps_t: float) -> float:
    """อัตราส่วนเหล็กที่ทำให้ความเครียดเหล็กรับแรงดึงเท่ากับ eps_t"""
    return 0.85 * beta1(fc) * fc / fy * EPS_CU / (EPS_CU + eps_t)


def rho_max(fc: float, fy: float) -> float:
    """ρmax = min(0.75ρb, ρ ที่ εt = 0.004)"""
    return min(0.75 * rho_balanced(fc, fy), rho_at_strain(fc, fy, 0.004))


def rho_min(fc: float, fy: float) -> float:
    return max(0.8 * math.sqrt(fc) / fy, 14.0 / fy)


@dataclass
class Section:
    b: float  # cm
    h: float  # cm
    cover: float  # cm ระยะหุ้ม (ถึงผิวเหล็กปลอก)
    stirrup: str
    fc: float
    fy: float
    fyt: float

    def bars_per_layer(self, bar: str, clear: float = 2.5) -> int:
        db = bar_dia_cm(bar)
        s = max(clear, db)
        width = self.b - 2 * self.cover - 2 * bar_dia_cm(self.stirrup)
        return max(2, int((width + s) // (db + s)))

    def depth_to_steel(self, bar: str, layers: int, clear: float = 2.5) -> float:
        """ระยะจากผิวคอนกรีตถึงศูนย์ถ่วงเหล็ก (สมมติจำนวนเหล็กแต่ละชั้นเท่ากัน)"""
        db = bar_dia_cm(bar)
        first = self.cover + bar_dia_cm(self.stirrup) + db / 2
        if layers == 1:
            return first
        return first + (db + max(clear, db)) / 2


@dataclass
class FlexureResult:
    Mu: float  # kg-cm
    bar: str
    d: float
    d_comp: float
    As_req: float
    As_comp_req: float
    n_tension: int
    n_comp: int
    layers: int
    As_prov: float
    As_comp_prov: float
    phiMn: float
    eps_t: float
    doubly: bool
    rho: float
    rho_min: float
    rho_max: float
    ok: bool
    notes: list


def _phi_mn(sec: Section, As: float, Asc: float, d: float, dc: float, phi: float):
    """กำลังรับโมเมนต์ของหน้าตัดจากเหล็กที่ใส่จริง (หา c จากสมดุลแรง)"""
    fc, fy, b = sec.fc, sec.fy, sec.b
    b1 = beta1(fc)

    def fs_c(c):
        return max(-fy, min(fy, EPS_CU * ES * (c - dc) / c))

    def fs_t(c):
        return max(-fy, min(fy, EPS_CU * ES * (d - c) / c))

    def residual(c):
        a = b1 * c
        Cc = 0.85 * fc * a * b
        Cs = Asc * (fs_c(c) - (0.85 * fc if c * b1 > dc else 0.0))
        return Cc + Cs - As * fs_t(c)

    lo, hi = 1e-6, sec.h
    for _ in range(200):
        mid = (lo + hi) / 2
        if residual(mid) > 0:
            hi = mid
        else:
            lo = mid
    c = (lo + hi) / 2
    a = b1 * c
    Cc = 0.85 * fc * a * b
    Cs = Asc * (fs_c(c) - (0.85 * fc if a > dc else 0.0))
    Mn = Cc * (d - a / 2) + Cs * (d - dc)
    eps_t = EPS_CU * (d - c) / c
    return phi * Mn, eps_t, c


def design_flexure(sec: Section, Mu: float, bar: str, comp_bar: str, phi: float = 0.90) -> FlexureResult:
    """ออกแบบเหล็กรับแรงดึง (และแรงอัดถ้าจำเป็น) สำหรับโมเมนต์ Mu (ค่าบวก, kg-cm)"""
    Mu = abs(Mu)
    fc, fy, b = sec.fc, sec.fy, sec.b
    notes = []
    Ab = bar_area(bar)
    rmin = rho_min(fc, fy)
    rmax = rho_max(fc, fy)
    dc = sec.depth_to_steel(comp_bar, 1)
    nmax = sec.bars_per_layer(bar)

    for layers in (1, 2):
        d = sec.h - sec.depth_to_steel(bar, layers)
        Rn = Mu / (phi * b * d * d) if Mu > 0 else 0.0
        disc = 1 - 2 * Rn / (0.85 * fc)
        rho = 0.85 * fc / fy * (1 - math.sqrt(disc)) if disc >= 0 else float("inf")
        As_comp = 0.0
        doubly = False
        if rho <= rmax:
            As = max(rho, rmin) * b * d if Mu > 0 else 0.0
        else:
            doubly = True
            # ส่วนเหล็กรับแรงดึงชุดแรกออกแบบให้ควบคุมด้วยแรงดึง (εt = 0.005)
            As1 = rho_at_strain(fc, fy, 0.005) * b * d
            a1 = As1 * fy / (0.85 * fc * b)
            Mn1 = As1 * fy * (d - a1 / 2)
            Mn2 = Mu / phi - Mn1
            c1 = a1 / beta1(fc)
            fs_comp = min(fy, EPS_CU * ES * (c1 - dc) / c1)
            if fs_comp <= 0:
                fs_comp = 1e-9
                notes.append("ความลึกคานน้อยเกินไปสำหรับเหล็กรับแรงอัด")
            As_comp = Mn2 / ((fs_comp - 0.85 * fc) * (d - dc)) if fs_comp > 0.85 * fc else float("inf")
            As = As1 + Mn2 / (fy * (d - dc))
        n = max(2, math.ceil(As / Ab - 1e-9))
        if n <= nmax or layers == 2:
            break

    if n > 2 * nmax:
        notes.append(f"เหล็ก {n} เส้นเกินกว่าจะวาง 2 ชั้นได้ (สูงสุดชั้นละ {nmax} เส้น) — ควรเพิ่มขนาดหน้าตัดหรือใช้เหล็กใหญ่ขึ้น")
    n_comp = max(2, math.ceil(As_comp / bar_area(comp_bar) - 1e-9)) if math.isfinite(As_comp) else 99
    As_prov = n * Ab
    Asc_prov = n_comp * bar_area(comp_bar)

    phiMn, eps_t, _ = _phi_mn(sec, As_prov, Asc_prov, d, dc, phi)
    rho_prov = As_prov / (b * d)
    ok = phiMn >= Mu and math.isfinite(As_comp) and n <= 2 * nmax
    if eps_t < 0.004:
        notes.append(f"ความเครียดเหล็กรับแรงดึง εt = {eps_t:.4f} < 0.004 (หน้าตัดไม่เหนียวพอ)")
        ok = False
    if doubly:
        notes.append("โมเมนต์เกินกำลังของหน้าตัดเสริมเหล็กรับแรงดึงอย่างเดียว → ออกแบบเป็นคานเสริมเหล็กสองชั้น (Doubly Reinforced)")

    return FlexureResult(
        Mu=Mu, bar=bar, d=d, d_comp=dc, As_req=As, As_comp_req=As_comp,
        n_tension=n, n_comp=n_comp, layers=1 if n <= nmax else 2,
        As_prov=As_prov, As_comp_prov=Asc_prov, phiMn=phiMn, eps_t=eps_t,
        doubly=doubly, rho=rho_prov, rho_min=rmin, rho_max=rmax, ok=ok, notes=notes,
    )


@dataclass
class ShearResult:
    Vu: float
    phiVc: float
    Vs_req: float
    Av: float
    s_req: float
    s_max: float
    s_use: float
    phiVn: float
    zone: str
    ok: bool
    notes: list


def design_shear(sec: Section, Vu: float, d: float, phi: float = 0.85, legs: int = 2) -> ShearResult:
    fc, b, fyt = sec.fc, sec.b, sec.fyt
    Vu = abs(Vu)
    notes = []
    Vc = 0.53 * math.sqrt(fc) * b * d
    phiVc = phi * Vc
    Av = legs * bar_area(sec.stirrup)
    s_min_steel = Av * fyt / (3.5 * b)  # ระยะห่างสูงสุดจากเหล็กปลอกขั้นต่ำ
    Vs = max(0.0, Vu / phi - Vc)
    ok = True

    if Vs > 2.1 * math.sqrt(fc) * b * d:
        notes.append("Vs เกิน 2.1√fc'·b·d — ต้องขยายหน้าตัดคาน")
        ok = False
    if Vs > 1.1 * math.sqrt(fc) * b * d:
        s_max = min(d / 4, 30.0)
    else:
        s_max = min(d / 2, 60.0)
    s_max = min(s_max, s_min_steel)

    if Vu <= phiVc / 2:
        zone = "Vu ≤ φVc/2 : ไม่ต้องการเหล็กปลอกตามทฤษฎี (ใส่เหล็กปลอกขั้นต่ำ)"
        s_req = float("inf")
    elif Vu <= phiVc:
        zone = "φVc/2 < Vu ≤ φVc : ใช้เหล็กปลอกขั้นต่ำ"
        s_req = float("inf")
    else:
        zone = "Vu > φVc : ต้องคำนวณเหล็กปลอก"
        s_req = Av * fyt * d / Vs

    s_use = min(s_req, s_max)
    s_use = math.floor(s_use / 2.5) * 2.5  # ปัดลงทีละ 2.5 cm
    if s_use < 5:
        notes.append("ระยะเรียงเหล็กปลอกน้อยกว่า 5 cm — ควรใช้เหล็กปลอกใหญ่ขึ้นหรือเพิ่มจำนวนขา")
        s_use = max(s_use, 2.5)
        ok = False
    phiVn = phi * (Vc + Av * fyt * d / s_use)
    if phiVn < Vu:
        ok = False
    return ShearResult(
        Vu=Vu, phiVc=phiVc, Vs_req=Vs, Av=Av, s_req=s_req, s_max=s_max,
        s_use=s_use, phiVn=phiVn, zone=zone, ok=ok, notes=notes,
    )


def gross_inertia(sec: Section) -> float:
    return sec.b * sec.h ** 3 / 12


def cracking_moment(sec: Section) -> float:
    fr = 2.0 * math.sqrt(sec.fc)
    return fr * gross_inertia(sec) / (sec.h / 2)


def cracked_inertia(sec: Section, As: float, d: float) -> float:
    n = ES / ec(sec.fc)
    B = sec.b / (n * As)
    kd = (math.sqrt(2 * d * B + 1) - 1) / B
    return sec.b * kd ** 3 / 3 + n * As * (d - kd) ** 2


def effective_inertia(sec: Section, Ma: float, As: float, d: float) -> float:
    Ig = gross_inertia(sec)
    Mcr = cracking_moment(sec)
    Ma = abs(Ma)
    if Ma <= Mcr:
        return Ig
    Icr = cracked_inertia(sec, As, d)
    r = (Mcr / Ma) ** 3
    return min(Ig, r * Ig + (1 - r) * Icr)


MIN_DEPTH_RATIO = {"simple": 16, "cantilever": 8, "fixed_fixed": 21, "propped": 18.5}


def min_depth(L: float, beam_type: str, fy: float) -> float:
    """ความลึกขั้นต่ำที่ไม่ต้องตรวจสอบการแอ่นตัว (ACI ตาราง 9.5a)"""
    return L / MIN_DEPTH_RATIO[beam_type] * (0.4 + fy / 7000)
