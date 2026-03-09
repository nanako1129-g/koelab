import os

from src.ingest_pdf import extract_free_text_records
from src.demo_select import select_demo_records_balanced
from src.safe_ops import classify_records_safe, generate_proposal_safe
from src.evidence_select import pick_evidence
from src.report_md import build_demo_report_md
from src.export_pdf import md_to_simple_pdf

records = extract_free_text_records("data/kesennuma.pdf", dataset_id="kesennuma_debug")
demo = select_demo_records_balanced(records, n_each=10)
print("分類中...")
classified = classify_records_safe(demo)
for c in classified[:3]:
    print(f"  {c['source_id']}: {c['themes']} conf={c['confidence']}")
evi_a = pick_evidence(demo, classified, bucket="A", k=5)
evi_b = pick_evidence(demo, classified, bucket="B", k=5)
print("提案A生成中...")
proposal_a = generate_proposal_safe("A", evi_a)
print(f"  提案A: {proposal_a.get('title', '?')}")
print("提案B生成中...")
proposal_b = generate_proposal_safe("B", evi_b)
print(f"  提案B: {proposal_b.get('title', '?')}")
md = build_demo_report_md(demo, classified, proposal_a, proposal_b)
md_to_simple_pdf(md, "outputs/debug_full.pdf")
print("全パイプライン完了！ outputs/debug_full.pdf")
