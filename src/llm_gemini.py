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

GEMINI_MODEL =  "gemini-3.1-flash-lite-preview"

THEMES = [
    "交通", "医療", "福祉", "賃金・雇用", "住宅・家賃",
    "子育て", "教育", "娯楽・余暇", "防災", "広聴・参加",
    "行政DX", "ジェンダー", "コミュニティ", "産業・企業誘致",
    "移住・定住", "広報・SNS"
]

CLASSIFY_PROMPT = """あなたは自治体の政策分析官です。以下の市民コメント一覧をJSON形式で分類してください。

【ルール】
- labels: ["賛成","反対","課題","提案"] から該当するものを全て選択（複数可）
- themes: {themes} から最大2つ選択
- stance: "賛成" / "反対" / "中立" のいずれか1つ
- summary: 30〜60字で要約
- quote: 元テキストからそのまま抜粋（部分文字列）
- confidence: 0.0〜1.0
- source_id: 入力のsource_idをそのまま返すこと

【出力形式】
{{"items": [{{"source_id":"...","labels":[...],"themes":[...],"stance":"...","summary":"...","quote":"...","confidence":0.0}}]}}

【市民コメント一覧】
{comments}
"""


def _build_prompt(records: List[Dict]) -> str:
    comments = json.dumps(
        [{"source_id": r["source_id"], "text": r["text"]} for r in records],
        ensure_ascii=False, indent=2
    )
    return CLASSIFY_PROMPT.format(
        themes=json.dumps(THEMES, ensure_ascii=False),
        comments=comments
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
def classify_with_gemini(records: List[Dict]) -> List[Dict]:
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY が未設定です。.env を確認してください。")
    client = genai.Client(api_key=api_key)
    prompt = _build_prompt(records)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={"response_mime_type": "application/json"}
    )
    text = response.text.strip()
    parsed = json.loads(text)
    return parsed.get("items", parsed) if isinstance(parsed, dict) else parsed
