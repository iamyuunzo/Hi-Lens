# pages/compare-page.py
# -----------------------------------------------------------------------------
# 이 페이지는 '개별 분석 페이지'가 아니라 '라우팅 템플릿' 1개다.
# 어떤 분석을 보여줄지는 URL ?aid=... 파라미터로 결정한다.
# 사이드바/landing에서 버튼 클릭 시 utils.goto_compare(aid)로 동일 페이지로 오게 됨.
# -----------------------------------------------------------------------------
import streamlit as st
from typing import List, Tuple
from io import BytesIO

from utils import render_sidebar, get_query_aid, get_analysis, touch_analysis
from retriever_client import search_chunks
from prompts import SYSTEM_PROMPT, build_user_prompt

st.set_page_config(page_title="PDF 비교/질의", layout="wide")
render_sidebar()

# -------------------- 간단 텍스트 추출(로컬 미리보기 용) --------------------
def _extract_texts(files: List[dict]) -> List[Tuple[str, str]]:
    try:
        import PyPDF2
    except Exception:
        return [(f["name"], "") for f in files]
    out = []
    for f in files:
        buf = []
        try:
            reader = __import__("PyPDF2").PdfReader(BytesIO(f["bytes"]))
            for p in reader.pages:
                try:
                    buf.append(p.extract_text() or "")
                except Exception:
                    pass
        except Exception:
            pass
        out.append((f["name"], "\n".join(buf)))
    return out
# ---------------------------------------------------------------------------

# 1) URL ?aid= 읽고 분석 로드
aid = get_query_aid()
rec = get_analysis(aid)

if not rec:
    st.warning("유효한 분석이 없습니다. landing-page에서 업로드하거나, 사이드바 기록에서 선택하세요.")
    st.stop()

# 사용 흔적 갱신(정렬용)
touch_analysis(aid)

st.markdown(f"## 📚 PDF 비교/질의 — **{rec['title']}**")
st.caption(f"Analysis ID: `{rec['id']}`")

left, right = st.columns([1, 1], gap="large")

with left:
    st.subheader("📄 업로드 파일")
    for f in rec["files"]:
        st.write(f"• {f['name']}")

    st.markdown("---")
    st.subheader("🤖 LLM 질의 (컨텍스트 검색 포함)")
    q = st.text_input("PDF 내용에 대해 질문해 보세요", placeholder="예) 11차 계획의 석탄 비중은?", key=f"q_{aid}")
    run = st.button("질문하기", use_container_width=True, key=f"ask_{aid}")

    if run and q.strip():
        # 1) 컨텍스트 검색: 팀 /search API 또는 목업 응답
        contexts = search_chunks(q)  # 현재는 업로드 파일과 무관한 '검색 백엔드' 자리(목업 지원)  :contentReference[oaicite:9]{index=9}

        # 2) LLM에 보낼 사용자 프롬프트 구성(미리보기)  :contentReference[oaicite:10]{index=10}
        user_prompt = build_user_prompt(q, contexts)

        st.caption("🔧 SYSTEM PROMPT")
        st.code(SYSTEM_PROMPT)

        st.caption("📦 USER PROMPT(컨텍스트 포함)")
        st.code(user_prompt)

        st.caption("🔎 검색 컨텍스트 미리보기")
        st.json(contexts)

with right:
    tab1, tab2 = st.tabs(["📑 PDF 원문(미리보기 자리)", "💬 대화기록(데모)"])
    with tab1:
        st.info("실서비스에서는 PDF.js/iframe으로 원문 뷰어를 임베드하세요.")
    with tab2:
        st.write("대화기록 저장/표시는 추후 LLM 연결 시 구현 예정.")
