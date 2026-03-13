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

        # --- テーブル行 ---
        if stripped.startswith("| ") and "|" in stripped[1:]:
            cols = [c.strip() for c in stripped.split("|")[1:-1]]
            if not cols:
                continue
            col_width = (pdf.w - pdf.l_margin - pdf.r_margin) / len(cols)
            pdf.set_font(font_name, "", 8)
            row_height = 7
            # 長いセルに対応：最大行数を計算
            max_lines = 1
            for col in cols:
                cell_text_width = pdf.get_string_width(col) + 2
                if cell_text_width > col_width:
                    max_lines = max(max_lines, int(cell_text_width / col_width) + 1)
            cell_height = row_height * max_lines

            x_start = pdf.get_x()
            y_start = pdf.get_y()

            # ページ跨ぎチェック
            if y_start + cell_height > pdf.h - pdf.b_margin:
                pdf.add_page()
                y_start = pdf.get_y()

            for col in cols:
                x_before = pdf.get_x()
                # 枠線を描画
                pdf.rect(x_before, y_start, col_width, cell_height)
                # テキストを描画
                pdf.set_xy(x_before + 1, y_start + 1)
                pdf.multi_cell(col_width - 2, row_height, col, border=0)
                # 次のセルへ
                pdf.set_xy(x_before + col_width, y_start)

            pdf.set_xy(pdf.l_margin, y_start + cell_height)
            continue

        # --- セパレータ行（|---|---|---| 等）スキップ ---
        if stripped.startswith("|") and set(stripped.replace("|", "").replace("-", "").replace(":", "").strip()) == set():
            continue

        # --- 見出し ---
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

        # --- 引用 ---
        elif stripped.startswith("> "):
            pdf.set_font(font_name, "", 9)
            pdf.set_x(pdf.l_margin + 5)
            pdf.multi_cell(0, 6, stripped[2:])

        # --- リスト ---
        elif stripped.startswith("- "):
            pdf.set_font(font_name, "", 10)
            pdf.multi_cell(0, 7, "\u2022 " + stripped[2:])

        # --- 水平線 ---
        elif stripped == "---":
            pdf.ln(3)
            y = pdf.get_y()
            pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
            pdf.ln(3)

        # --- 通常テキスト ---
        else:
            pdf.set_font(font_name, "", 10)
            pdf.multi_cell(0, 7, stripped)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    pdf.output(out_path)
