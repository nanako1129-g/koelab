import os
import json
from typing import List, Dict
from pathlib import Path
from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential

# .env から読み込み
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

GEMINI_MODEL = "gemini-3-flash-preview"

PROPOSAL_PROMPT = """あなたは自治体の新規事業企画官です。以下の市民の声（エビデンス）に基づき、新規事業提案を1つ作成してください。

【バケット】{bucket_label}
【エビデンス】
{evidence_json}

【出力JSON形式】
{{
  "title": "事業名（20字以内）",
  "target_themes": ["テーマ1", "テーマ2"],
  "problem": "課題の要約（100字以内）",
  "solution": "施策概要（150字以内）",
  "scope": "対象範囲（50字以内）",
  "budget_range_yen": "予算レンジ（例: 2000万〜8000万）",
  "schedule": [{{"phase": "フェーズ名", "period": "期間"}}],
  "kpi": [{{"metric": "指標", "target": "目標値"}}],
  "risks": [{{"risk": "リスク", "mitigation": "対策"}}],
  "evidence_source_ids": ["使用したエビデンスのsource_id"]
}}

【ルール】
- evidence_source_idsは入力エビデンスのsource_idのみ使用
- 根拠のない提案は禁止
- 予算は現実的な範囲で
- 予算参考レンジ（バケットA: 暮らし課題系）: 2,000万〜1億円（交通改善・医療拠点整備等）
- 予算参考レンジ（バケットB: 参加・広聴系）: 500万〜3,000万円（DXツール導入・市民参加制度設計等）
- 気仙沼市の一般会計は約458億円、人口約6万人の地方都市であることを考慮
- スケジュールは準備期間6ヶ月〜1年、実施1〜3年が現実的
"""

BUCKET_LABELS = {
    "A": "暮らし課題系（交通・医療・賃金・住宅・子育て等）",
    "B": "参加・ジェンダー・広聴設計系"
}


def _build_proposal_prompt(bucket: str, evidence: List[Dict]) -> str:
    evi = [{"source_id": e["source_id"], "themes": e.get("themes", []),
            "summary": e.get("summary", ""), "text": e.get("text", "")}
           for e in evidence]
    return PROPOSAL_PROMPT.format(
        bucket_label=BUCKET_LABELS.get(bucket, bucket),
        evidence_json=json.dumps(evi, ensure_ascii=False, indent=2)
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
def generate_proposal(bucket: str, evidence: List[Dict]) -> Dict:
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY が未設定です")
    client = genai.Client(api_key=api_key)
    prompt = _build_proposal_prompt(bucket, evidence)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={"response_mime_type": "application/json"}
    )
    return json.loads(response.text.strip())
