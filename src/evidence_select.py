from typing import List, Dict

BUCKET_A_THEMES = {"交通", "医療", "福祉", "賃金・雇用", "子育て", "住宅・家賃",
                   "教育", "娯楽・余暇", "コミュニティ", "防災", "移住・定住", "産業・企業誘致"}

BUCKET_B_THEMES = {"ジェンダー", "広聴・参加", "行政DX", "広報・SNS"}


def pick_evidence(records: List[Dict], classified: List[Dict],
                  bucket: str = "A", k: int = 5) -> List[Dict]:
    themes = BUCKET_A_THEMES if bucket == "A" else BUCKET_B_THEMES

    scored = []
    for i, (r, c) in enumerate(zip(records, classified)):
        c_themes = set(c.get("themes", []))
        if not c_themes & themes:
            continue
        score = c.get("confidence", 0.0)
        if "課題" in c.get("labels", []):
            score += 0.2
        if "提案" in c.get("labels", []):
            score += 0.15
        scored.append({**r, **c, "_score": score})

    scored.sort(key=lambda x: x["_score"], reverse=True)
    picked = scored[:k]
    return [{k2: v for k2, v in p.items() if k2 != "_score"} for p in picked]
