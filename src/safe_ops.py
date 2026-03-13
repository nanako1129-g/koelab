from typing import List, Dict, Optional
from src.analyze import classify_records
from src.propose import generate_proposal

FALLBACK_THEMES_KEYWORDS = {
    "交通": ["交通", "バス", "車", "道路", "通勤", "運転", "電車", "駐車"],
    "医療": ["医療", "病院", "医者", "健康", "診療", "通院", "クリニック"],
    "賃金・雇用": ["賃金", "給料", "雇用", "仕事", "就職", "働", "昇進", "格差", "製造", "正社員", "パート", "収入", "所得"],
    "子育て": ["子育て", "保育", "子ども", "育児", "子供", "幼稚園", "保育園", "産休", "育休"],
    "ジェンダー": ["ジェンダー", "男女", "女性", "性別", "嫁", "家事", "夫婦", "妻", "セクハラ", "差別"],
    "広聴・参加": ["参加", "意見", "広聴", "市民", "アンケート", "声", "要望"],
    "住宅・家賃": ["住宅", "家賃", "住まい", "アパート", "空き家", "持ち家"],
    "教育": ["教育", "学校", "学習", "進学", "塾", "大学"],
    "娯楽・余暇": ["娯楽", "遊び", "施設", "レジャー", "公園", "イベント", "映画"],
    "福祉": ["福祉", "介護", "高齢", "障害", "年金", "老人", "デイサービス"],
    "行政DX": ["DX", "デジタル", "オンライン", "IT", "マイナンバー", "電子"],
    "コミュニティ": ["地域", "町内", "自治会", "近所", "ボランティア", "祭り"]
}


def _rule_classify(record: Dict) -> Dict:
    text = record.get("text", "")
    themes = []
    for theme, keywords in FALLBACK_THEMES_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            themes.append(theme)
        if len(themes) >= 2:
            break
    labels = []
    if any(w in text for w in ["ほしい", "必要", "不足", "ない"]):
        labels.append("課題")
    if any(w in text for w in ["べき", "したら", "提案"]):
        labels.append("提案")
    if not labels:
        labels = ["課題"]
    return {
        "source_id": record["source_id"],
        "labels": labels,
        "themes": themes or ["コミュニティ"],
        "stance": "中立",
        "summary": text[:60],
        "quote": text[:100],
        "confidence": 0.35
    }


def classify_records_safe(records: List[Dict]) -> List[Dict]:
    try:
        return classify_records(records)
    except Exception as e:
        print(f"Gemini classification failed, using rule-based: {e}")
        return [_rule_classify(r) for r in records]


def _build_fallback_template(bucket: str, evidence: List[Dict],
                              source_name: Optional[str] = None) -> Dict:
    area = source_name or "対象地域"

    if bucket == "A":
        return {
            "title": "暮らし課題解決パッケージ",
            "target_themes": ["交通", "医療"],
            "problem": f"{area}の市民アンケートで交通・医療へのアクセス困難が多数報告",
            "solution": "デマンド交通の拡充とオンライン診療の導入支援",
            "scope": f"{area}全域（特に中山間部）",
            "budget_range_yen": "3,000万〜6,000万",
            "schedule": [{"phase": "調査・設計", "period": "6ヶ月"},
                         {"phase": "実証実験", "period": "1年"},
                         {"phase": "本格運用", "period": "2年目〜"}],
            "kpi": [{"metric": "利用者数", "target": "月500人"},
                    {"metric": "満足度", "target": "70%以上"}],
            "risks": [{"risk": "利用率低迷", "mitigation": "広報強化・無料体験期間"}],
            "evidence_source_ids": [e["source_id"] for e in evidence[:3]]
        }
    else:
        return {
            "title": "市民参加・広聴DX推進事業",
            "target_themes": ["広聴・参加", "ジェンダー"],
            "problem": f"{area}の市政への参加機会が限定的でジェンダーギャップの声が届きにくい",
            "solution": "オンライン広聴プラットフォーム導入と多様な声の可視化",
            "scope": f"{area}全域",
            "budget_range_yen": "800万〜2,000万",
            "schedule": [{"phase": "要件定義", "period": "3ヶ月"},
                         {"phase": "開発・テスト", "period": "6ヶ月"},
                         {"phase": "運用開始", "period": "1年目〜"}],
            "kpi": [{"metric": "投稿数", "target": "月100件"},
                    {"metric": "女性参加率", "target": "50%以上"}],
            "risks": [{"risk": "デジタル格差", "mitigation": "紙・対面との併用"}],
            "evidence_source_ids": [e["source_id"] for e in evidence[:3]]
        }


def generate_proposal_safe(bucket: str, evidence: List[Dict],
                            source_name: Optional[str] = None) -> Dict:
    try:
        return generate_proposal(bucket, evidence)
    except Exception as e:
        print(f"Gemini proposal failed, using template: {e}")
        return _build_fallback_template(bucket, evidence, source_name)
