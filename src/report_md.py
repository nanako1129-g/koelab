from typing import List, Dict
from collections import Counter
from datetime import datetime


def build_demo_report_md(records: List[Dict], classified: List[Dict],
                         proposal_a: Dict, proposal_b: Dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    n_q21 = sum(1 for r in records if r.get("question_id") == "Q21")
    n_q28 = sum(1 for r in records if r.get("question_id") == "Q28")

    theme_counter = Counter()
    label_counter = Counter()
    for c in classified:
        for t in c.get("themes", []):
            theme_counter[t] += 1
        for l in c.get("labels", []):
            label_counter[l] += 1

    md = f"""# こえラボ 分析レポート（デモ20件版）

生成日時: {now}

## 1. データ概要

- 分析対象: 気仙沼市Well-beingアンケート
- 抽出件数: {len(records)}件（Q21: {n_q21}件 / Q28: {n_q28}件）

## 2. テーマ分布

"""
    for theme, count in theme_counter.most_common():
        md += f"- {theme}: {count}件\n"

    md += "\n## 3. ラベル分布\n\n"
    for label, count in label_counter.most_common():
        md += f"- {label}: {count}件\n"

    md += "\n## 4. 代表的な市民の声\n"
    top_themes = [t for t, _ in theme_counter.most_common(3)]
    for theme in top_themes:
        md += f"\n### {theme}\n\n"
        shown = 0
        for c in classified:
            if theme in c.get("themes", []) and shown < 2:
                quote = c.get("quote", c.get("summary", ""))
                sid = c.get("source_id", "")
                md += f"「{quote}」（{sid}）\n\n"
                shown += 1

    md += _proposal_section("A", proposal_a, classified)
    md += _proposal_section("B", proposal_b, classified)

    md += "\n## 7. 引用一覧\n\n"
    for r in records:
        text = r["text"][:80].replace("\n", " ")
        md += f"- {r['source_id']}（p.{r.get('page', '?')}）: {text}\n"

    md += f"\n---\nこえラボ プロトタイプ | 生成日時: {now}\n"
    return md


def _proposal_section(bucket: str, proposal: Dict, classified: List[Dict]) -> str:
    num = "5" if bucket == "A" else "6"
    md = f"\n## {num}. 提案{bucket}: {proposal.get('title', '')}\n\n"
    md += f"- 対象テーマ: {', '.join(proposal.get('target_themes', []))}\n"
    md += f"- 課題: {proposal.get('problem', '')}\n"
    md += f"- 施策: {proposal.get('solution', '')}\n"
    md += f"- 対象範囲: {proposal.get('scope', '')}\n"
    md += f"- 概算予算: {proposal.get('budget_range_yen', '')}\n"

    md += "\n### スケジュール\n\n"
    for s in proposal.get("schedule", []):
        md += f"- {s.get('phase', '')}: {s.get('period', '')}\n"

    md += "\n### KPI\n\n"
    for k in proposal.get("kpi", []):
        md += f"- {k.get('metric', '')}: {k.get('target', '')}\n"

    md += "\n### リスクと対策\n\n"
    for r in proposal.get("risks", []):
        md += f"- {r.get('risk', '')} → {r.get('mitigation', '')}\n"

    md += "\n### エビデンス（出典）\n\n"
    for sid in proposal.get("evidence_source_ids", []):
        for c in classified:
            if c.get("source_id") == sid:
                text = c.get("summary", "").replace("\n", " ")[:80]
                md += f"- {sid}: {text}\n"
                break

    return md
