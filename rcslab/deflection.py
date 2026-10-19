"""Immediate and long-term deflection of a one-way slab strip (ACI 318, Branson Ie).

Units: loads kg/m² (strip 1 m wide), lengths cm, stresses ksc.
"""

from dataclasses import dataclass
import math

from .flexure import B
from .materials import Concrete, Steel

# Δ = w·L⁴ / (k·Ec·I) for a uniform load; plus P·L³/(3EI) for a cantilever end load
DEFLECTION_K = {"simple": 384 / 5, "one_end": 185.0, "both_ends": 384.0, "cantilever": 8.0}


@dataclass
class DeflectionResult:
    L: float  # cm
    Ec: float
    n: float
    Ig: float  # cm⁴
    Icr: float
    fr: float
    Mcr: float  # kg-cm
    Ma_D: float
    Ma_DL: float
    Ie_D: float
    Ie_DL: float
    delta_D: float  # cm
    delta_DL: float
    delta_L: float
    lam: float
    delta_long: float  # λΔD + ΔL
    limit_L: float
    limit_long: float

    @property
    def ok_L(self) -> bool:
        return self.delta_L <= self.limit_L

    @property
    def ok_long(self) -> bool:
        return self.delta_long <= self.limit_long

    @property
    def ok(self) -> bool:
        return self.ok_L and self.ok_long


def cracked_inertia(As: float, d: float, n: float) -> float:
    nAs = n * As
    x = (-nAs + math.sqrt(nAs**2 + 2 * B * nAs * d)) / B
    return B * x**3 / 3 + nAs * (d - x) ** 2


def effective_inertia(Ma: float, Mcr: float, Ig: float, Icr: float) -> float:
    if Ma <= Mcr:
        return Ig
    r = (Mcr / Ma) ** 3
    return min(Ig, r * Ig + (1 - r) * Icr)


def one_way_deflection(
    support: str,
    span_m: float,
    h: float,
    d: float,
    As: float,
    w_dead: float,
    w_live: float,
    p_end: float,
    moment_div: float,
    conc: Concrete,
    steel: Steel,
    xi: float = 2.0,
) -> DeflectionResult:
    """support: key of DEFLECTION_K; moment_div: Ma = wL²/moment_div at the critical section."""
    L = span_m * 100
    Ec = conc.Ec
    n = steel.Es / Ec
    Ig = B * h**3 / 12
    Icr = cracked_inertia(As, d, n)
    fr = 2.0 * math.sqrt(conc.fc)
    Mcr = fr * Ig / (h / 2)

    def moment(w: float, p: float) -> float:
        M = w / 100 * L**2 / moment_div
        return M + p * L if support == "cantilever" else M

    def deflect(w: float, p: float, Ie: float) -> float:
        dl = w / 100 * L**4 / (DEFLECTION_K[support] * Ec * Ie)
        if support == "cantilever":
            dl += p * L**3 / (3 * Ec * Ie)
        return dl

    Ma_D = moment(w_dead, p_end)
    Ma_DL = moment(w_dead + w_live, p_end)
    Ie_D = effective_inertia(Ma_D, Mcr, Ig, Icr)
    Ie_DL = effective_inertia(Ma_DL, Mcr, Ig, Icr)
    delta_D = deflect(w_dead, p_end, Ie_D)
    delta_DL = deflect(w_dead + w_live, p_end, Ie_DL)
    delta_L = delta_DL - delta_D
    lam = xi / (1 + 50 * 0.0)  # no compression steel
    # cantilever limits are applied to twice the overhang (equivalent span)
    L_eq = 2 * L if support == "cantilever" else L
    return DeflectionResult(
        L=L,
        Ec=Ec,
        n=n,
        Ig=Ig,
        Icr=Icr,
        fr=fr,
        Mcr=Mcr,
        Ma_D=Ma_D,
        Ma_DL=Ma_DL,
        Ie_D=Ie_D,
        Ie_DL=Ie_DL,
        delta_D=delta_D,
        delta_DL=delta_DL,
        delta_L=delta_L,
        lam=lam,
        delta_long=lam * delta_D + delta_L,
        limit_L=L_eq / 360,
        limit_long=L_eq / 240,
    )
