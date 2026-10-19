"""Strength-design flexure and shear checks for a 1 m wide slab strip."""

from dataclasses import dataclass
import math

from .materials import Concrete, DesignCode, Steel, bar_area

B = 100.0  # strip width, cm
SPACING_STEP = 2.5  # round spacing down to this increment, cm


@dataclass
class FlexureResult:
    label: str
    Mu: float  # kg-m per m
    d: float  # cm
    Rn: float  # ksc
    rho_req: float
    As_req: float  # cm²/m from strength
    As_min: float  # cm²/m
    As_design: float  # cm²/m governing
    bar: str
    spacing: float  # cm
    As_prov: float  # cm²/m
    phiMn: float  # kg-m per m
    ok: bool
    note: str = ""

    @property
    def callout(self) -> str:
        return f"{self.bar} @ {self.spacing / 100:.3f} m"


@dataclass
class ShearResult:
    Vu: float  # kg per m
    phiVc: float  # kg per m
    d: float
    ok: bool

    @property
    def ratio(self) -> float:
        return self.Vu / self.phiVc if self.phiVc else math.inf


def rho_balanced(conc: Concrete, steel: Steel) -> float:
    return 0.85 * conc.beta1 * conc.fc / steel.fy * 6120 / (6120 + steel.fy)


def rho_max(conc: Concrete, steel: Steel) -> float:
    return 0.75 * rho_balanced(conc, steel)


def required_rho(Mu_kgm: float, d: float, conc: Concrete, steel: Steel, code: DesignCode) -> tuple[float, float]:
    """Return (Rn, rho). rho = nan when section is inadequate."""
    Mu = Mu_kgm * 100  # kg-cm
    Rn = Mu / (code.phi_flexure * B * d**2)
    k = 1 - 2 * Rn / (0.85 * conc.fc)
    if k < 0:
        return Rn, math.nan
    rho = 0.85 * conc.fc / steel.fy * (1 - math.sqrt(k))
    return Rn, rho


def select_spacing(As_req: float, bar: str, s_max: float) -> float:
    s = B * bar_area(bar) / As_req if As_req > 0 else s_max
    s = math.floor(s / SPACING_STEP + 1e-9) * SPACING_STEP
    return max(SPACING_STEP, min(s, s_max))


def moment_capacity(As: float, d: float, conc: Concrete, steel: Steel, code: DesignCode) -> float:
    a = As * steel.fy / (0.85 * conc.fc * B)
    return code.phi_flexure * As * steel.fy * (d - a / 2) / 100  # kg-m


def design_flexure(
    label: str,
    Mu: float,
    d: float,
    h: float,
    bar: str,
    s_max: float,
    conc: Concrete,
    steel: Steel,
    code: DesignCode,
) -> FlexureResult:
    Mu = abs(Mu)
    Rn, rho = required_rho(Mu, d, conc, steel, code)
    As_min = steel.rho_temp * B * h
    notes = []
    ok = True
    if math.isnan(rho):
        ok = False
        As_req = math.nan
        As_design = As_min
        notes.append("หน้าตัดรับโมเมนต์ไม่พอ — เพิ่มความหนาพื้น")
    else:
        As_req = rho * B * d
        if rho > rho_max(conc, steel):
            ok = False
            notes.append("ρ > ρmax — เพิ่มความหนาพื้น")
        As_design = max(As_req, As_min)
        if As_min > As_req:
            notes.append("ใช้ As,min (temperature & shrinkage)")
    s = select_spacing(As_design, bar, s_max)
    As_prov = B * bar_area(bar) / s
    phiMn = moment_capacity(As_prov, d, conc, steel, code)
    if As_prov < As_design - 1e-9:
        ok = False
        notes.append(f"{bar} ที่ระยะ {SPACING_STEP:g} cm ยังไม่พอ — เพิ่มขนาดเหล็ก")
    if phiMn < Mu - 1e-6:
        ok = False
    return FlexureResult(
        label=label,
        Mu=Mu,
        d=d,
        Rn=Rn,
        rho_req=rho,
        As_req=As_req,
        As_min=As_min,
        As_design=As_design,
        bar=bar,
        spacing=s,
        As_prov=As_prov,
        phiMn=phiMn,
        ok=ok,
        note="; ".join(notes),
    )


def check_shear(Vu: float, d: float, conc: Concrete, code: DesignCode) -> ShearResult:
    phiVc = code.phi_shear * 0.53 * math.sqrt(conc.fc) * B * d
    return ShearResult(Vu=Vu, phiVc=phiVc, d=d, ok=Vu <= phiVc)
