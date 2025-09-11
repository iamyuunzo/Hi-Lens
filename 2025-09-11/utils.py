# utils.py
# -----------------------------------------------------------------------------
# ✅ (추가) 세션 상태/라우팅/사이드바 + (기존) PDF 텍스트 프리뷰 유지
# - compare-page는 '템플릿 1개'이고, 어떤 분석을 볼지는 URL ?aid=<analysis_id>
# - 사이드바에는 섹션 버튼(landing/promptying) + 분석 기록 목록 버튼 렌더링
# -----------------------------------------------------------------------------

from __future__ import annotations
import datetime as dt
import uuid
import streamlit as st
import fitz  # PyMuPDF
from io import BytesIO
from typing import List, Dict

# ---------------------- 기존 프리뷰 유틸(그대로 유지) ------------------------
def extract_text_from_pdf(file_bytes: bytes, max_pages: int = 1) -> str:
    doc = fitz.open(stream=BytesIO(file_bytes), filetype="pdf")
    out = []
    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        out.append(page.get_text())
    doc.close()
    return "\n".join(out).strip()
# ---------------------------------------------------------------------------

# ---------------------- 신규: 세션 상태 키 -------------------------------
KEY_ANALYSES = "analyses"                 # {id: {id,title,files,created_at,updated_at}}
KEY_CURRENT_AID = "current_aid"

def _ensure_session():
    if KEY_ANALYSES not in st.session_state:
        st.session_state[KEY_ANALYSES] = {}
    if KEY_CURRENT_AID not in st.session_state:
        st.session_state[KEY_CURRENT_AID] = None

# ---------------------- 신규: 분석 CRUD ---------------------------------
def create_analysis(title: str, files_payload: List[Dict[str, bytes]]) -> str:
    """
    새 분석을 메모리 세션에 저장하고 analysis_id 반환.
    files_payload: [{"name": str, "bytes": bytes}, ...]
    """
    _ensure_session()
    aid = str(uuid.uuid4())
    now = dt.datetime.utcnow().isoformat()
    st.session_state[KEY_ANALYSES][aid] = {
        "id": aid,
        "title": title.strip() or "제목 없음",
        "files": files_payload,           # 데모: 세션에 보관(프로덕션: 디스크/DB 권장)
        "created_at": now,
        "updated_at": now,
    }
    st.session_state[KEY_CURRENT_AID] = aid
    return aid

def get_analysis(aid: str | None):
    _ensure_session()
    if not aid:
        return None
    return st.session_state[KEY_ANALYSES].get(aid)

def touch_analysis(aid: str):
    _ensure_session()
    rec = st.session_state[KEY_ANALYSES].get(aid)
    if rec:
        rec["updated_at"] = dt.datetime.utcnow().isoformat()

def list_analyses() -> list[dict]:
    _ensure_session()
    items = list(st.session_state[KEY_ANALYSES].values())
    items.sort(key=lambda r: r.get("updated_at", ""), reverse=True)
    return items

# ---------------------- 신규: URL 쿼리 & 페이지 이동 ----------------------
def get_query_aid() -> str | None:
    """현재 URL에서 ?aid= 파라미터 읽기 (버전별 폴백 포함)"""
    try:
        return st.query_params.get("aid")
    except Exception:
        params = st.experimental_get_query_params()
        vals = params.get("aid")
        return vals[0] if vals else None

def goto_compare(aid: str):
    """compare-page로 이동하면서 ?aid= 세팅"""
    try:
        st.query_params["aid"] = aid
    except Exception:
        st.experimental_set_query_params(aid=aid)
    try:
        st.switch_page("pages/compare-page.py")
    except Exception:
        st.toast("좌측에서 compare-page를 클릭하세요.", icon="➡️")

# ---------------------- 신규: 공통 사이드바 렌더링 -----------------------
def render_sidebar():
    """상단: 섹션 버튼 / 하단: 분석 기록 목록(누르면 해당 aid로 compare 이동)"""
    _ensure_session()
    with st.sidebar:
        st.markdown("## app")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("landing-page", use_container_width=True):
                try:
                    st.switch_page("landing-page.py")
                except Exception:
                    st.toast("좌측 목록에서 landing-page 클릭", icon="ℹ️")
        with c2:
            if st.button("promptying-page", use_container_width=True):
                try:
                    st.switch_page("pages/promptying-page.py")
                except Exception:
                    st.toast("좌측 목록에서 promptying-page 클릭", icon="ℹ️")

        st.markdown("---")
        st.markdown("### 업로드 기록")
        for rec in list_analyses():
            if st.button(rec["title"], key=f"aid_{rec['id']}", use_container_width=True):
                goto_compare(rec["id"])

        st.caption("※ 데모: 세션 메모리 저장. 런타임 재시작 시 사라집니다.")
