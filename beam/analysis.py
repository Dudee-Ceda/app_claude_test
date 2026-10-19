"""การวิเคราะห์คานช่วงเดียวด้วยวิธีไฟไนต์เอลิเมนต์ (Euler-Bernoulli beam element)

หน่วยภายในทั้งหมด: kg, cm
- ความยาว / ตำแหน่ง: cm
- น้ำหนักแผ่: kg/cm
- แรงจุด: kg
- E: kg/cm² (ksc), I: cm⁴
- โมเมนต์: kg-cm

เครื่องหมาย: แรงทิศขึ้นเป็นบวก, น้ำหนักบรรทุกทิศลงใส่ค่าบวก,
โมเมนต์ดัดบวก = โมเมนต์บวก (ท้องคานรับแรงดึง)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# ประเภทจุดรองรับ: (ยึดการเคลื่อนที่แนวดิ่ง, ยึดการหมุน)
SUPPORTS = {
    "pin": (True, False),
    "fixed": (True, True),
    "free": (False, False),
}

BEAM_TYPES = {
    "simple": ("pin", "pin"),
    "cantilever": ("fixed", "free"),
    "fixed_fixed": ("fixed", "fixed"),
    "propped": ("fixed", "pin"),
}


@dataclass
class PointLoad:
    x: float  # cm จากปลายซ้าย
    P: float  # kg (ทิศลงเป็นบวก)


@dataclass
class BeamResult:
    x: np.ndarray  # cm
    V: np.ndarray  # kg
    M: np.ndarray  # kg-cm
    defl: np.ndarray  # cm (ทิศลงเป็นบวก)
    reactions: dict = field(default_factory=dict)  # {"left": (R, M), "right": (R, M)}


def _element_stiffness(EI: float, le: float) -> np.ndarray:
    l2, l3 = le * le, le ** 3
    return EI / l3 * np.array(
        [
            [12, 6 * le, -12, 6 * le],
            [6 * le, 4 * l2, -6 * le, 2 * l2],
            [-12, -6 * le, 12, -6 * le],
            [6 * le, 2 * l2, -6 * le, 4 * l2],
        ]
    )


def analyze(
    L: float,
    beam_type: str,
    w: float,
    point_loads: list[PointLoad] | None = None,
    EI: float = 1.0,
    n_elem: int = 200,
) -> BeamResult:
    """วิเคราะห์คานช่วงเดียวรับน้ำหนักแผ่สม่ำเสมอ w และแรงจุด"""
    point_loads = [p for p in (point_loads or []) if 0 <= p.x <= L and p.P != 0]
    left, right = BEAM_TYPES[beam_type]

    xs = np.linspace(0.0, L, n_elem + 1)
    xs = np.unique(np.concatenate([xs, [p.x for p in point_loads]]))
    n_nodes = len(xs)
    ndof = 2 * n_nodes

    K = np.zeros((ndof, ndof))
    F = np.zeros(ndof)
    for i in range(n_nodes - 1):
        le = xs[i + 1] - xs[i]
        dofs = [2 * i, 2 * i + 1, 2 * i + 2, 2 * i + 3]
        K[np.ix_(dofs, dofs)] += _element_stiffness(EI, le)
        # แรงเทียบเท่าของน้ำหนักแผ่ (ทิศลง)
        F[dofs] += -w * np.array([le / 2, le * le / 12, le / 2, -le * le / 12])
    for p in point_loads:
        idx = int(np.argmin(np.abs(xs - p.x)))
        F[2 * idx] += -p.P

    restrained = []
    for node, sup in ((0, left), (n_nodes - 1, right)):
        fix_v, fix_r = SUPPORTS[sup]
        if fix_v:
            restrained.append(2 * node)
        if fix_r:
            restrained.append(2 * node + 1)
    free = np.setdiff1d(np.arange(ndof), restrained)

    u = np.zeros(ndof)
    u[free] = np.linalg.solve(K[np.ix_(free, free)], F[free])
    R = K @ u - F  # แรงปฏิกิริยา (ทิศขึ้น/ทวนเข็มเป็นบวก)

    reactions = {
        "left": (R[0], R[1]),
        "right": (R[2 * (n_nodes - 1)], R[2 * (n_nodes - 1) + 1]),
    }

    # แรงเฉือนและโมเมนต์จากสมดุลของชิ้นส่วนด้านซ้าย (แม่นยำ ไม่ขึ้นกับจำนวนเอลิเมนต์)
    x_plot = np.linspace(0.0, L, 801)
    eps = 1e-9 * L
    x_plot = np.unique(
        np.concatenate([x_plot, [p.x - eps for p in point_loads if p.x > 0], [p.x for p in point_loads]])
    )
    x_plot = x_plot[(x_plot >= 0) & (x_plot <= L)]
    RL, ML = reactions["left"]
    V = RL - w * x_plot
    M = RL * x_plot - ML - w * x_plot ** 2 / 2
    for p in point_loads:
        past = x_plot >= p.x
        V = V - p.P * past
        M = M - p.P * (x_plot - p.x) * past

    # ตัดค่าคลาดเคลื่อนเชิงตัวเลขที่เล็กมากออก
    for arr in (V, M):
        arr[np.abs(arr) < 1e-6 * max(np.abs(arr).max(), 1.0)] = 0.0

    defl = -np.interp(x_plot, xs, u[0::2])
    return BeamResult(x=x_plot, V=V, M=M, defl=defl, reactions=reactions)
