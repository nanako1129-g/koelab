# src/ingest_pdf.py
from __future__ import annotations

import re
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


def extract_free_text_records(pdf_path: str, dataset_id: str = "kesennuma") -> List[Dict]:
    dataset_id = _sanitize_dataset_id(dataset_id)
    pages = pdf_to_pages_text(pdf_path)

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
            records.append(
                {
                    "source_id": source_id,
                    "page": buf_page,
                    "question_id": current_q,
                    "text": buf_text.strip(),
                }
            )
        buf_text = None
        buf_page = None

    for page_num, text in enumerate(pages, start=1):
        lines = [_clean_line(l) for l in (text or "").splitlines()]
        lines = [l for l in lines if l]

        for line in lines:
            if Q21_START.search(line):
                flush()
                current_q = "Q21"
                continue

            if Q28_START.search(line):
                flush()
                current_q = "Q28"
                continue

            if current_q == "Q21" and Q21_END.search(line):
                flush()
                current_q = None
                continue

            if current_q is None:
                continue

            if BULLET_RE.match(line):
                flush()
                buf_page = page_num
                buf_text = BULLET_RE.sub("", line).strip()
            else:
                if buf_text:
                    buf_text += " " + line.strip()

    flush()

    sids = [r["source_id"] for r in records]
    if len(sids) != len(set(sids)):
        from collections import Counter
        dup = [k for k, v in Counter(sids).items() if v > 1]
        raise RuntimeError(f"source_idが重複しています: {dup[:5]}")

    return records
