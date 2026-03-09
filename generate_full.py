"""フル版（全29件）レポートを事前生成するスクリプト"""
import hashlib
from pathlib import Path
from collections import Counter
from src.ingest_pdf import extract_free_text_records
from src.safe_ops import classify_records_safe, generate_proposal_safe
from src.evidence_select import pick_evidence
from src.report_md import build_demo_report_md
from src.export_pdf import md_to_simple_pdf

PDF_PATH = "data/kesennuma.pdf"
APP_DIR = Path(__file__).resolve().parent
FONT_PATH = (APP_DIR / "fonts" / "ipaexg.ttf").as_posix()
OUTPUTS_DIR = Path("outputs")

def sha16(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]

def main():
    pdf_bytes = Path(PDF_PATH).read_bytes()
    key = sha16(pdf_bytes)
    dataset_id = f"kesennuma_{key}"
    out_dir = OUTPUTS_DIR / key
    out_dir.mkdir(parents=True, exist_ok=True)

    print("PDF読み込み中...")
    records = extract_free_text_records(PDF_PATH, dataset_id=dataset_id)
    print(f"抽出完了: {len(records)}件")

    print("AI分類中...")
    classified = classify_records_safe(records)
    print(f"分類完了: {len(classified)}件")

    print("エビデンス選定中...")
    evi_a = pick_evidence(records, classified, bucket="A", k=5)
    evi_b = pick_evidence(records, classified, bucket="B", k=5)

    print("提案生成中...")
    proposal_a = generate_proposal_safe("A", evi_a)
    proposal_b = generate_proposal_safe("B", evi_b)

    print("レポート作成中...")
    md = build_demo_report_md(records, classified, proposal_a, proposal_b)
    (out_dir / "full_report.md").write_text(md, encoding="utf-8")

    pdf_out = out_dir / "full_report.pdf"
    md_to_simple_pdf(md, str(pdf_out), font_path=FONT_PATH)
    print(f"完了！ {pdf_out}")

if __name__ == "__main__":
    main()
