# src/ingest_pdf.py
from __future__ import annotations

import re, os, json
from typing import List, Dict, Optional

import pdfplumber

# ===== 正規表現 / ルール =====
BULLET_RE = re.compile(r"^\s*(?:[-•●◦\uf09e])\s*")
MD_HASH_RE = re.compile(r"^\s*##\s*")
Q21_START = re.compile(r"問\s*21\b")
Q21_END   = re.compile(r"問\s*22\b")
Q28_START = re.compile(r"問\s*28\b")


def _clean_line(line: str) -> str:
    line = (line or "").rstrip("\n")
    line = MD_HASH_RE.sub("", line).strip()
    return line


def _sanitize_dataset_id(dataset_id: str) -> str:
    dataset_id = (dataset_id or "").strip()
    dataset_id = re.sub(r"[^0-9A-Za-z_\-]", "_", dataset_id)
    return dataset_id or "dataset"


def pdf_to_pages_text(pdf_path: str) -> List[str]:
    pages: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for p in pdf.pages:
            pages.append(p.extract_text() or "")
    return pages


# ===== 汎用抽出 (Gemini) =====
EXTRACT_PROMPT = """あなたは自治体アンケートの分析官です。
以下のPDFテキストから、市民の自由記述（意見・感想・要望・コメント）に該当する文を全て抽出してください。
選択肢の説明文やグラフのラベル、調査概要の説明文は除外してください。

【出力形式】JSONのみ。説明不要。
{{"items": [{{"page": ページ番号, "text": "自由記述の本文"}}]}}

ページ番号は与えられたページ番号をそのまま使ってください。

【PDFテキスト】
{pdf_text}
"""


def _extract_with_gemini(pages: List[str], dataset_id: str) -> List[Dict]:
    """Gemini APIで自由記述を汎用抽出"""
    from google import genai

    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        return []

    model = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")

    # ページ番号付きでテキストを結合
    chunks = []
    for i, text in enumerate(pages, start=1):
        if text.strip():
            chunks.append(f"--- Page {i} ---\n{text}")

    full_text = "\n".join(chunks)

    # トークン制限を考慮して分割（おおよそ30ページずつ）
    MAX_CHARS = 80000
    segments = []
    current = ""
    for chunk in chunks:
        if len(current) + len(chunk) > MAX_CHARS:
            if current:
                segments.append(current)
            current = chunk
        else:
            current += "\n" + chunk
    if current:
        segments.append(current)

    client = genai.Client(api_key=api_key)
    all_items = []

    for seg in segments:
        prompt = EXTRACT_PROMPT.format(pdf_text=seg)
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            parsed = json.loads(response.text.strip())
            items = parsed.get("items", parsed) if isinstance(parsed, dict) else parsed
            all_items.extend(items)
        except Exception as e:
            print(f"[汎用抽出] Gemini呼び出しエラー: {e}")
            continue

    # recordsに変換
    records = []
    for idx, item in enumerate(all_items, start=1):
        text = (item.get("text") or "").strip()
        if not text or len(text) < 5:
            continue
        page = item.get("page", 0)
        source_id = f"{dataset_id}_FREE_{idx:04d}"
        records.append({
            "source_id": source_id,
            "page": page,
            "question_id": "FREE",
            "text": text,
        })

    return records


# ===== 旧ロジック (気仙沼専用) =====
def _extract_kesennuma(pages: List[str], dataset_id: str) -> List[Dict]:
    records: List[Dict] = []
    current_q: Optional[str] = None
    buf_text: Optional[str] = None
    buf_page: Optional[int] = None
    counters = {"Q21": 0, "Q28": 0}

    def flush() -> None:
        nonlocal buf_text, buf_page, current_q
        if buf_text and buf_page and current_q:
            counters[current_q] += 1
            idx = counters[current_q]
            source_id = f"{dataset_id}_{current_q}_{idx:03d}"
            records.append({
                "source_id": source_id,
                "page": buf_page,
                "question_id": current_q,
                "text": buf_text.strip(),
            })
        buf_text = None
        buf_page = None

    for page_num, text in enumerate(pages, start=1):
        lines = [_clean_line(l) for l in (text or "").splitlines()]
        lines = [l for l in lines if l]
        for line in lines:
            if Q21_START.search(line):
                flush(); current_q = "Q21"; continue
            if Q28_START.search(line):
                flush(); current_q = "Q28"; continue
            if current_q == "Q21" and Q21_END.search(line):
                flush(); current_q = None; continue
            if current_q is None:
                continue
            if BULLET_RE.match(line):
                flush(); buf_page = page_num
                buf_text = BULLET_RE.sub("", line).strip()
            else:
                if buf_text:
                    buf_text += " " + line.strip()
        flush()

    return records


# ===== メイン関数 =====
def extract_free_text_records(pdf_path: str, dataset_id: str = "dataset") -> List[Dict]:
    dataset_id = _sanitize_dataset_id(dataset_id)
    pages = pdf_to_pages_text(pdf_path)

    # まず旧ロジック（気仙沼）を試す
    records = _extract_kesennuma(pages, dataset_id)
    if records:
        print(f"[抽出] 旧ロジックで {len(records)}件抽出")
        return records

    # 旧ロジックで0件 → Gemini汎用抽出
    print("[抽出] 旧ロジック0件 → Gemini汎用抽出を実行")
    records = _extract_with_gemini(pages, dataset_id)
    if records:
        print(f"[抽出] Gemini汎用抽出で {len(records)}件抽出")
    else:
        print("[抽出] 抽出できませんでした")

    # source_id重複チェック
    sids = [r["source_id"] for r in records]
    if len(sids) != len(set(sids)):
        from collections import Counter
        dup = [k for k, v in Counter(sids).items() if v > 1]
        raise RuntimeError(f"source_idが重複しています: {dup[:5]}")

    return records
