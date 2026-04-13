from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import streamlit as st

JST = timezone(timedelta(hours=9))

DAILY_USAGE_LIMIT = 5
CSV_MAX_ROWS = 200
CSV_MAX_FILE_BYTES = 300 * 1024
CSV_MAX_CELL_CHARS = 1000
CACHE_TTL_HOURS = 24

USAGE_STATE_PATH = Path("outputs") / "_demo_usage_state.json"
CACHE_META_FILENAME = "live_cache.json"


def _load_json(path: Path) -> Dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, data: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def normalize_source_name(source_name: Optional[str]) -> Optional[str]:
    if source_name is None:
        return None
    name = source_name.strip()
    return name or None


def get_demo_user_key() -> str:
    """IPが取れればIPベース、取れなければセッションベースで識別する。"""
    headers = None
    context = getattr(st, "context", None)
    if context is not None:
        headers = getattr(context, "headers", None)

    if headers:
        for key in ("x-forwarded-for", "x-real-ip", "remote-addr"):
            raw = headers.get(key) or headers.get(key.title())
            if raw:
                ip = raw.split(",")[0].strip()
                if ip:
                    return f"ip:{ip}"

    session_id = st.session_state.get("_demo_session_id")
    if not session_id:
        session_id = uuid.uuid4().hex
        st.session_state["_demo_session_id"] = session_id
    return f"session:{session_id}"


def _prune_old_usage(data: Dict, keep_days: int = 7) -> Dict:
    usage = data.get("usage", {})
    today = datetime.now(JST).date()
    pruned = {}
    for day, users in usage.items():
        try:
            day_date = datetime.strptime(day, "%Y-%m-%d").date()
        except ValueError:
            continue
        if (today - day_date).days <= keep_days:
            pruned[day] = users
    data["usage"] = pruned
    return data


def get_remaining_daily_uses(user_key: str) -> int:
    today_key = datetime.now(JST).strftime("%Y-%m-%d")
    data = _prune_old_usage(_load_json(USAGE_STATE_PATH))
    used = int(data.get("usage", {}).get(today_key, {}).get(user_key, 0))
    return max(0, DAILY_USAGE_LIMIT - used)


def register_daily_use(user_key: str) -> int:
    """利用回数を1回消費し、消費後の残り回数を返す。"""
    today_key = datetime.now(JST).strftime("%Y-%m-%d")
    data = _prune_old_usage(_load_json(USAGE_STATE_PATH))
    usage = data.setdefault("usage", {})
    day_usage = usage.setdefault(today_key, {})
    day_usage[user_key] = int(day_usage.get(user_key, 0)) + 1
    _write_json(USAGE_STATE_PATH, data)
    return max(0, DAILY_USAGE_LIMIT - day_usage[user_key])


def validate_csv_upload(file_bytes: bytes) -> List[Dict[str, str]]:
    if len(file_bytes) > CSV_MAX_FILE_BYTES:
        raise ValueError(
            f"デモ版のため、CSVサイズは {CSV_MAX_FILE_BYTES // 1024}KB までです。"
        )

    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSVはUTF-8形式でアップロードしてください。") from exc

    reader = csv.DictReader(io.StringIO(text))
    fieldnames = reader.fieldnames or []
    required = {"id", "text"}
    if not required.issubset(set(fieldnames)):
        raise ValueError("CSVは `id` 列と `text` 列を含む必要があります。")

    rows: List[Dict[str, str]] = []
    for row_num, row in enumerate(reader, start=1):
        if row_num > CSV_MAX_ROWS:
            raise ValueError(
                f"デモ版のため、CSVは {CSV_MAX_ROWS} 行までに制限しています。"
            )

        clean_row = {}
        for key, value in row.items():
            cell = (value or "").strip()
            if len(cell) > CSV_MAX_CELL_CHARS:
                raise ValueError(
                    f"デモ版のため、1セルあたり {CSV_MAX_CELL_CHARS} 文字までです。"
                )
            clean_row[key] = cell

        if not clean_row.get("id") or not clean_row.get("text"):
            raise ValueError(
                f"CSVの {row_num} 行目に空の `id` または `text` があります。"
            )
        rows.append(clean_row)

    if not rows:
        raise ValueError("CSVにデータ行がありません。")

    return rows


def load_cached_result(out_dir: Path, source_name: Optional[str]) -> Optional[Dict]:
    cache_path = out_dir / CACHE_META_FILENAME
    pdf_path = out_dir / "demo_report.pdf"
    md_path = out_dir / "demo_report.md"
    if not cache_path.exists() or not pdf_path.exists() or not md_path.exists():
        return None

    payload = _load_json(cache_path)
    created_at_text = payload.get("created_at")
    if not created_at_text:
        return None

    try:
        created_at = datetime.fromisoformat(created_at_text)
    except ValueError:
        return None

    age = datetime.now(JST) - created_at
    if age > timedelta(hours=CACHE_TTL_HOURS):
        return None

    if payload.get("source_name") != normalize_source_name(source_name):
        return None

    return {
        "demo": payload.get("demo", []),
        "classified": payload.get("classified", []),
        "proposal_a": payload.get("proposal_a", {}),
        "proposal_b": payload.get("proposal_b", {}),
        "md": md_path.read_text(encoding="utf-8"),
        "pdf_bytes": pdf_path.read_bytes(),
    }


def save_cached_result(
    out_dir: Path,
    source_name: Optional[str],
    demo: List[Dict],
    classified: List[Dict],
    proposal_a: Dict,
    proposal_b: Dict,
) -> None:
    payload = {
        "created_at": datetime.now(JST).isoformat(),
        "source_name": normalize_source_name(source_name),
        "demo": demo,
        "classified": classified,
        "proposal_a": proposal_a,
        "proposal_b": proposal_b,
    }
    _write_json(out_dir / CACHE_META_FILENAME, payload)
