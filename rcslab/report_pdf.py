"""Render the Markdown calculation report to PDF (Thai font: Sarabun, OFL)."""

from pathlib import Path
import re

from fpdf import FPDF
from fpdf.fonts import FontFace

FONT_DIR = Path(__file__).parent / "fonts"

# Sarabun has no Greek or emoji glyphs
REPLACEMENTS = {
    "φ": "phi",
    "ρ": "rho",
    "β": "beta",
    "λ": "lambda",
    "ξ": "xi",
    "Δ": "delta ",
    "✅": "[OK]",
    "❌": "[NG]",
    "⚠️": "!",
    "⚠": "!",
}


def _clean(text: str) -> str:
    for a, b in REPLACEMENTS.items():
        text = text.replace(a, b)
    return text


class _PDF(FPDF):
    title_text = "RC Slab Design"

    def header(self) -> None:
        self.set_font("Sarabun", "", 9)
        self.set_text_color(110)
        self.cell(0, 6, f"{self.title_text} — รายการคำนวณ", align="L")
        self.ln(8)
        self.set_text_color(0)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Sarabun", "", 9)
        self.set_text_color(110)
        self.cell(0, 6, f"หน้า {self.page_no()}/{{nb}}", align="C")


def _table(pdf: FPDF, rows: list[str], font_size: float = 9, col_widths: tuple | None = None) -> None:
    cells = [[_clean(c.strip()) for c in r.strip().strip("|").split("|")] for r in rows]
    cells = [r for r in cells if not all(re.fullmatch(r":?-+:?", c) for c in r)]
    pdf.set_font("Sarabun", "", font_size)
    with pdf.table(
        headings_style=FontFace(emphasis="BOLD", fill_color=(235, 238, 245)),
        line_height=5.5,
        text_align="LEFT",
        padding=1,
        col_widths=col_widths if col_widths and len(col_widths) == len(cells[0]) else None,
    ) as table:
        for r in cells:
            row = table.row()
            for c in r:
                row.cell(c.replace("**", ""))
    pdf.ln(2)


def markdown_to_pdf(md: str, landscape: bool = False, table_font: float = 9, col_widths: tuple | None = None) -> bytes:
    pdf = _PDF(orientation="L" if landscape else "P", format="A4")
    pdf.add_font("Sarabun", "", FONT_DIR / "Sarabun-Regular.ttf")
    pdf.add_font("Sarabun", "B", FONT_DIR / "Sarabun-Bold.ttf")
    pdf.set_text_shaping(True)
    pdf.set_margins(18, 15, 18)
    pdf.set_auto_page_break(True, 18)
    pdf.add_page()

    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                block.append(lines[i])
                i += 1
            _table(pdf, block, table_font, col_widths)
            continue
        text = _clean(line)
        if text.startswith("# "):
            pdf.set_font("Sarabun", "B", 16)
            pdf.multi_cell(0, 8, text[2:])
            pdf.ln(2)
        elif text.startswith("## "):
            pdf.ln(2)
            pdf.set_font("Sarabun", "B", 12.5)
            pdf.set_text_color(29, 78, 216)
            pdf.multi_cell(0, 7, text[3:])
            pdf.set_text_color(0)
        elif text.startswith("- "):
            pdf.set_font("Sarabun", "", 10.5)
            pdf.set_x(pdf.l_margin + 3)
            pdf.multi_cell(0, 5.8, "•  " + text[2:], markdown=True, align="L")
        elif text.strip():
            pdf.set_font("Sarabun", "", 10.5)
            pdf.multi_cell(0, 5.8, text, markdown=True, align="L")
        else:
            pdf.ln(2)
        i += 1
    return bytes(pdf.output())
