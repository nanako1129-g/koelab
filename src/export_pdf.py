from fpdf import FPDF
from pathlib import Path


def md_to_simple_pdf(md_text: str, out_path: str,
                     font_path: str = "fonts/ipaexg.ttf") -> None:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    if Path(font_path).exists():
        pdf.add_font("JP", "", font_path)
        font_name = "JP"
    else:
        font_name = "Helvetica"

    pdf.add_page()

    for line in md_text.split("\n"):
        stripped = line.strip()
        pdf.set_x(pdf.l_margin)

        if stripped == "":
            pdf.ln(5)
            continue

        if stripped.startswith("# ") and not stripped.startswith("## "):
            pdf.set_font(font_name, "", 16)
            pdf.multi_cell(0, 10, stripped[2:])
            pdf.ln(4)
        elif stripped.startswith("## "):
            pdf.set_font(font_name, "", 14)
            pdf.multi_cell(0, 9, stripped[3:])
            pdf.ln(3)
        elif stripped.startswith("### "):
            pdf.set_font(font_name, "", 12)
            pdf.multi_cell(0, 8, stripped[4:])
            pdf.ln(2)
        elif stripped.startswith("> "):
            pdf.set_font(font_name, "", 9)
            pdf.set_x(pdf.l_margin + 5)
            pdf.multi_cell(0, 6, stripped[2:])
        elif stripped.startswith("- "):
            pdf.set_font(font_name, "", 10)
            pdf.multi_cell(0, 7, "\u2022 " + stripped[2:])
        elif stripped == "---":
            pdf.ln(3)
            y = pdf.get_y()
            pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
            pdf.ln(3)
        else:
            pdf.set_font(font_name, "", 10)
            pdf.multi_cell(0, 7, stripped)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    pdf.output(out_path)
