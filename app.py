"""RC Slab Design — Streamlit app for reinforced concrete slab design (SDM)."""

import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from rcslab import BARS, CODES, ONE_WAY_SUPPORTS, Concrete, Steel
from rcslab.boq import BOQ, one_way_boq, two_way_boq
from rcslab.flexure import FlexureResult, rho_max
from rcslab.materials import STEEL_GRADES
from rcslab.one_way import OneWayInput, OneWayResult, design_one_way
from rcslab.report_pdf import markdown_to_pdf
from rcslab.schedule import COLUMNS, PDF_COL_WIDTHS, one_way_row, schedule_notes, two_way_row
from rcslab.two_way import CASE_NAMES, TwoWayInput, TwoWayResult, design_two_way

st.set_page_config(page_title="RC Slab Design", page_icon="🏗️", layout="wide")

PASS = "✅ ผ่าน"
FAIL = "❌ ไม่ผ่าน"


def status(ok: bool) -> str:
    return PASS if ok else FAIL


# --------------------------------------------------------------------------- sidebar
st.sidebar.title("🏗️ RC Slab Design")
st.sidebar.caption("ออกแบบพื้นคอนกรีตเสริมเหล็ก — วิธีกำลัง (Strength Design Method)")

st.sidebar.header("มาตรฐานการออกแบบ")
code_name = st.sidebar.selectbox("Load combination / φ", list(CODES))
code = CODES[code_name]
st.sidebar.caption(
    f"U = {code.dl_factor}D + {code.ll_factor}L · φ(ดัด) = {code.phi_flexure} · φ(เฉือน) = {code.phi_shear}"
)

st.sidebar.header("วัสดุ")
fc = st.sidebar.number_input("f'c คอนกรีต (ksc)", 150.0, 500.0, 240.0, 10.0)
grade = st.sidebar.selectbox("ชั้นคุณภาพเหล็กเสริม", list(STEEL_GRADES), index=2)
fy = STEEL_GRADES[grade]
st.sidebar.caption(f"fy = {fy:,.0f} ksc")
gamma_c = st.sidebar.number_input("หน่วยน้ำหนักคอนกรีต (kg/m³)", 2200.0, 2600.0, 2400.0, 50.0)
cover = st.sidebar.number_input("ระยะหุ้มคอนกรีต (cm)", 1.5, 5.0, 2.0, 0.5)

st.sidebar.header("ปริมาณวัสดุ (BOQ)")
waste = st.sidebar.number_input("เผื่อระยะทาบ/เศษเหล็ก (%)", 0.0, 30.0, 7.0, 1.0) / 100

conc = Concrete(fc=fc, unit_weight=gamma_c)
steel = Steel(fy=fy)

with st.sidebar.expander("ค่าคงที่ที่ใช้"):
    st.write(f"β₁ = {conc.beta1:.3f}")
    st.write(f"Ec = {conc.Ec:,.0f} ksc")
    st.write(f"ρ,temp = {steel.rho_temp:.4f}")
    st.write(f"ρ,max = 0.75ρb = {rho_max(conc, steel):.4f}")

# --------------------------------------------------------------------------- helpers
BAR_NAMES = list(BARS)


def flexure_table(rows: list[FlexureResult]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ตำแหน่ง": r.label,
                "Mu (kg-m/m)": round(r.Mu, 1),
                "ρ req": "—" if r.rho_req != r.rho_req else f"{r.rho_req:.5f}",
                "As req (cm²/m)": "—" if r.As_req != r.As_req else round(r.As_req, 2),
                "As min (cm²/m)": round(r.As_min, 2),
                "เหล็กเสริม": r.callout,
                "As prov (cm²/m)": round(r.As_prov, 2),
                "φMn (kg-m/m)": round(r.phiMn, 1),
                "สถานะ": status(r.ok),
                "หมายเหตุ": r.note,
            }
            for r in rows
        ]
    )


def load_block(sw: float, sdl: float, ll: float, wd: float, wu: float) -> None:
    c = st.columns(4)
    c[0].metric("น้ำหนักพื้น (SW)", f"{sw:,.0f} kg/m²")
    c[1].metric("DL รวม", f"{wd:,.0f} kg/m²")
    c[2].metric("LL", f"{ll:,.0f} kg/m²")
    c[3].metric("wu (factored)", f"{wu:,.0f} kg/m²")


def overall_banner(ok: bool) -> None:
    if ok:
        st.success("ผลการออกแบบ: ผ่านทุกเกณฑ์ ✅")
    else:
        st.error("ผลการออกแบบ: มีรายการไม่ผ่าน ❌ — ดูรายละเอียดด้านล่าง")


def one_way_moment_figure(res: OneWayResult) -> go.Figure:
    L = res.inp.span
    sup = ONE_WAY_SUPPORTS[res.inp.support]
    n = 101
    xs = [L * i / (n - 1) for i in range(n)]
    w = res.wu
    if sup.name == "cantilever":
        pu = code.dl_factor * res.inp.p_end
        ys = [-(w * (L - x) ** 2 / 2 + pu * (L - x)) for x in xs]
    else:
        ml = w * L**2 / sup.neg_disc if sup.neg_disc else 0.0
        mr = w * L**2 / sup.neg_cont if sup.neg_cont else 0.0
        if sup.name == "both_ends":
            ml = mr
        if sup.name == "simple":  # top bars at simple ends are for crack control only
            ml = mr = 0.0
        mp = w * L**2 / sup.pos
        # quadratic through (0,-ml), (L/2, mp), (L,-mr)
        a = (-ml - mr - 2 * mp) * 2 / L**2
        b = (-mr + ml) / L - a * L
        ys = [a * x**2 + b * x - ml for x in xs]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=xs, y=ys, fill="tozeroy", mode="lines", line=dict(color="#2563eb", width=2), name="Mu")
    )
    fig.add_hline(y=0, line=dict(color="#6b7280", width=1))
    fig.update_layout(
        title="แผนภาพโมเมนต์ (โดยประมาณจากสัมประสิทธิ์)",
        xaxis_title="ระยะ (m)",
        yaxis_title="Mu (kg-m/m)",
        yaxis=dict(autorange="reversed"),  # positive moment drawn downward (tension side)
        height=320,
        margin=dict(l=10, r=10, t=50, b=10),
        showlegend=False,
    )
    return fig


def two_way_plan_figure(res: TwoWayResult) -> go.Figure:
    inp = res.inp
    W, H = inp.short_span, inp.long_span  # x = first span input, y = second span input
    fig = go.Figure()

    def edge(x0, y0, x1, y1, cont: bool, name: str):
        fig.add_trace(
            go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                line=dict(color="#111827" if cont else "#dc2626", width=6 if cont else 3,
                          dash="solid" if cont else "dash"),
                name=name,
                hoverinfo="name",
                showlegend=False,
            )
        )

    # edges along y (length H) = "long_edge" flags; edges along x (length W) = "short_edge" flags
    edge(0, 0, 0, H, inp.long_edge_1, "ขอบ 1 " + ("ต่อเนื่อง" if inp.long_edge_1 else "ไม่ต่อเนื่อง"))
    edge(W, 0, W, H, inp.long_edge_2, "ขอบ 2 " + ("ต่อเนื่อง" if inp.long_edge_2 else "ไม่ต่อเนื่อง"))
    edge(0, 0, W, 0, inp.short_edge_1, "ขอบ 3 " + ("ต่อเนื่อง" if inp.short_edge_1 else "ไม่ต่อเนื่อง"))
    edge(0, H, W, H, inp.short_edge_2, "ขอบ 4 " + ("ต่อเนื่อง" if inp.short_edge_2 else "ไม่ต่อเนื่อง"))

    s_pos = next(f for f in res.flexure_short if "+M" in f.label)
    l_pos = next(f for f in res.flexure_long if "+M" in f.label)
    swapped = inp.short_span > inp.long_span
    x_bar, y_bar = (l_pos, s_pos) if swapped else (s_pos, l_pos)
    # bottom bars: X-direction bar drawn horizontally, Y-direction bar drawn vertically
    fig.add_trace(go.Scatter(x=[0.08 * W, 0.92 * W], y=[0.35 * H] * 2, mode="lines",
                             line=dict(color="#1d4ed8", width=3), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=[0.35 * W] * 2, y=[0.08 * H, 0.92 * H], mode="lines",
                             line=dict(color="#047857", width=3), hoverinfo="skip", showlegend=False))
    fig.add_annotation(x=0.62 * W, y=0.35 * H, yshift=12, text=f"X: {x_bar.callout}", showarrow=False,
                       font=dict(size=12, color="#1d4ed8"))
    fig.add_annotation(x=0.35 * W, y=0.7 * H, xshift=-12, text=f"Y: {y_bar.callout}", showarrow=False,
                       textangle=-90, font=dict(size=12, color="#047857"))
    fig.add_annotation(x=W / 2, y=-0.08 * H, text=f"{W:.2f} m", showarrow=False)
    fig.add_annotation(x=-0.08 * W, y=H / 2, text=f"{H:.2f} m", showarrow=False, textangle=-90)
    fig.update_layout(
        title=dict(text="แปลนแผ่นพื้น · เหล็กล่าง<br><sup>เส้นทึบดำ = ขอบต่อเนื่อง, เส้นประแดง = ขอบไม่ต่อเนื่อง</sup>"),
        xaxis=dict(visible=False, range=[-0.2 * W, 1.2 * W]),
        yaxis=dict(visible=False, range=[-0.2 * H, 1.2 * H]),
        height=460,
        margin=dict(l=10, r=10, t=50, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def boq_table(boq: BOQ) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "รายการ": i.description,
                "เหล็ก": i.bar,
                "@ (m)": round(i.spacing / 100, 3),
                "จำนวน (เส้น)": i.count,
                "ยาว/เส้น (m)": round(i.length, 2),
                "ยาวรวม (m)": round(i.total_length, 2),
                "น้ำหนัก (kg)": round(i.weight, 1),
            }
            for i in boq.items
        ]
    )


def boq_section(boq: BOQ) -> None:
    st.subheader("ปริมาณวัสดุ (BOQ) ต่อ 1 แผ่นพื้น")
    c = st.columns(4)
    c[0].metric("คอนกรีต", f"{boq.concrete:.2f} m³")
    c[1].metric("ไม้แบบท้องพื้น", f"{boq.formwork:.2f} m²")
    c[2].metric(f"เหล็กเสริม (+{boq.waste * 100:.0f}%)", f"{boq.steel_total:,.1f} kg")
    c[3].metric("อัตราส่วนเหล็ก", f"{boq.steel_ratio:.1f} kg/m³")
    st.dataframe(boq_table(boq), hide_index=True, width="stretch")
    st.caption(
        "น้ำหนักเหล็กแยกขนาด (รวมเผื่อ): "
        + ", ".join(f"{b} {w:,.1f} kg" for b, w in boq.by_bar().items())
        + " · ความยาวเหล็กเป็นค่าประมาณสำหรับถอดปริมาณ ไม่ใช่แบบขยายรายละเอียด"
    )


def boq_markdown(boq: BOQ) -> list[str]:
    lines = [
        "",
        "## ปริมาณวัสดุ (BOQ) ต่อ 1 แผ่นพื้น",
        f"- คอนกรีต = {boq.area:.2f} m² × {boq.h / 100:.3f} m = {boq.concrete:.2f} m³",
        f"- ไม้แบบท้องพื้น = {boq.formwork:.2f} m²",
        f"- เหล็กเสริมสุทธิ = {boq.steel_net:,.1f} kg, รวมเผื่อ {boq.waste * 100:.0f}% = **{boq.steel_total:,.1f} kg**"
        f" ({boq.steel_ratio:.1f} kg/m³)",
        "",
        "| รายการ | เหล็ก | @ (m) | จำนวน | ยาว/เส้น (m) | ยาวรวม (m) | น้ำหนัก (kg) |",
        "|---|---|---|---|---|---|---|",
    ]
    for i in boq.items:
        lines.append(
            f"| {i.description} | {i.bar} | {i.spacing / 100:.3f} | {i.count} | {i.length:.2f} | "
            f"{i.total_length:.2f} | {i.weight:.1f} |"
        )
    return lines


@st.cache_data(show_spinner=False)
def to_pdf(md: str, landscape: bool = False, col_widths: tuple | None = None) -> bytes:
    return markdown_to_pdf(md, landscape=landscape, table_font=8 if landscape else 9, col_widths=col_widths)


def download_buttons(md: str, stem: str) -> None:
    c = st.columns([1, 1, 3])
    c[0].download_button("📄 รายการคำนวณ (.md)", md, f"{stem}.md", "text/markdown", key=f"{stem}_md")
    c[1].download_button("🖨️ รายการคำนวณ (PDF)", to_pdf(md), f"{stem}.pdf", "application/pdf", key=f"{stem}_pdf")


def report_one_way(res: OneWayResult, boq: BOQ) -> str:
    i = res.inp
    lines = [
        "# RC Slab Design — พื้นทางเดียว (One-way slab)",
        "",
        f"- มาตรฐาน: {code_name}",
        f"- f'c = {fc:.0f} ksc, {grade} fy = {fy:.0f} ksc, cover = {i.cover} cm",
        f"- ช่วงพื้น L = {i.span:.2f} m, ความหนา h = {i.h:.1f} cm, เงื่อนไข: {i.support}",
        *([f"- น้ำหนักแนวเส้นที่ปลายพื้นยื่น P = {i.p_end:.1f} kg/m (DL)"] if i.p_end else []),
        "",
        "## น้ำหนักบรรทุก",
        f"- SW = {res.sw:.1f} kg/m², SDL = {i.sdl:.1f} kg/m², DL = {res.wd:.1f} kg/m², LL = {i.ll:.1f} kg/m²",
        f"- wu = {code.dl_factor}({res.wd:.1f}) + {code.ll_factor}({i.ll:.1f}) = {res.wu:.1f} kg/m²",
        "",
        "## ความหนาต่ำสุด",
        f"- h,min = {res.h_min:.2f} cm → {status(res.h_ok)}",
        "",
        "## เหล็กเสริมรับโมเมนต์ (d = %.2f cm)" % res.d,
    ]
    for f in res.flexure + [res.temp]:
        lines.append(
            f"- {f.label}: Mu = {f.Mu:.1f} kg-m/m, As,req = {f.As_design:.2f} cm²/m → **{f.callout}** "
            f"(As = {f.As_prov:.2f} cm²/m, φMn = {f.phiMn:.1f}) {status(f.ok)}"
        )
    s = res.shear
    df = res.deflection
    lines += [
        "",
        "## แรงเฉือน",
        f"- Vu = {s.Vu:.1f} kg/m, φVc = {s.phiVc:.1f} kg/m → {status(s.ok)}",
        "",
        "## การแอ่นตัว (ACI 318, Branson Ie)",
        f"- Ec = {df.Ec:,.0f} ksc, n = {df.n:.2f}, fr = {df.fr:.1f} ksc",
        f"- Ig = {df.Ig:,.0f} cm⁴, Icr = {df.Icr:,.0f} cm⁴, Mcr = {df.Mcr / 100:,.1f} kg-m",
        f"- Ma(D) = {df.Ma_D / 100:,.1f} kg-m → Ie = {df.Ie_D:,.0f} cm⁴; "
        f"Ma(D+L) = {df.Ma_DL / 100:,.1f} kg-m → Ie = {df.Ie_DL:,.0f} cm⁴",
        f"- ΔD = {df.delta_D:.3f} cm, ΔD+L = {df.delta_DL:.3f} cm",
        f"- ΔL = {df.delta_L:.3f} cm ≤ {df.limit_L:.3f} cm → {status(df.ok_L)}",
        f"- λ·ΔD + ΔL = {df.lam:.1f}×{df.delta_D:.3f} + {df.delta_L:.3f} = {df.delta_long:.3f} cm "
        f"≤ {df.limit_long:.3f} cm → {status(df.ok_long)}",
        *boq_markdown(boq),
        *(["", "## หมายเหตุ"] + [f"- {n}" for n in res.notes] if res.notes else []),
        "",
        f"**สรุป: {status(res.ok)}**",
    ]
    return "\n".join(lines)


def report_two_way(res: TwoWayResult, boq: BOQ) -> str:
    i = res.inp
    lines = [
        "# RC Slab Design — พื้นสองทาง (Two-way slab, ACI 318-63 Method 2)",
        "",
        f"- มาตรฐาน: {code_name}",
        f"- f'c = {fc:.0f} ksc, {grade} fy = {fy:.0f} ksc, cover = {i.cover} cm",
        f"- S = {res.S:.2f} m, L = {res.L:.2f} m, m = {res.m:.3f}, h = {i.h:.1f} cm",
        f"- {CASE_NAMES[res.case]}",
        "",
        "## น้ำหนักบรรทุก",
        f"- SW = {res.sw:.1f} kg/m², SDL = {i.sdl:.1f} kg/m², DL = {res.wd:.1f} kg/m², LL = {i.ll:.1f} kg/m²",
        f"- wu = {code.dl_factor}({res.wd:.1f}) + {code.ll_factor}({i.ll:.1f}) = {res.wu:.1f} kg/m²",
        "",
        "## ความหนาต่ำสุด",
        f"- h,min = เส้นรอบรูป/180 = {res.h_min:.2f} cm → {status(res.h_ok)}",
        "",
        "## โมเมนต์และเหล็กเสริม (M = C·wu·S²)",
    ]
    for f in res.flexure_short + res.flexure_long:
        lines.append(
            f"- {f.label}: C = {res.coefs[f.label]:.4f}, Mu = {f.Mu:.1f} kg-m/m, d = {f.d:.2f} cm, "
            f"As,req = {f.As_design:.2f} cm²/m → **{f.callout}** {status(f.ok)}"
        )
    s = res.shear
    lines += [
        "",
        "## แรงเฉือน",
        f"- Vu = {s.Vu:.1f} kg/m, φVc = {s.phiVc:.1f} kg/m → {status(s.ok)}",
        "",
        "## น้ำหนักถ่ายลงคาน",
        f"- คานด้านสั้น (ยาว S): wu·S/3 = {res.beam_load_short_edge:.1f} kg/m",
        f"- คานด้านยาว (ยาว L): wu·S/3·(3−m²)/2 = {res.beam_load_long_edge:.1f} kg/m",
        *boq_markdown(boq),
        *(["", "## หมายเหตุ"] + [f"- {n}" for n in res.notes] if res.notes else []),
        "",
        f"**สรุป: {status(res.ok)}**",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- main
st.title("RC Slab Design")
st.caption("โปรแกรมออกแบบพื้นคอนกรีตเสริมเหล็ก · หน่วย: kg, cm, m, ksc")

if "schedule" not in st.session_state:
    st.session_state.schedule = {}  # mark -> schedule row dict


def natural_key(mark: str):
    return [int(s) if s.isdigit() else s for s in re.split(r"(\d+)", mark)]


def next_mark() -> str:
    n = 1
    while f"S{n}" in st.session_state.schedule:
        n += 1
    return f"S{n}"


def _save_row(row, bars: list[str], key: str) -> None:
    mark = st.session_state[f"{key}_mark"].strip()
    exists = mark in st.session_state.schedule
    d = row(mark).as_dict()
    d["_bars"] = bars
    st.session_state.schedule[mark] = d
    for k in ("ow", "tw"):  # both tabs move on to the next free mark
        st.session_state[f"{k}_mark"] = next_mark()
    st.toast(f"{'แทนที่' if exists else 'เพิ่ม'} {mark} ในตารางเหล็กพื้นแล้ว")


def add_to_schedule(row, bars: list[str], key: str) -> None:
    st.subheader("บันทึกลงตารางเหล็กพื้น")
    if f"{key}_mark" not in st.session_state:
        st.session_state[f"{key}_mark"] = next_mark()
    c = st.columns([1, 2, 3])
    mark = c[0].text_input("ชื่อพื้น (Mark)", key=f"{key}_mark").strip()
    c[1].write("")
    c[1].write("")
    c[1].button("➕ เพิ่ม/แทนที่ในตาราง", key=f"{key}_add", disabled=not mark, on_click=_save_row,
                args=(row, bars, key))
    c[2].caption("ใช้ชื่อเดิมเพื่อแทนที่แถวเดิม · ดูตารางทั้งหมดในแท็บ ตารางเหล็กพื้น")


def schedule_markdown(rows: list[dict]) -> str:
    keys = list(COLUMNS)
    lines = ["# ตารางเหล็กพื้น (Slab Schedule)", "", f"- มาตรฐาน: {code_name}", "",
             "| " + " | ".join(COLUMNS[k] for k in keys) + " |", "|" + "---|" * len(keys)]
    lines += ["| " + " | ".join(str(r[k]) for k in keys) + " |" for r in rows]
    bars = [b for r in rows for b in r["_bars"]]
    lines += ["", "## หมายเหตุ", *[f"- {n}" for n in schedule_notes(fc, grade, cover, bars)]]
    return "\n".join(lines)


tab1, tab2, tab4, tab3 = st.tabs(
    ["พื้นทางเดียว (One-way)", "พื้นสองทาง (Two-way)", "ตารางเหล็กพื้น", "ทฤษฎี / อ้างอิง"]
)

# ---------------- One-way
with tab1:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("รูปทรง")
        support = st.selectbox("เงื่อนไขการรองรับ", list(ONE_WAY_SUPPORTS), key="ow_sup")
        span = st.number_input("ช่วงพื้น L (m)", 0.5, 10.0, 3.0, 0.1, key="ow_L")
        h1 = st.number_input("ความหนาพื้น h (cm)", 8.0, 50.0, 15.0, 1.0, key="ow_h")
    with c2:
        st.subheader("น้ำหนักบรรทุก")
        sdl1 = st.number_input("SDL — วัสดุปูผิว/ฝ้า/งานระบบ (kg/m²)", 0.0, 2000.0, 100.0, 10.0, key="ow_sdl")
        ll1 = st.number_input("LL — น้ำหนักจร (kg/m²)", 0.0, 2000.0, 200.0, 10.0, key="ow_ll")
    with c3:
        st.subheader("เหล็กเสริม")
        main_bar = st.selectbox("ขนาดเหล็กเสริม", BAR_NAMES, index=BAR_NAMES.index("DB12"), key="ow_bar")
        st.caption("ใช้ขนาดเดียวทั้งแผ่น ทั้งเหล็กหลักและเหล็กกันร้าว")
    is_cant = ONE_WAY_SUPPORTS[support].name == "cantilever"
    with c1:
        width1 = st.number_input("ความกว้างแผ่นพื้น (ตั้งฉากกับช่วง) สำหรับ BOQ (m)", 0.5, 30.0, 4.0, 0.1,
                                 key="ow_W")
    with c2:
        p_end = 0.0
        if is_cant:
            p_end = st.number_input("น้ำหนักแนวเส้นที่ปลายพื้นยื่น P (kg/m) — เช่น ผนัง/ราวกันตก (DL)",
                                    0.0, 3000.0, 0.0, 10.0, key="ow_P")
        xi = st.selectbox("ระยะเวลาน้ำหนักค้าง (ξ)", [2.0, 1.4, 1.2, 1.0], key="ow_xi",
                          format_func=lambda v: {2.0: "≥ 5 ปี (ξ = 2.0)", 1.4: "12 เดือน (ξ = 1.4)",
                                                 1.2: "6 เดือน (ξ = 1.2)", 1.0: "3 เดือน (ξ = 1.0)"}[v])

    ow = design_one_way(
        OneWayInput(span, h1, support, sdl1, ll1, cover, main_bar, p_end, xi), conc, steel, code
    )
    ow_boq = one_way_boq(ow, width1, waste)
    st.divider()
    overall_banner(ow.ok)
    load_block(ow.sw, sdl1, ll1, ow.wd, ow.wu)

    c = st.columns(3)
    c[0].metric("h,min (ACI 9.5a)", f"{ow.h_min:.1f} cm", status(ow.h_ok), delta_color="off")
    c[1].metric("d", f"{ow.d:.2f} cm")
    c[2].metric("แรงเฉือน Vu/φVc", f"{ow.shear.ratio:.2f}", status(ow.shear.ok), delta_color="off",
                help=f"Vu = {ow.shear.Vu:,.0f} kg/m, φVc = {ow.shear.phiVc:,.0f} kg/m")

    st.subheader("เหล็กเสริม")
    st.dataframe(flexure_table(ow.flexure + [ow.temp]), hide_index=True, width="stretch")
    st.plotly_chart(one_way_moment_figure(ow), width="stretch")

    st.subheader("การแอ่นตัว (Deflection)")
    df = ow.deflection
    c = st.columns(4)
    c[0].metric("ΔL ทันที (LL)", f"{df.delta_L * 10:.2f} mm", f"≤ {df.limit_L * 10:.2f} mm · {status(df.ok_L)}",
                delta_color="off")
    c[1].metric("λΔD + ΔL (ระยะยาว)", f"{df.delta_long * 10:.2f} mm",
                f"≤ {df.limit_long * 10:.2f} mm · {status(df.ok_long)}", delta_color="off")
    c[2].metric("Ie (D+L)", f"{df.Ie_DL:,.0f} cm⁴", f"Ig = {df.Ig:,.0f}", delta_color="off")
    c[3].metric("Mcr / Ma(D+L)", f"{df.Mcr / df.Ma_DL:.2f}",
                "ไม่แตกร้าว" if df.Mcr >= df.Ma_DL else "แตกร้าว", delta_color="off")
    st.caption("เกณฑ์ ACI 318 Table 9.5(b): ΔL ≤ L/360 (พื้น), λΔD + ΔL ≤ L/240 (รองรับชิ้นส่วนที่ไม่เสียหายง่าย)")

    boq_section(ow_boq)
    for n in ow.notes:
        st.info(n)
    download_buttons(report_one_way(ow, ow_boq), "rc_slab_one_way")
    st.divider()
    add_to_schedule(lambda m: one_way_row(m, ow, width1), [main_bar], "ow")

# ---------------- Two-way
with tab2:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("รูปทรง")
        sx = st.number_input("ช่วงพื้นแนว X (m)", 1.0, 12.0, 4.0, 0.1, key="tw_x")
        sy = st.number_input("ช่วงพื้นแนว Y (m)", 1.0, 12.0, 5.0, 0.1, key="tw_y")
        h2 = st.number_input("ความหนาพื้น h (cm)", 8.0, 50.0, 12.0, 1.0, key="tw_h")
    with c2:
        st.subheader("น้ำหนักบรรทุก")
        sdl2 = st.number_input("SDL (kg/m²)", 0.0, 2000.0, 100.0, 10.0, key="tw_sdl")
        ll2 = st.number_input("LL (kg/m²)", 0.0, 2000.0, 200.0, 10.0, key="tw_ll")
        bar2 = st.selectbox("ขนาดเหล็กเสริม", BAR_NAMES, index=BAR_NAMES.index("DB12"), key="tw_bar")
        st.caption("ใช้ขนาดเดียวทั้งแผ่น")
    with c3:
        st.subheader("ความต่อเนื่องของขอบ")
        e1 = st.checkbox("ขอบ 1 (ซ้าย, ยาวตามแนว Y) ต่อเนื่อง", True)
        e2 = st.checkbox("ขอบ 2 (ขวา, ยาวตามแนว Y) ต่อเนื่อง", True)
        e3 = st.checkbox("ขอบ 3 (ล่าง, ยาวตามแนว X) ต่อเนื่อง", True)
        e4 = st.checkbox("ขอบ 4 (บน, ยาวตามแนว X) ต่อเนื่อง", True)

    # long_edge_* are edges of length = second span (Y); short_edge_* are edges of length = first span (X)
    tw = design_two_way(TwoWayInput(sx, sy, h2, sdl2, ll2, e1, e2, e3, e4, cover, bar2), conc, steel, code)
    tw_boq = two_way_boq(tw, waste)
    st.divider()
    if not tw.is_two_way:
        st.warning(f"m = S/L = {tw.m:.2f} < 0.5 → แผ่นพื้นทำงานแบบทางเดียว ให้ออกแบบในแท็บ One-way")
    overall_banner(tw.ok)
    load_block(tw.sw, sdl2, ll2, tw.wd, tw.wu)

    c = st.columns(4)
    c[0].metric("m = S/L", f"{tw.m:.3f}")
    c[1].metric("กรณี (Method 2)", f"Case {tw.case}")
    c[2].metric("h,min (P/180)", f"{tw.h_min:.1f} cm", status(tw.h_ok), delta_color="off")
    c[3].metric("แรงเฉือน Vu/φVc", f"{tw.shear.ratio:.2f}", status(tw.shear.ok), delta_color="off",
                help=f"Vu = {tw.shear.Vu:,.0f} kg/m, φVc = {tw.shear.phiVc:,.0f} kg/m")
    st.caption(CASE_NAMES[tw.case])

    left, right = st.columns([3, 2])
    with left:
        st.subheader("ช่วงสั้น (Short span, S = %.2f m, d = %.2f cm)" % (tw.S, tw.d_short))
        st.dataframe(flexure_table(tw.flexure_short), hide_index=True, width="stretch")
        st.subheader("ช่วงยาว (Long span, L = %.2f m, d = %.2f cm)" % (tw.L, tw.d_long))
        st.dataframe(flexure_table(tw.flexure_long), hide_index=True, width="stretch")
        st.dataframe(
            pd.DataFrame({"ตำแหน่ง": list(tw.coefs), "C": [round(v, 4) for v in tw.coefs.values()],
                          "Mu (kg-m/m)": [round(v, 1) for v in tw.moments.values()]}),
            hide_index=True,
            width="stretch",
        )
    with right:
        st.plotly_chart(two_way_plan_figure(tw), width="stretch")
        st.metric("น้ำหนักลงคานด้านสั้น (wS/3)", f"{tw.beam_load_short_edge:,.0f} kg/m")
        st.metric("น้ำหนักลงคานด้านยาว (wS/3·(3−m²)/2)", f"{tw.beam_load_long_edge:,.0f} kg/m")
    for n in tw.notes:
        st.info(n)
    boq_section(tw_boq)
    download_buttons(report_two_way(tw, tw_boq), "rc_slab_two_way")
    st.divider()
    add_to_schedule(lambda m: two_way_row(m, tw), [bar2], "tw")

# ---------------- Slab schedule
with tab4:
    st.subheader("ตารางเหล็กพื้น (Slab Schedule)")
    rows = [st.session_state.schedule[k] for k in sorted(st.session_state.schedule, key=natural_key)]
    if not rows:
        st.info("ยังไม่มีรายการ ออกแบบพื้นในแท็บพื้นทางเดียวหรือพื้นสองทาง แล้วกด เพิ่ม/แทนที่ในตาราง")
    else:
        df = pd.DataFrame([{COLUMNS[k]: r[k] for k in COLUMNS} | {"สถานะ": status(r["ok"])} for r in rows])
        st.dataframe(df, hide_index=True, width="stretch")
        if not all(r["ok"] for r in rows):
            st.warning("มีพื้นที่ผลการออกแบบไม่ผ่าน ตรวจสอบก่อนนำไปใช้ในแบบ")
        st.markdown("**หมายเหตุสำหรับแบบ**")
        for n in schedule_notes(fc, grade, cover, [b for r in rows for b in r["_bars"]]):
            st.markdown(f"- {n}")
        md = schedule_markdown(rows)
        csv = df.drop(columns="สถานะ").to_csv(index=False).encode("utf-8-sig")
        c = st.columns([1, 1, 1, 2])
        c[0].download_button("📊 Excel (.csv)", csv, "slab_schedule.csv", "text/csv")
        c[1].download_button("🖨️ PDF (A4 แนวนอน)", to_pdf(md, landscape=True, col_widths=PDF_COL_WIDTHS), "slab_schedule.pdf", "application/pdf")
        c[2].download_button("📄 Markdown", md, "slab_schedule.md", "text/markdown")
        with st.expander("ลบรายการ"):
            drop = st.multiselect("เลือกพื้นที่จะลบ", [r["mark"] for r in rows])
            d1, d2 = st.columns(2)
            if d1.button("ลบที่เลือก", disabled=not drop):
                for m in drop:
                    st.session_state.schedule.pop(m, None)
                st.rerun()
            if d2.button("ล้างตารางทั้งหมด"):
                st.session_state.schedule = {}
                st.rerun()

# ---------------- Theory
with tab3:
    st.markdown(
        r"""
### หลักการออกแบบ (Strength Design Method)

**น้ำหนักบรรทุกประลัย** $w_u = \alpha_D (SW + SDL) + \alpha_L LL$ คิดต่อแถบกว้าง 1 m

**ออกแบบรับแรงดัด**

$$R_n = \frac{M_u}{\phi b d^2}, \qquad
\rho = \frac{0.85 f'_c}{f_y}\left(1-\sqrt{1-\frac{2R_n}{0.85 f'_c}}\right)$$

- $A_{s,min} = \rho_{temp}\, b\, h$ : 0.0020 (SR24, SD30), 0.0018 (SD40), $0.0018\times4000/f_y \ge 0.0014$ (fy > 4000)
- $\rho \le \rho_{max} = 0.75\rho_b$, $\rho_b = \dfrac{0.85\beta_1 f'_c}{f_y}\dfrac{6120}{6120+f_y}$
- ระยะห่างเหล็กหลัก ≤ 3h, เหล็กกันร้าว ≤ 5h และทุกตำแหน่ง ≤ 30 cm (ข้อกำหนดสำนักงาน; ACI ยอมให้ถึง 45 cm)

**ตรวจสอบแรงเฉือน** $\phi V_c = \phi \cdot 0.53\sqrt{f'_c}\, b\, d$ (ksc)

### พื้นทางเดียว — ACI approximate coefficients
| เงื่อนไข | h,min | +M | −M |
|---|---|---|---|
| Simply supported | L/20 | wL²/8 | wL²/24 ที่ขอบ (เหล็กบนควบคุมรอยร้าว) |
| One end continuous (> 2 ช่วง) | L/24 | wL²/11 | wL²/10 (ภายใน), wL²/24 (ริม) |
| One end continuous (2 ช่วง) | L/24 | wL²/11 | wL²/9 (ภายใน), wL²/24 (ริม) |
| Both ends continuous | L/28 | wL²/16 | wL²/11 |
| Cantilever | L/10 | — | wL²/2 + P·L |

h,min คูณด้วย (0.4 + fy/7000) สำหรับ fy ในหน่วย ksc

### การแอ่นตัว (พื้นทางเดียว)
- $I_e = (M_{cr}/M_a)^3 I_g + [1-(M_{cr}/M_a)^3] I_{cr} \le I_g$, $M_{cr} = f_r I_g / y_t$, $f_r = 2\sqrt{f'_c}$
- $\Delta = w L^4 / (k E_c I_e)$ : k = 384/5 (ช่วงเดียว), 185 (ต่อเนื่องปลายเดียว), 384 (ต่อเนื่องสองปลาย), 8 (พื้นยื่น, + $PL^3/3EI$)
- ระยะยาว $\lambda = \xi/(1+50\rho')$; ตรวจ $\Delta_L \le L/360$ และ $\lambda\Delta_D + \Delta_L \le L/240$ (พื้นยื่นใช้ 2L)
- ถ้า h < h,min แต่การแอ่นตัวผ่านเกณฑ์ ถือว่าใช้ได้ (ACI 9.5.2)

### ปริมาณวัสดุ (BOQ)
- เหล็กล่างยาวเต็มช่วง + ฝัง 0.10 m แต่ละปลาย; เหล็กบนยื่น 0.3 × ช่วง (สองทาง: 0.3S) + 0.15 m
- เหล็กบนพื้นยื่นยาว 2L (ยื่น L + ยึดฝังช่วงใน L); น้ำหนักเหล็ก 0.785 kg/m ต่อ 1 cm² และเผื่อระยะทาบ/เศษตามที่กำหนด

### พื้นสองทาง — ACI 318-63 Method 2
- $m = S/L \ge 0.5$; $M = C\,w_u\,S^2$ (แถบกลาง) — แถบเสาใช้ 2/3 ของแถบกลาง
- สัมประสิทธิ์ C ตาม Case 1–5 (จำนวนขอบไม่ต่อเนื่อง) ประมาณค่าเชิงเส้นตาม m
- ช่วงยาวใช้ค่า C ที่ m = 1.0 เสมอ
- ความหนาต่ำสุด ≥ เส้นรอบรูป/180 และ ≥ 9 cm
- เหล็กช่วงยาววางชั้นใน: $d_L = d_S - d_b$
- น้ำหนักลงคาน: ด้านสั้น $w S/3$, ด้านยาว $\dfrac{wS}{3}\dfrac{3-m^2}{2}$

> ⚠️ โปรแกรมนี้เป็นเครื่องมือช่วยคำนวณเบื้องต้น ผลลัพธ์ต้องได้รับการตรวจสอบและรับรองโดยวิศวกรโยธาผู้มีใบอนุญาต
"""
    )
