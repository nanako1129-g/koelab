import csv
import json
from pathlib import Path
from src.safe_ops import classify_records_safe, generate_proposal_safe
from src.evidence_select import pick_evidence
from src.report_md import build_demo_report_md
from src.export_pdf import md_to_simple_pdf

APP_DIR = Path(__file__).resolve().parent
FONT_PATH = (APP_DIR / "fonts" / "ipaexg.ttf").as_posix()

# 1. CSV読み込み
rows = list(csv.DictReader(open('data/shiojiri_demo.csv', encoding='utf-8')))
records = [
    {
        'source_id': f'shiojiri_demo_{r["id"]}',
        'page': 0,
        'question_id': 'FREE',
        'text': r['text']
    }
    for r in rows
]
print(f"{len(records)}件読み込み")

# 2. 分類
classified = classify_records_safe(records)
print(f"{len(classified)}件分類完了")

# 3. エビデンス選定
evi_a = pick_evidence(records, classified, bucket="A", k=5)
evi_b = pick_evidence(records, classified, bucket="B", k=5)
print("エビデンス選定完了")

# 4. 提案生成
proposal_a = generate_proposal_safe("A", evi_a)
proposal_b = generate_proposal_safe("B", evi_b)
print("提案生成完了")

# 5. レポート作成
md = build_demo_report_md(records, classified, proposal_a, proposal_b)
out_dir = Path("outputs/shiojiri_demo")
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "report.md").write_text(md, encoding="utf-8")
pdf_out = out_dir / "report.pdf"
md_to_simple_pdf(md, str(pdf_out), font_path=FONT_PATH)
print(f"完了！ {pdf_out}")
