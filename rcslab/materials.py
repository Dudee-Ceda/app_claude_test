"""Materials, rebar table and design-code parameters.

Units: stress in ksc (kg/cm²), length in cm, bar area in cm².
"""

from dataclasses import dataclass
import math

# Thai standard bars (TIS 20 / TIS 24): name -> (diameter cm, area cm²)
BARS: dict[str, tuple[float, float]] = {
    "RB6": (0.6, 0.283),
    "RB9": (0.9, 0.636),
    "DB10": (1.0, 0.785),
    "DB12": (1.2, 1.131),
    "DB16": (1.6, 2.011),
    "DB20": (2.0, 3.142),
}

# Common Thai steel grades: name -> fy (ksc)
STEEL_GRADES: dict[str, float] = {
    "SR24": 2400.0,
    "SD30": 3000.0,
    "SD40": 4000.0,
    "SD50": 5000.0,
}


@dataclass(frozen=True)
class DesignCode:
    name: str
    dl_factor: float
    ll_factor: float
    phi_flexure: float
    phi_shear: float


CODES: dict[str, DesignCode] = {
    "EIT / ACI 318-99 (1.4D + 1.7L)": DesignCode("EIT / ACI 318-99", 1.4, 1.7, 0.90, 0.85),
    "ACI 318-19 (1.2D + 1.6L)": DesignCode("ACI 318-19", 1.2, 1.6, 0.90, 0.75),
}


@dataclass(frozen=True)
class Concrete:
    fc: float  # ksc
    unit_weight: float = 2400.0  # kg/m³

    @property
    def beta1(self) -> float:
        """Whitney stress-block factor (fc in ksc, 280 ksc ≈ 4000 psi)."""
        if self.fc <= 280:
            return 0.85
        return max(0.65, 0.85 - 0.05 * (self.fc - 280) / 70)

    @property
    def Ec(self) -> float:
        return 15100 * math.sqrt(self.fc)


@dataclass(frozen=True)
class Steel:
    fy: float  # ksc
    Es: float = 2.04e6

    @property
    def rho_temp(self) -> float:
        """Shrinkage & temperature steel ratio (ACI 318 7.12 / EIT)."""
        if self.fy <= 3500:
            return 0.0020
        if self.fy <= 4000:
            return 0.0018
        return max(0.0014, 0.0018 * 4000 / self.fy)


def bar_area(bar: str) -> float:
    return BARS[bar][1]


def bar_dia(bar: str) -> float:
    return BARS[bar][0]
