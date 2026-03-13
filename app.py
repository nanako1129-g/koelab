import streamlit as st
import csv as csv_mod
import pandas as pd
import tempfile
import hashlib
from pathlib import Path
from collections import Counter
from src.safe_ops import classify_records_safe, generate_proposal_safe
from src.evidence_select import pick_evidence
from src.report_md import build_demo_report_md
from src.export_pdf import md_to_simple_pdf

OUTPUTS_DIR = Path("outputs")
APP_DIR = Path(__file__).resolve().parent
FONT_PATH = (APP_DIR / "fonts" / "ipaexg.ttf").as_posix()


def sha16(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def records_from_csv(csv_path: str, basename: str):
    rows = list(csv_mod.DictReader(open(csv_path, encoding="utf-8")))
    return [
        {
            "source_id": f"{basename}_{r['id']}",
            "page": 0,
            "question_id": "FREE",
            "text": r["text"],
        }
        for r in rows
    ]


def records_from_pdf(pdf_path: str, dataset_id: str):
    from src.ingest_pdf import extract_free_text_records
    from src.demo_select import select_demo_records_balanced
    records = extract_free_text_records(pdf_path, dataset_id=dataset_id)
    demo = select_demo_records_balanced(records, n_each=10)
    return records, demo


# --- UI ---
st.set_page_config(page_title="こえラボ Proto", layout="wide")
st.title("🗣️ こえラボ（Koe Lab）プロトタイプ")
st.caption("市民の声をAIで分析し、エビデンス付き新規事業提案レポートを自動生成")

prod_mode = st.sidebar.toggle("本番モード（LLM呼ばない）", value=True)
st.sidebar.markdown("---")
st.sidebar.markdown("### 将来構想")
st.sidebar.markdown("- LINE Bot連携\n- GPSヒートマップ\n- 全国1,741自治体対応")

source_name = st.text_input("自治体名（任意）", placeholder="例: 塩尻市、気仙沼市")

uploaded = st.file_uploader("PDF または CSV をアップロード", type=["pdf", "csv"])
if not uploaded:
    st.info("アンケートの PDF または CSV をアップロードしてください")
    st.stop()

file_bytes = uploaded.getvalue()
key = sha16(file_bytes)
file_ext = Path(uploaded.name).suffix.lower()
out_dir = OUTPUTS_DIR / key
out_dir.mkdir(parents=True, exist_ok=True)

# --- 事前生成レポート表示 ---
demo_pdf_path = out_dir / "demo_report.pdf"
full_pdf_path = out_dir / "full_report.pdf"

st.subheader("1. 事前生成レポート")
col1, col2 = st.columns(2)
with col1:
    if demo_pdf_path.exists():
        st.success("デモ20件版PDF 検出済み")
        st.download_button("デモ20件版PDFをダウンロード",
                           data=demo_pdf_path.read_bytes(),
                           file_name="koelab_demo_20.pdf",
                           mime="application/pdf",
                           key="pre_pdf")
    else:
        st.warning("デモ20件版が未生成です")
with col2:
    if full_pdf_path.exists():
        st.success("フル版PDF 検出済み")
        st.download_button("フル版をダウンロード",
                           data=full_pdf_path.read_bytes(),
                           file_name="koelab_full.pdf",
                           mime="application/pdf",
                           key="pre_full")
    else:
        st.warning("フル版が未生成です")

if prod_mode:
    st.info("本番モードON：ライブ生成は無効です")
    st.stop()

# --- ライブ生成 ---
st.subheader("2. ライブ生成")
run = st.button("📊 ライブ生成を実行", type="primary")

# --- 生成実行 ---
if run:
    tmp_path = out_dir / f"upload{file_ext}"
    tmp_path.write_bytes(file_bytes)

    try:
        with st.status("分析中...", expanded=True) as status:
            if file_ext == ".csv":
                st.write("CSV読み込み中...")
                basename = Path(uploaded.name).stem
                demo = records_from_csv(str(tmp_path), basename)
                st.write(f"読み込み完了: {len(demo)}件")
            else:
                st.write("PDF読み込み中...")
                dataset_id = f"upload_{key}"
                all_records, demo = records_from_pdf(str(tmp_path), dataset_id)
                n21 = sum(1 for r in demo if r["question_id"] == "Q21")
                n28 = sum(1 for r in demo if r["question_id"] == "Q28")
                st.write(f"抽出完了: {len(all_records)}件 → デモ対象: {len(demo)}件（Q21={n21} / Q28={n28}）")

            st.write("AI分類中...")
            classified = classify_records_safe(demo)
            df = pd.DataFrame(classified)
            st.dataframe(df[["source_id", "labels", "themes", "summary", "confidence"]], height=200)

            st.write("テーマ分布")
            theme_counts = Counter()
            for c in classified:
                for t in c.get("themes", []):
                    theme_counts[t] += 1
            if theme_counts:
                st.bar_chart(pd.Series(dict(theme_counts.most_common())))

            st.write("エビデンス選定中...")
            evi_a = pick_evidence(demo, classified, bucket="A", k=5)
            evi_b = pick_evidence(demo, classified, bucket="B", k=5)

            st.write("提案生成中...")
            sn = source_name if source_name else None
            proposal_a = generate_proposal_safe("A", evi_a, source_name=sn)
            proposal_b = generate_proposal_safe("B", evi_b, source_name=sn)

            st.write("レポート作成中...")
            md = build_demo_report_md(demo, classified, proposal_a, proposal_b,
                                      source_name=sn)
            (out_dir / "demo_report.md").write_text(md, encoding="utf-8")

            pdf_out = out_dir / "demo_report.pdf"
            md_to_simple_pdf(md, str(pdf_out), font_path=FONT_PATH)

            # --- 結果をsession_stateに保存 ---
            st.session_state["result_pdf"] = pdf_out.read_bytes()
            st.session_state["result_md"] = md
            st.session_state["result_ready"] = True

            status.update(label="完了！", state="complete")

    except Exception as e:
        st.error(f"エラー: {e}")
        if demo_pdf_path.exists():
            st.info("事前生成PDFを代わりに提示します")
            st.download_button("事前生成PDFをダウンロード",
                               data=demo_pdf_path.read_bytes(),
                               file_name="koelab_fallback.pdf",
                               mime="application/pdf",
                               key="fallback")

# --- 結果表示（消えない） ---
if st.session_state.get("result_ready"):
    st.subheader("3. レポートダウンロード")

    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button(
            "📥 レポートPDFをダウンロード",
            data=st.session_state["result_pdf"],
            file_name="koelab_report.pdf",
            mime="application/pdf",
            key="dl_pdf",
        )
    with dl_col2:
        st.download_button(
            "📝 レポートテキストをダウンロード",
            data=st.session_state["result_md"].encode("utf-8"),
            file_name="koelab_report.md",
            mime="text/markdown",
            key="dl_md",
        )

    st.markdown("---")
    if st.button("🗑️ 結果をクリアする"):
        del st.session_state["result_pdf"]
        del st.session_state["result_md"]
        del st.session_state["result_ready"]
        st.rerun()
