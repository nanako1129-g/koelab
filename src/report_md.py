import re
from typing import List, Dict, Optional
from collections import Counter
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))


def _guess_source_name(records: List[Dict]) -> Optional[str]:
    """レコードのテキストから自治体名を推定"""
    city_pattern = re.compile(r'([\u4e00-\u9fff]{1,4}[市町村区])')
    counts = Counter()
    for r in records:
        matches = city_pattern.findall(r.get("text", ""))
        for m in matches:
            counts[m] += 1
    if counts:
        return counts.most_common(1)[0][0]
    return None


def build_demo_report_md(records: List[Dict], classified: List[Dict],
                         proposal_a: Dict, proposal_b: Dict,
                         source_name: Optional[str] = None) -> str:
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")

    # --- 自治体名の推定（明示指定 > ファイル名推定 > レコード本文推定 > フォールバック） ---
    if not source_name:
        # ファイル名から推定（source_id が "shiojiri_demo_1" のような形式）
        first_sid = records[0].get("source_id", "") if records else ""
        basename = first_sid.rsplit("_", 1)[0] if "_" in first_sid else ""
        city_pat = re.compile(r'([\u4e00-\u9fff]{1,4}[市町村区])')
        m = city_pat.search(basename)
        if m:
            source_name = m.group(1)
    if not source_name:
        source_name = _guess_source_name(records)
    if not source_name:
        source_name = "アップロードデータ"

    # --- Q21/Q28 カウント（CSVの場合はFREEなので分けない） ---
    n_q21 = sum(1 for r in records if r.get("question_id") == "Q21")
    n_q28 = sum(1 for r in records if r.get("question_id") == "Q28")
    has_questions = (n_q21 + n_q28) > 0

    # --- 声番号マッピング ---
    voice_map = {}
    for i, r in enumerate(records, 1):
        voice_map[r["source_id"]] = f"声{i:03d}"

    theme_counter = Counter()
    label_counter = Counter()
    for c in classified:
        for t in c.get("themes", []):
            theme_counter[t] += 1
        for l in c.get("labels", []):
            label_counter[l] += 1

    # --- レポートタイトルに自治体名を入れる ---
    md = f"""# {source_name} こえラボ 分析レポート

生成日時: {now}

## 1. データ概要

- 分析対象: {source_name}
"""
    if has_questions:
        md += f"- 抽出件数: {len(records)}件（Q21: {n_q21}件 / Q28: {n_q28}件）\n"
    else:
        md += f"- 抽出件数: {len(records)}件（自由記述）\n"

    md += "\n## 2. テーマ分布\n\n"
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
                vid = voice_map.get(c.get("source_id", ""), c.get("source_id", ""))
                md += f"「{quote}」（{vid}）\n\n"
                shown += 1

    md += _proposal_section("A", proposal_a, classified, voice_map)
    md += _proposal_section("B", proposal_b, classified, voice_map)

    # --- 引用元一覧（声番号 + 原文 + ページ） ---
    md += "\n## 7. 引用元一覧\n\n"
    md += "| 声番号 | source_id | ページ | 原文（抜粋） |\n"
    md += "|--------|-----------|--------|-------------|\n"
    for r in records:
        vid = voice_map.get(r["source_id"], "?")
        text = r["text"][:60].replace("\n", " ").replace("|", "｜")
        page = r.get("page", "?")
        md += f"| {vid} | {r['source_id']} | p.{page} | {text} |\n"

    md += f"\n---\nこえラボ プロトタイプ | 生成日時: {now}\n"
    return md


def _proposal_section(bucket: str, proposal: Dict,
                      classified: List[Dict], voice_map: Dict) -> str:
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
        vid = voice_map.get(sid, sid)
        for c in classified:
            if c.get("source_id") == sid:
                text = c.get("summary", "").replace("\n", " ")[:80]
                md += f"- {vid}（{sid}）: {text}\n"
                break

    return md
