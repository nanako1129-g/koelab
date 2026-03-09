import streamlit as st
import pandas as pd
import tempfile
import hashlib
from pathlib import Path
from collections import Counter
from src.ingest_pdf import extract_free_text_records
from src.demo_select import select_demo_records_balanced
from src.safe_ops import classify_records_safe, generate_proposal_safe
from src.evidence_select import pick_evidence
from src.report_md import build_demo_report_md
from src.export_pdf import md_to_simple_pdf

OUTPUTS_DIR = Path("outputs")
APP_DIR = Path(__file__).resolve().parent
FONT_PATH = (APP_DIR / "fonts" / "ipaexg.ttf").as_posix()

def sha16(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]

st.set_page_config(page_title="こえラボ Proto", layout="wide")
st.title("こえラボ（Koe Lab）プロトタイプ")
st.caption("市民の声をAIで分析し、エビデンス付き新規事業提案レポートを自動生成")

prod_mode = st.sidebar.toggle("本番モード（LLM呼ばない）", value=True)
st.sidebar.markdown("---")
st.sidebar.markdown("### 将来構想")
st.sidebar.markdown("- LINE Bot連携\n- GPSヒートマップ\n- 全国1,741自治体対応")

uploaded = st.file_uploader("PDFをアップロード", type=["pdf"])
if not uploaded:
    st.info("気仙沼市Well-beingアンケートPDFをアップロードしてください")
    st.stop()

pdf_bytes = uploaded.getvalue()
key = sha16(pdf_bytes)
dataset_id = f"kesennuma_{key}"
out_dir = OUTPUTS_DIR / key
out_dir.mkdir(parents=True, exist_ok=True)

demo_pdf_path = out_dir / "demo_report.pdf"
full_pdf_path = out_dir / "full_report.pdf"

st.subheader("1. 事前生成レポート")
col1, col2 = st.columns(2)
with col1:
    if demo_pdf_path.exists():
        st.success("デモ20件版PDF 検出済み")
        st.download_button("デモ20件版をダウンロード",
                           data=demo_pdf_path.read_bytes(),
                           file_name="koelab_demo_20.pdf",
                           mime="application/pdf")
    else:
        st.warning("デモ20件版が未生成です")
with col2:
    if full_pdf_path.exists():
        st.success("フル版PDF 検出済み")
        st.download_button("フル版をダウンロード",
                           data=full_pdf_path.read_bytes(),
                           file_name="koelab_full.pdf",
                           mime="application/pdf")
    else:
        st.warning("フル版が未生成です")

if prod_mode:
    st.info("本番モードON：ライブ生成は無効です")
    st.stop()

st.subheader("2. ライブ生成（デモ20件）")
run = st.button("ライブ生成を実行", type="primary")
if not run:
    st.stop()

with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
    f.write(pdf_bytes)
    tmp_path = f.name

try:
    with st.status("分析中...", expanded=True) as status:
        st.write("PDF読み込み中...")
        records = extract_free_text_records(tmp_path, dataset_id=dataset_id)
        st.write(f"抽出完了: {len(records)}件")

        demo = select_demo_records_balanced(records, n_each=10)
        n21 = sum(1 for r in demo if r["question_id"] == "Q21")
        n28 = sum(1 for r in demo if r["question_id"] == "Q28")
        st.write(f"デモ対象: {len(demo)}件（Q21={n21} / Q28={n28}）")

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
        proposal_a = generate_proposal_safe("A", evi_a)
        proposal_b = generate_proposal_safe("B", evi_b)

        st.write("レポート作成中...")
        md = build_demo_report_md(demo, classified, proposal_a, proposal_b)
        (out_dir / "demo_report.md").write_text(md, encoding="utf-8")

        pdf_out = out_dir / "demo_report.pdf"
        try:
            md_to_simple_pdf(md, str(pdf_out), font_path=FONT_PATH)
            status.update(label="完了！", state="complete")
            st.download_button("生成したPDFをダウンロード",
                               data=pdf_out.read_bytes(),
                               file_name="koelab_demo_live.pdf",
                               mime="application/pdf")
        except Exception as e:
            txt_path = out_dir / "demo_report.txt"
            txt_path.write_text(md, encoding="utf-8")
            status.update(label="PDF失敗→テキスト版", state="complete")
            st.download_button("テキスト版をダウンロード",
                               data=md,
                               file_name="koelab_demo.txt",
                               mime="text/plain")
except Exception as e:
    st.error(f"エラー: {e}")
    if demo_pdf_path.exists():
        st.info("事前生成PDFを代わりに提示します")
        st.download_button("事前生成PDFをダウンロード",
                           data=demo_pdf_path.read_bytes(),
                           file_name="koelab_demo_fallback.pdf",
                           mime="application/pdf")
finally:
    Path(tmp_path).unlink(missing_ok=True)
