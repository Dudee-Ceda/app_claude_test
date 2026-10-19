"""Streamlit web app สำหรับวิเคราะห์และออกแบบคานคอนกรีตเสริมเหล็ก

รัน: streamlit run app.py
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from beam.analysis import PointLoad, analyze
from beam import design as dsg

st.set_page_config(page_title="ออกแบบคาน คสล.", page_icon="🏗️", layout="wide")

BEAM_LABELS = {
    "simple": "คานช่วงเดียวธรรมดา (Simple)",
    "cantilever": "คานยื่น (Cantilever)",
    "fixed_fixed": "ยึดแน่นสองปลาย (Fixed-Fixed)",
    "propped": "ยึดแน่น-หมุนได้ (Propped Cantilever)",
}
CONCRETE_UNIT_WEIGHT = 2400  # kg/m³


def ok_badge(ok: bool) -> str:
    return "✅ ผ่าน" if ok else "❌ ไม่ผ่าน"


# ---------------------------------------------------------------- ข้อมูลนำเข้า
with st.sidebar:
    st.header("⚙️ ข้อมูลนำเข้า")

    st.subheader("1. ประเภทคาน")
    beam_type = st.selectbox("รูปแบบจุดรองรับ", list(BEAM_LABELS), format_func=BEAM_LABELS.get)
    L_m = st.number_input("ความยาวช่วงคาน L (m)", 0.5, 30.0, 5.0, 0.1)

    st.subheader("2. วัสดุ")
    fc = st.number_input("กำลังอัดคอนกรีต fc' (ksc)", 150.0, 600.0, 240.0, 10.0)
    fy_grade = st.selectbox("เหล็กเสริมหลัก", ["SD40", "SD30", "SD50", "SR24"])
    fyt_grade = st.selectbox("เหล็กปลอก", ["SR24", "SD30", "SD40"])
    fy, fyt = dsg.STEEL_GRADES[fy_grade], dsg.STEEL_GRADES[fyt_grade]

    st.subheader("3. หน้าตัดคาน")
    c1, c2 = st.columns(2)
    b = c1.number_input("กว้าง b (cm)", 10.0, 150.0, 25.0, 5.0)
    h = c2.number_input("ลึก h (cm)", 15.0, 250.0, 50.0, 5.0)
    cover = st.number_input("ระยะหุ้มคอนกรีต (cm)", 2.0, 7.5, 3.0, 0.5)
    c1, c2 = st.columns(2)
    main_bar = c1.selectbox("เหล็กเสริมหลัก", ["DB16", "DB12", "DB20", "DB25", "DB28", "DB32"])
    stirrup = c2.selectbox("เหล็กปลอก", ["RB9", "RB6", "DB10", "DB12"])
    legs = st.number_input("จำนวนขาเหล็กปลอก", 2, 6, 2, 1)

    st.subheader("4. น้ำหนักบรรทุก")
    combo_name = st.selectbox("การรวมน้ำหนัก", list(dsg.LOAD_COMBOS))
    self_weight = st.checkbox("รวมน้ำหนักคานเอง", value=True)
    wD = st.number_input("น้ำหนักบรรทุกคงที่เพิ่มเติม DL (kg/m)", 0.0, 1e6, 1500.0, 100.0)
    wL = st.number_input("น้ำหนักบรรทุกจร LL (kg/m)", 0.0, 1e6, 800.0, 100.0)
    st.caption("แรงกระทำเป็นจุด (ระยะวัดจากปลายซ้าย)")
    pl_df = st.data_editor(
        pd.DataFrame({"x (m)": [L_m / 2], "PD (kg)": [0.0], "PL (kg)": [0.0]}),
        num_rows="dynamic",
        width="stretch",
        key="point_loads",
    )

# ---------------------------------------------------------------- คำนวณ
L = L_m * 100  # cm
fD, fL, phi_b, phi_v = dsg.LOAD_COMBOS[combo_name]
sw = CONCRETE_UNIT_WEIGHT * b * h / 1e4 if self_weight else 0.0  # kg/m
wD_total = wD + sw
wu = fD * wD_total + fL * wL  # kg/m

pl_df = pl_df.dropna()
pD_loads = [PointLoad(r["x (m)"] * 100, r["PD (kg)"]) for _, r in pl_df.iterrows()]
pL_loads = [PointLoad(r["x (m)"] * 100, r["PL (kg)"]) for _, r in pl_df.iterrows()]
pU_loads = [PointLoad(d.x, fD * d.P + fL * l.P) for d, l in zip(pD_loads, pL_loads)]
bad_loads = [p.x / 100 for p in pU_loads if not 0 <= p.x <= L]
if bad_loads:
    st.sidebar.warning(f"ไม่นำแรงจุดที่ตำแหน่ง {bad_loads} m มาคิด เพราะอยู่นอกช่วงคาน")

sec = dsg.Section(b=b, h=h, cover=cover, stirrup=stirrup, fc=fc, fy=fy, fyt=fyt)

res_u = analyze(L, beam_type, wu / 100, pU_loads)
Mpos = max(res_u.M.max(), 0.0) + 0.0
Mneg = max(-res_u.M.min(), 0.0) + 0.0

hanger = "DB12" if fy_grade != "SR24" else "RB9"
flex_pos = dsg.design_flexure(sec, Mpos, main_bar, main_bar if Mneg > 0 else hanger, phi_b)
flex_neg = dsg.design_flexure(sec, Mneg, main_bar, main_bar, phi_b) if Mneg > 0 else None

# เหล็กบน/ล่างที่ใช้จริง (รวมเหล็กรับแรงอัดจากการออกแบบเสริมเหล็กสองชั้น)
n_bot = flex_pos.n_tension
n_top = flex_neg.n_tension if flex_neg else 2
top_bar = main_bar if flex_neg else hanger
if flex_pos.doubly:
    n_top = max(n_top, flex_pos.n_comp)
if flex_neg and flex_neg.doubly:
    n_bot = max(n_bot, flex_neg.n_comp)

# แรงเฉือนวิกฤตที่ระยะ d จากหน้าจุดรองรับ
d_eff = min(flex_pos.d, flex_neg.d if flex_neg else flex_pos.d)
supports_x = {"simple": [0, L], "cantilever": [0], "fixed_fixed": [0, L], "propped": [0, L]}[beam_type]
near_support_load = any(abs(p.x - s) < d_eff for p in pU_loads if p.P for s in supports_x)
mask = np.ones_like(res_u.x, dtype=bool)
if not near_support_load and L > 2 * d_eff:
    for s in supports_x:
        mask &= np.abs(res_u.x - s) >= d_eff
Vu_crit = np.abs(res_u.V[mask]).max()
Vu_max = np.abs(res_u.V).max()
shear = dsg.design_shear(sec, Vu_crit, d_eff, phi_v, legs)

# การโก่งตัว (น้ำหนักใช้งาน)
Ma_serv = np.abs(analyze(L, beam_type, (wD_total + wL) / 100, [PointLoad(d.x, d.P + l.P) for d, l in zip(pD_loads, pL_loads)]).M).max()
governing = flex_neg if (flex_neg and Mneg > Mpos) else flex_pos
Ie = dsg.effective_inertia(sec, Ma_serv, governing.As_prov, governing.d)
EIe = dsg.ec(fc) * Ie
defl_D = analyze(L, beam_type, wD_total / 100, pD_loads, EI=EIe).defl
defl_L = analyze(L, beam_type, wL / 100, pL_loads, EI=EIe).defl
rho_comp = (n_top * dsg.bar_area(top_bar)) / (b * governing.d)
lam = 2.0 / (1 + 50 * rho_comp)
idx_max = int(np.argmax(np.abs(defl_D + defl_L)))
dD, dL = defl_D[idx_max], defl_L[idx_max]
d_long = lam * dD + dL
span_for_limit = 2 * L if beam_type == "cantilever" else L
lim_L, lim_total = span_for_limit / 360, span_for_limit / 240
h_min = dsg.min_depth(L, beam_type, fy)
defl_ok = abs(dL) <= lim_L and abs(d_long) <= lim_total

all_ok = flex_pos.ok and (flex_neg.ok if flex_neg else True) and shear.ok and defl_ok

# ---------------------------------------------------------------- แสดงผล
st.title("🏗️ ออกแบบคานคอนกรีตเสริมเหล็ก")
st.caption(f"วิธีกำลัง (SDM) ตามแนวทาง วสท./ACI 318 · {BEAM_LABELS[beam_type]} · L = {L_m:g} m · หน่วย kg, cm")

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("wu (kg/m)", f"{wu:,.0f}")
m2.metric("Mu(+) (t-m)", f"{Mpos / 1e5:,.2f}")
m3.metric("Mu(−) (t-m)", f"{Mneg / 1e5:,.2f}")
m4.metric("Vu,max (t)", f"{Vu_max / 1e3:,.2f}")
m5.metric("สรุปผล", "ผ่าน ✅" if all_ok else "ไม่ผ่าน ❌")

tab_sum, tab_an, tab_flex, tab_shear, tab_defl = st.tabs(
    ["📋 สรุปผลการออกแบบ", "📈 แรงภายใน", "🔩 โมเมนต์ดัด", "✂️ แรงเฉือน", "📉 การโก่งตัว"]
)


def section_figure() -> go.Figure:
    fig = go.Figure()
    fig.add_shape(type="rect", x0=0, y0=0, x1=b, y1=h, line=dict(color="#555", width=2), fillcolor="#d9d9d9")
    ds = dsg.bar_dia_cm(stirrup)
    fig.add_shape(
        type="rect", x0=cover + ds / 2, y0=cover + ds / 2, x1=b - cover - ds / 2, y1=h - cover - ds / 2,
        line=dict(color="#1f6feb", width=2),
    )

    def place(n, bar, y_first, downward):
        db = dsg.bar_dia_cm(bar)
        per_layer = sec.bars_per_layer(bar)
        layers = [min(per_layer, n - i * per_layer) for i in range(math.ceil(n / per_layer))]
        spacing_v = db + max(2.5, db)
        for li, count in enumerate(layers):
            y = y_first + (-li if downward else li) * spacing_v
            x0, x1 = cover + ds + db / 2, b - cover - ds - db / 2
            xs = [x0] if count == 1 else np.linspace(x0, x1, count)
            for x in xs:
                fig.add_shape(type="circle", x0=x - db / 2, y0=y - db / 2, x1=x + db / 2, y1=y + db / 2,
                              fillcolor="#c0392b", line=dict(color="#7b241c"))

    place(n_bot, main_bar, cover + ds + dsg.bar_dia_cm(main_bar) / 2, downward=False)
    place(n_top, top_bar, h - cover - ds - dsg.bar_dia_cm(top_bar) / 2, downward=True)
    fig.add_annotation(x=b / 2, y=-4, text=f"b = {b:g} cm", showarrow=False)
    fig.add_annotation(x=-4, y=h / 2, text=f"h = {h:g} cm", showarrow=False, textangle=-90)
    fig.add_annotation(x=b / 2, y=h + 4, text=f"บน {n_top}-{top_bar}", showarrow=False)
    fig.add_annotation(x=b / 2, y=-9, text=f"ล่าง {n_bot}-{main_bar}", showarrow=False)
    pad = 12
    fig.update_xaxes(range=[-pad, b + pad], visible=False, scaleanchor="y")
    fig.update_yaxes(range=[-pad - 2, h + pad], visible=False)
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="rgba(0,0,0,0)")
    return fig


with tab_sum:
    c1, c2 = st.columns([1, 1.3])
    with c1:
        st.subheader("หน้าตัดคาน")
        st.plotly_chart(section_figure(), width="stretch")
    with c2:
        st.subheader("รายละเอียดเหล็กเสริม")
        rows = [
            ["เหล็กล่าง (รับโมเมนต์บวก)", f"{n_bot}-{main_bar}", f"{n_bot * dsg.bar_area(main_bar):.2f}",
             ok_badge(flex_pos.ok)],
            ["เหล็กบน" + (" (รับโมเมนต์ลบ)" if flex_neg else " (เหล็กยึดปลอก)"), f"{n_top}-{top_bar}",
             f"{n_top * dsg.bar_area(top_bar):.2f}", ok_badge(flex_neg.ok) if flex_neg else "—"],
            ["เหล็กปลอก", f"{stirrup} ({legs} ขา) @ {shear.s_use:g} cm", f"Av = {shear.Av:.2f}", ok_badge(shear.ok)],
            ["การโก่งตัว", f"Δ = {abs(d_long):.2f} cm", f"ยอมให้ {lim_total:.2f} cm", ok_badge(defl_ok)],
        ]
        st.dataframe(pd.DataFrame(rows, columns=["รายการ", "ใช้", "As (cm²)", "ตรวจสอบ"]),
                     hide_index=True, width="stretch")
        if h < h_min:
            st.info(f"ความลึกคาน h = {h:g} cm น้อยกว่าค่าแนะนำ h_min = {h_min:.1f} cm (ตรวจสอบการโก่งตัวแล้วในแท็บ 'การโก่งตัว')")
        for n in flex_pos.notes + (flex_neg.notes if flex_neg else []) + shear.notes:
            st.warning(n)
        st.markdown(
            f"""
**ข้อมูลการคำนวณ**
- น้ำหนักคานเอง = {sw:,.0f} kg/m, DL รวม = {wD_total:,.0f} kg/m, LL = {wL:,.0f} kg/m
- wu = {fD}×{wD_total:,.0f} + {fL}×{wL:,.0f} = **{wu:,.0f} kg/m**
- fc' = {fc:g} ksc, fy = {fy:,} ksc ({fy_grade}), fyt = {fyt:,} ksc ({fyt_grade})
- φ(ดัด) = {phi_b}, φ(เฉือน) = {phi_v}
"""
        )

with tab_an:
    x_m = res_u.x / 100
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.07,
                        subplot_titles=("แผนภาพแรงเฉือน Vu (t)", "แผนภาพโมเมนต์ดัด Mu (t-m)", "การโก่งตัวใช้งาน (cm)"))
    fig.add_trace(go.Scatter(x=x_m, y=res_u.V / 1e3, fill="tozeroy", name="Vu", line=dict(color="#2e86c1")), 1, 1)
    fig.add_trace(go.Scatter(x=x_m, y=res_u.M / 1e5, fill="tozeroy", name="Mu", line=dict(color="#c0392b")), 2, 1)
    fig.add_trace(go.Scatter(x=x_m, y=-(defl_D + defl_L), name="Δ (D+L)", line=dict(color="#27ae60")), 3, 1)
    fig.update_yaxes(autorange="reversed", row=2, col=1)  # วาดโมเมนต์บวกด้านล่าง (ด้านรับแรงดึง)
    fig.update_xaxes(title_text="ระยะ x (m)", row=3, col=1)
    fig.update_layout(height=750, showlegend=False, margin=dict(t=40))
    st.plotly_chart(fig, width="stretch")
    RL, ML = res_u.reactions["left"]
    RR, MR = res_u.reactions["right"]
    st.markdown(
        f"**แรงปฏิกิริยา (ประลัย):** ซ้าย R = {RL / 1e3:,.2f} t, M = {abs(ML) / 1e5:,.2f} t-m · "
        f"ขวา R = {RR / 1e3:,.2f} t, M = {abs(MR) / 1e5:,.2f} t-m"
    )
    with st.expander("ตารางค่าแรงภายใน"):
        step = max(1, len(res_u.x) // 40)
        st.dataframe(pd.DataFrame({
            "x (m)": x_m[::step].round(3), "Vu (kg)": res_u.V[::step].round(0), "Mu (kg-m)": (res_u.M[::step] / 100).round(0),
        }), hide_index=True, width="stretch")


def flexure_report(title: str, r: dsg.FlexureResult):
    st.subheader(title)
    a, bcol = st.columns(2)
    a.markdown(
        f"""
- Mu = {r.Mu / 1e5:,.3f} t-m
- d = {r.d:.2f} cm ({'2 ชั้น' if r.layers == 2 else '1 ชั้น'}), d' = {r.d_comp:.2f} cm
- ρmin = {r.rho_min:.5f}, ρmax = {r.rho_max:.5f}
- As ต้องการ = **{r.As_req:.2f} cm²**{f", As' ต้องการ = **{r.As_comp_req:.2f} cm²**" if r.doubly else ""}
"""
    )
    bcol.markdown(
        f"""
- ใช้เหล็ก **{r.n_tension}-{r.bar}** (As = {r.As_prov:.2f} cm², ρ = {r.rho:.5f})
- φMn = {r.phiMn / 1e5:,.3f} t-m {'≥' if r.phiMn >= r.Mu else '<'} Mu → {ok_badge(r.phiMn >= r.Mu)}
- εt = {r.eps_t:.4f} {'≥' if r.eps_t >= 0.004 else '<'} 0.004
- อัตราส่วนการใช้กำลัง = {r.Mu / r.phiMn if r.phiMn else float('inf'):.2f}
"""
    )


with tab_flex:
    flexure_report("โมเมนต์บวก (เหล็กล่าง)", flex_pos)
    if flex_neg:
        st.divider()
        flexure_report("โมเมนต์ลบ (เหล็กบน)", flex_neg)
    st.caption(
        "Rn = Mu/(φbd²), ρ = 0.85fc'/fy·[1 − √(1 − 2Rn/0.85fc')], "
        "ρb = 0.85β₁fc'/fy·6120/(6120+fy), ρmax = min(0.75ρb, ρ@εt=0.004), ρmin = max(0.8√fc'/fy, 14/fy)"
    )

with tab_shear:
    st.subheader("ออกแบบเหล็กปลอก")
    st.markdown(
        f"""
- Vu ที่หน้าตัดวิกฤต (ระยะ d จากจุดรองรับ) = **{shear.Vu / 1e3:,.2f} t**{" (มีแรงจุดใกล้จุดรองรับ ใช้ Vu สูงสุด)" if near_support_load else ""}
- Vc = 0.53√fc'·b·d = {shear.phiVc / phi_v / 1e3:,.2f} t → φVc = **{shear.phiVc / 1e3:,.2f} t**
- {shear.zone}
- Vs ต้องการ = Vu/φ − Vc = {shear.Vs_req / 1e3:,.2f} t
- Av = {legs} × {dsg.bar_area(stirrup):.3f} = {shear.Av:.3f} cm²
- s ต้องการ = Av·fyt·d / Vs = {"—" if math.isinf(shear.s_req) else f"{shear.s_req:.1f} cm"}
- s สูงสุด = {shear.s_max:.1f} cm
- **ใช้ {stirrup} @ {shear.s_use:g} cm** → φVn = {shear.phiVn / 1e3:,.2f} t {ok_badge(shear.ok)}
"""
    )
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=res_u.x / 100, y=np.abs(res_u.V) / 1e3, name="|Vu|", fill="tozeroy"))
    fig.add_hline(y=shear.phiVc / 1e3, line_dash="dash", line_color="orange", annotation_text="φVc")
    fig.add_hline(y=shear.phiVc / 2e3, line_dash="dot", line_color="gray", annotation_text="φVc/2")
    fig.add_hline(y=shear.phiVn / 1e3, line_color="green", annotation_text="φVn (ที่ใช้)")
    fig.update_layout(height=380, xaxis_title="ระยะ x (m)", yaxis_title="แรงเฉือน (t)", margin=dict(t=20))
    st.plotly_chart(fig, width="stretch")

with tab_defl:
    st.subheader("ตรวจสอบการโก่งตัว")
    st.markdown(
        f"""
- ความลึกขั้นต่ำ (ไม่ต้องตรวจการโก่งตัว) h_min = {h_min:.1f} cm → {"✅ h เพียงพอ" if h >= h_min else "⚠️ ต้องตรวจสอบการโก่งตัว"}
- Ec = 15,100√fc' = {dsg.ec(fc):,.0f} ksc, Ig = {dsg.gross_inertia(sec):,.0f} cm⁴
- Mcr = {dsg.cracking_moment(sec) / 1e5:,.3f} t-m, Ma (ใช้งาน) = {Ma_serv / 1e5:,.3f} t-m
- Ie (Branson) = {Ie:,.0f} cm⁴
- การโก่งตัวทันทีจาก DL = {abs(dD):.3f} cm, จาก LL = {abs(dL):.3f} cm
- ตัวคูณระยะยาว λ = 2.0/(1+50ρ') = {lam:.2f}
- LL: {abs(dL):.3f} ≤ L/360 = {lim_L:.2f} cm → {ok_badge(abs(dL) <= lim_L)}
- ระยะยาว λΔD + ΔL = {abs(d_long):.3f} ≤ L/240 = {lim_total:.2f} cm → {ok_badge(abs(d_long) <= lim_total)}
"""
    )
    if beam_type == "cantilever":
        st.caption("คานยื่น: ใช้ความยาวอ้างอิง 2L ในการคำนวณค่าการโก่งตัวที่ยอมให้")

st.divider()
st.caption("⚠️ โปรแกรมนี้ใช้เพื่อการศึกษาและการออกแบบเบื้องต้น ผลการออกแบบจริงควรได้รับการตรวจสอบโดยวิศวกรผู้มีใบอนุญาต")
