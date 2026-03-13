from src.ingest_pdf import extract_free_text_records
from src.demo_select import select_demo_records_balanced
from src.safe_ops import _rule_classify
from src.evidence_select import pick_evidence, BUCKET_B_THEMES

records = extract_free_text_records('data/kesennuma.pdf')
demo = select_demo_records_balanced(records, n_each=10)

# Geminiを飛ばして直接_rule_classifyで分類
classified = [_rule_classify(r) for r in demo]

print("テーマ確認:")
for c in classified[:3]:
    print(f"  {c['themes']}")

evi_a = pick_evidence(demo, classified, bucket='A', k=5)
evi_b = pick_evidence(demo, classified, bucket='B', k=5)
print(f"\nエビA: {len(evi_a)} エビB: {len(evi_b)}")
