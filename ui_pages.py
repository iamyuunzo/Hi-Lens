# ui_pages.py — 최종본 (요청사항 모두 반영)
# -----------------------------------------------------------------------------
# ✅ 반영사항:
#   - 대화 탭/표·그림 탭 모두 동일한 st.chat_input 기반 AI 챗봇 UI
#     · 대화 탭: 전체 원문 QA
#     · 표·그림 탭: 표/그림 중심 QA (표 미리보기/인접본문에 한정)
#   - 추천질문/목차 토글/기존 파이프라인 보존
#   - 이미지: max-width 제한(기본 800px) + 반응형(use_container_width=True)
#   - 랜딩: 제목/설명 센터 정렬
#   - 로딩: 스피너/제목/진행바 간격 조정
#   - 답변/근거/요약: 문장 줄바꿈 + 불릿(◦)
# -----------------------------------------------------------------------------
APP_VERSION = "2025-09-26.01"

from __future__ import annotations
import time, hashlib, datetime as dt, re
from typing import Dict, Any, List, Optional

import pandas as pd
import streamlit as st
from styles import get_css, ACCENT
from extract import build_chunks, crop_table_image
try:
    from extract import crop_figure_image
except Exception:
    crop_figure_image = crop_table_image  # 폴백

# LLM 유틸들
from llm import (
    answer_with_context,
    get_provider_name,
    explain_tables,
)
# explain_figure_image는 예외 대비 폴백
try:
    from llm import explain_figure_image
except Exception:
    def explain_figure_image(query: str, image, neighbor_text: str = "") -> str:
        return answer_with_context(
            query,
            f"[이미지 요약 폴백]\n{(neighbor_text or '')[:1800]}",
            page_label=None,
        )

from summarizer import summarize_from_chunks
from qa_recos import QA_RECOMMENDATIONS
from rag import RAGIndex
try:
    from rank_bm25 import BM25Okapi
except Exception:
    BM25Okapi = None


# ================================ 세션/유틸 ================================
def _init_session_defaults():
    """앱 전역 세션키 기본값"""
    st.session_state.setdefault("route", "landing")
    st.session_state.setdefault("pdf_bytes", None)
    st.session_state.setdefault("pdf_name", "")
    st.session_state.setdefault("chunks", {})
    st.session_state.setdefault("summary", "")
    st.session_state.setdefault("chat", [])          # 대화 탭 히스토리
    st.session_state.setdefault("toc_dialogs", [])   # 표·그림 탭 히스토리
    st.session_state.setdefault("_threads", [])
    st.session_state.setdefault("_current_tid", None)


def _pdf_id() -> Optional[str]:
    """업로드 PDF를 해시로 식별"""
    data = st.session_state.get("pdf_bytes")
    return hashlib.sha1(data).hexdigest()[:12] if data else None


def _threads() -> List[Dict[str, Any]]:
    """문서별 세션 저장소"""
    return st.session_state.setdefault("_threads", [])


def _current_thread() -> Optional[Dict[str, Any]]:
    tid = st.session_state.get("_current_tid")
    for t in _threads():
        if t["tid"] == tid:
            return t
    return None


def _ensure_thread():
    """현재 PDF 기준 스레드 없으면 생성"""
    if _current_thread():
        return
    pid = _pdf_id()
    name = st.session_state.get("pdf_name") or "문서"
    tid = f"{pid}-{int(time.time())}"
    _threads().append(
        {"tid": tid, "pdf_id": pid, "pdf_name": name, "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
         "messages": [], "pdf_bytes": st.session_state.get("pdf_bytes"), "chunks": {}, "summary": ""}
    )
    st.session_state["_current_tid"] = tid


# ================================ 사이드바 ================================
def render_sidebar():
    st.sidebar.markdown("<div class='hp-brand'><span class='dot'></span>Hi-Lens</div>", unsafe_allow_html=True)
    st.sidebar.caption("PDF 요약·발췌·시각화 도우미")
    st.sidebar.info(f"LLM: {get_provider_name()}", icon="🧠")

    if st.sidebar.button("🏠 홈으로", use_container_width=True):
        st.session_state["route"] = "landing"; st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.subheader("PDF 분석 기록")

    for t in reversed(_threads()):
        label = f"📄 {t['pdf_name']} · {t['ts']} · 질문 {len(t['messages'])}개"
        if st.sidebar.button(label, key=f"hist-{t['tid']}", use_container_width=True):
            st.session_state.update(
                {"_current_tid": t["tid"], "pdf_name": t["pdf_name"], "pdf_bytes": t.get("pdf_bytes"),
                 "chunks": t.get("chunks", {}), "summary": t.get("summary", ""), "route": "analysis"}
            ); st.rerun()


# ================================ 페이지들 ================================
def landing_page():
    _init_session_defaults()
    _inject_css()
    render_sidebar()

    # 제목/설명 모두 센터 정렬
    st.markdown("<p style='text-align:center;'> </p>", unsafe_allow_html=True)
    st.markdown("<h1 style='font-weight:900; text-align:center;'>👋 Hi-Lens</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;'> </p>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;'>PDF에서 표/그림/문단을 추출해 <b>질문 → 표/그래프/요약</b>으로 재구성합니다.</p>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;'> </p>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;'> </p>", unsafe_allow_html=True)

    upl = st.file_uploader("분석할 PDF 업로드해주세요.", type=["pdf"], key="landing_upl")
    if st.button("🔍 분석 시작", use_container_width=True):
        if not upl:
            st.warning("먼저 PDF를 업로드해주세요."); st.stop()
        pdf_bytes, pdf_name = upl.read(), upl.name
        pdf_id = hashlib.sha1(pdf_bytes).hexdigest()[:12]
        tid = f"{pdf_id}-{int(time.time())}"
        _threads().append({"tid": tid, "pdf_id": pdf_id, "pdf_name": pdf_name,
                           "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
                           "messages": [], "pdf_bytes": pdf_bytes, "chunks": {}, "summary": ""})
        st.session_state.update({"_current_tid": tid, "pdf_bytes": pdf_bytes, "pdf_name": pdf_name, "route": "loading"})
        st.rerun()


def loading_page():
    _init_session_defaults()

    # 헤더/사이드바 숨김
    st.markdown("<style>section[data-testid='stSidebar']{display:none;} header,footer{display:none;}</style>", unsafe_allow_html=True)

    # 🔧 프로그레스바 색상 강제 변경 (기본 빨강 → 남색)
    st.markdown(
        """
        <style>
          /* 진행 바 채워지는 부분 색상 */
          .stProgress > div > div > div > div {
              background-color: #0f2e69 !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 로딩 스피너 + 간격 (🔧 간격 확장)
    st.markdown(
        """
        <style>
          .hl-wrap { text-align:center; margin-top:110px; /* 🔧 상단 여백 확대 */ }
          .hl-spinner {
            margin: 0 auto 34px auto; /* 🔧 스피너와 제목 사이 간격 확대 */ width: 42px; height: 42px;
            border: 4px solid #e9ecef; border-top-color: #dc8d32;
            border-radius: 50%; animation: hlspin .9s linear infinite;
          }
          @keyframes hlspin { to { transform: rotate(360deg); } }
          .hl-title { font-weight: 900; font-size: 28px; margin-bottom: 28px; /* 🔧 제목과 진행바 사이 간격 확대 */ }
        </style>
        <div class="hl-wrap">
          <div class="hl-spinner"></div>
          <div class="hl-title">Hi-Lens가 분석중...</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:25px'></div>", unsafe_allow_html=True)  # 🔧 스피너/제목과 로딩바 사이 간격 확보
    bar = st.progress(0.0, text="PDF 처리 시작")
    pdf_bytes = st.session_state.get("pdf_bytes")
    if not pdf_bytes:
        st.warning("업로드된 PDF가 없습니다."); return

    # 실제 추출/요약
    chunks = build_chunks(pdf_bytes)
    def _cb(msg, ratio): bar.progress(ratio, text=msg)
    summary = summarize_from_chunks(chunks, max_pages=20, progress_cb=_cb)

    # 세션 저장
    st.session_state["chunks"], st.session_state["summary"] = chunks, summary
    th = _current_thread()
    if th: th.update({"chunks": chunks, "summary": summary})

    st.session_state["route"] = "analysis"; st.rerun()


def analysis_page():
    _init_session_defaults()

    # ✅ 배포할 때마다 캐시 싹 비우기
    st.cache_data.clear()
    st.cache_resource.clear()
    
    _inject_css()
    render_sidebar()

    pdf_name = st.session_state.get("pdf_name") or "분석 문서"
    chunks   = st.session_state.get("chunks") or {}
    summary  = st.session_state.get("summary") or ""
    _ensure_thread()

    n_t, n_f, n_x = len(chunks.get("tables", [])), len(chunks.get("figures", [])), len(chunks.get("texts", []))
    st.markdown(
        f"<div class='hp-header'><div class='title'>📄 {pdf_name}</div>"
        f"<div class='summary'>텍스트 {n_x} · 표 {n_t} · 그림 {n_f}</div></div>",
        unsafe_allow_html=True
    )

    # ================== 탭 ==================
    tab_chat, tab_toc = st.tabs(["💬 대화", "📑 표·그림 목차"])

    # ----------------------- 대화 탭 -----------------------
    with tab_chat:
        with st.expander("원문 요약", expanded=False):
            if summary:
                summary_fmt = _format_paragraphs(summary, bullets=True)
                st.markdown(f"<div class='hp-answer-box1'>{summary_fmt}</div>", unsafe_allow_html=True)
            else:
                st.info("요약이 아직 준비되지 않았습니다.")

        with st.expander("추천 질문", expanded=False):
            recos = QA_RECOMMENDATIONS.get(pdf_name, {})
            for i, (_, data) in enumerate(recos.items()):
                if st.button(data["question"], key=f"recbtn-{i}"):
                    _append_dialog(
                        which="chat",
                        user=data["question"],
                        answer=data["answer"],
                        grounds=data.get("grounds")
                    ); st.rerun()

        if not st.session_state.get("chat"):
            st.info("아직 대화가 없습니다. 추천 질문을 클릭하거나 질문을 입력해보세요 🙂")
        else:
            _render_dialogs("chat")

        # ✅ 이 탭 전용 입력창 (푸터 고정)
        usr_q = st.chat_input("PDF 원문에 대해 질문해보세요.", key="inp-chat")
        if usr_q and usr_q.strip():
            ans, grounds = _qa_pipeline(usr_q, chunks)
            _append_dialog(which="chat", user=usr_q, answer=ans, grounds=grounds)
            st.rerun()

    # ------------------- 표·그림 목차 탭 -------------------
    with tab_toc:
        with st.expander("목차 보기", expanded=False):
            toc_tab1, toc_tab2 = st.tabs(["표 목차", "그림 목차"])
            with toc_tab1:
                _render_toc_buttons(chunks.get("toc", {}).get("tables", []), kind="table", chunks=chunks, cols=2)
            with toc_tab2:
                _render_toc_buttons(chunks.get("toc", {}).get("figures", []), kind="figure", chunks=chunks, cols=2)

        if not st.session_state.get("toc_dialogs"):
            st.info("아직 표·그림 관련 대화가 없습니다. 목차를 클릭하거나 질문을 입력해보세요 🙂")
        else:
            _render_dialogs("toc")

        # ✅ 이 탭 전용 입력창 (푸터 고정)
        toc_q = st.chat_input("표·그림에 대해 질문해보세요.", key="inp-toc")
        if toc_q and toc_q.strip():
            ans, grounds = _qa_pipeline_tables_only(toc_q, chunks)
            _append_dialog(which="toc", user=toc_q, answer=ans, grounds=grounds)
            st.rerun()



# ============================ QA 파이프라인 ============================
def _qa_pipeline(query: str, chunks: Dict[str, Any]) -> (str, list):
    """전체 원문 QA: 표 RAG + 본문 검색 결합"""
    table_parts: List[str] = []
    grounds_parts: List[tuple] = []  # (snippet, page)

    rag = RAGIndex(); rag.build_from_chunks(chunks)

    # 1) 표/그림 관련 상위 (context로만 사용, 근거에는 추가하지 않음)
    table_hits = rag.search_tables(query, k=3)
    for hit in table_hits:
        title = (hit.get("title") or "").strip()
        pno   = hit.get("page_label", "?")
        prev  = (hit.get("text") or "").strip()
        nb    = _neighbor_text(chunks, hit.get("page_index", 0) + 1)
        table_parts.append(f"(표/그림 p.{pno}) {title}\n{prev}\n{nb}")

    # 2) 본문 텍스트 검색 (근거는 여기서만 추가)
    text_hits = _search_text_pages(query, chunks, k=3, per_len=1200)
    for h in text_hits:
        snippet_clean = _cleanup_text_for_grounds(h["snippet"])
        if snippet_clean:
            table_parts.append(f"(본문 p.{h['page']})\n{snippet_clean}")
            grounds_parts.append((snippet_clean, h["page"]))

    # 3) 컨텍스트 합성
    ctx = "\n\n---\n\n".join([p for p in table_parts if p]).strip()
    if not ctx:
        ctx = "\n".join([(t.get("text") or "") for t in chunks.get("texts", [])[:3]])[:2000]

    ans = answer_with_context(query, ctx, page_label=None)

    # ✅ 사용자가 "표" 요청했을 때만 표 변환 실행
    if "표" in query:
        table_suggestion = make_table_from_text(ctx)
        if table_suggestion:
            ans += "\n\n---\n\n📊 요청하신 내용을 표로 정리하면:\n" + table_suggestion

    return ans, grounds_parts


def _qa_pipeline_tables_only(query: str, chunks: Dict[str, Any]) -> (str, list):
    """표/그림 중심 QA: 표/그림 미리보기 + 인접 본문만 사용"""
    table_parts: List[str] = []
    grounds_parts: List[tuple] = []  # (snippet, page)

    rag = RAGIndex(); rag.build_from_chunks(chunks)
    hits = rag.search_tables(query, k=5)
    for hit in hits:
        title = (hit.get("title") or "").strip()
        pno   = hit.get("page_label", "?")
        prev  = (hit.get("text") or "").strip()
        nb    = _neighbor_text(chunks, hit.get("page_index", 0) + 1)
        table_parts.append(f"(표/그림 p.{pno}) {title}\n{prev}\n{nb}")

    # 본문 Top3 근거도 수집
    text_hits = _search_text_pages(query, chunks, k=3, per_len=1200)
    for h in text_hits:
        snippet_clean = _cleanup_text_for_grounds(h["snippet"])
        if snippet_clean:
            table_parts.append(f"(본문 p.{h['page']})\n{snippet_clean}")
            grounds_parts.append((snippet_clean, h["page"]))

    ctx = "\n\n".join([p for p in table_parts if p]).strip()[:4000]
    if not ctx:
        ctx = "\n".join([(t.get("text") or "") for t in chunks.get("texts", [])[:2]])[:1500]

    ans = answer_with_context(query, ctx, page_label=None)

    # ✅ 사용자가 "표" 요청했을 때만 표 변환 실행
    if "표" in query:
        table_suggestion = make_table_from_text(ctx)
        if table_suggestion:
            ans += "\n\n---\n\n📊 요청하신 내용을 표로 정리하면:\n" + table_suggestion

    return ans, grounds_parts


# ================================ 대화/렌더 ================================
def _append_dialog(which: str, user: str, answer: str, item: Optional[Dict] = None, grounds: Optional[str] = None):
    """대화/목차 탭 메시지 추가"""
    key = "toc_dialogs" if (which == "toc" or item) else "chat"
    st.session_state.setdefault(key, []).append({"user": user, "answer": answer, "item": item, "grounds": grounds})


def _render_dialogs(which: str):
    dialogs = st.session_state.get("toc_dialogs" if which == "toc" else "chat", [])
    for d in dialogs:
        # 사용자 질문
        st.markdown("<p style='text-align:center;'> </p>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='hp-msg user'><div class='bubble'>{d['user']}</div></div>",
            unsafe_allow_html=True
        )
        st.markdown("<p style='text-align:center;'> </p>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center;'> </p>", unsafe_allow_html=True)
        st.markdown("<div class='hp-card__title'>🤔 Hi-Lens의 답변</div>", unsafe_allow_html=True)

        # 표/그림 미리보기 (있으면)
        if d.get("item"):
            _render_item_preview(d["item"])

        # 답변 출력
        formatted = _format_answer(d["answer"]) if d.get("answer") else ""

        if "|" in formatted and "---" in formatted:
            # 마크다운 표 감지 시 → Streamlit 표로 변환
            st.markdown("📊 요청하신 내용을 표로 정리하면:")
            render_markdown_table(formatted)
        else:
            # 일반 텍스트 답변
            st.markdown(f"<div class='hp-answer-box'>{formatted}</div>", unsafe_allow_html=True)

        # 원문 근거 출력
        if d.get("grounds"):
            st.markdown("<p style='text-align:center;'> </p>", unsafe_allow_html=True)
            with st.expander("📑 원문 근거 보기", expanded=False):
                grounds = d["grounds"]
                blocks = []
                if isinstance(grounds, list) and all(isinstance(g, tuple) for g in grounds):
                    for i, (txt, page) in enumerate(grounds[:3], 1):  # 최대 3개
                        lines = [ln.strip() for ln in txt.split("\n") if ln.strip()]
                        if len(lines) > 2:
                            preview = [lines[0], "...(중략)...", lines[-1]]
                        elif len(lines) == 2:
                            preview = [lines[0], "...(중략)...", lines[1]]
                        elif len(lines) == 1:
                            preview = [lines[0]]
                        else:
                            preview = []
                        block = f"**원문 근거 {i}. (p.{page})**\n" + "\n".join(preview)
                        blocks.append(block)
                else:
                    grounds_text = _cleanup_text_for_grounds(str(grounds))
                    lines = [ln.strip() for ln in grounds_text.split("\n") if ln.strip()]
                    if len(lines) > 2:
                        preview = [lines[0], "...(중략)...", lines[-1]]
                    else:
                        preview = lines
                    blocks.append(f"**원문 근거 1.**\n" + "\n".join(preview))

                st.markdown("\n\n".join(blocks), unsafe_allow_html=True)


# ============================ 목차 버튼/프리뷰 ============================
def _render_toc_buttons(items: List[Dict[str, Any]], kind: str, chunks: Dict[str, Any], cols: int = 2):
    """목차 버튼(번호+제목) — 기존 기능 유지"""
    st.markdown(
        """
        <style>
        div[data-testid="stButton"] > button {
            padding: 6px 10px !important;
            font-size: 13px !important;
            line-height: 1.35 !important;
            white-space: normal !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    if not items:
        st.info("목차가 없습니다."); return

    cols_container = st.columns(cols, gap="small")
    for i, it in enumerate(items):
        col = cols_container[i % cols]
        with col:
            label = it.get("label")
            title = (it.get("title") or "").strip()
            text  = f"{'표' if kind=='table' else '그림'} {label}" + (f". {title}" if title else "")

            if st.button(text, key=f"toc-{kind}-{label}"):
                if kind == "table":
                    t   = _find_table_full(chunks, label)
                    q   = f"<표 {label}> 설명해줘"
                    ctx = (t or {}).get("preview_md") or ""
                    nb  = _neighbor_text(chunks, (t or {}).get("page", 0)) if t else ""
                    ans = answer_with_context(q, (ctx + "\n\n" + nb)[:1800], page_label=(t or {}).get("page"))
                    _append_dialog(which="toc", user=q, answer=ans,
                                   item={"kind": "table", "obj": t}, grounds=nb)
                else:
                    f   = _find_figure_full(chunks, label)
                    q   = f"<그림 {label}> 설명해줘"
                    nb  = _neighbor_text(chunks, (f or {}).get("page", 0)) if f else ""
                    img = None
                    try:
                        if f and f.get("bbox") and st.session_state.get("pdf_bytes"):
                            img = crop_figure_image(st.session_state["pdf_bytes"], f["page"] - 1, f["bbox"], dpi=300)
                    except Exception:
                        img = None
                    ans = explain_figure_image(q, img, neighbor_text=nb)
                    _append_dialog(which="toc", user=q, answer=ans,
                                   item={"kind": "figure", "obj": f}, grounds=nb)
                st.rerun()

        # 다음 줄로 개행
        if (i % cols) == (cols - 1) and (i != len(items) - 1):
            cols_container = st.columns(cols, gap="small")


def _render_item_preview(item: Dict[str, Any]):
    """
    표/그림 썸네일:
      - 제목: 이미지 '바로 위' 중앙/볼드
      - 이미지: 본문 폭 사용 + 최대폭 800px 제한(반응형)
    """
    if not item or "obj" not in item: return
    obj = item["obj"]; kind = item["kind"]
    if not obj: return

    # 제목
    title_text = (obj.get("title") or "").strip()
    if not title_text:
        title_text = ("표" if kind == "table" else "그림") + " " + str(obj.get("label"))
    st.markdown(f"<div class='hp-figtitle'>{title_text}</div>", unsafe_allow_html=True)

    # 이미지 크롭
    img = None
    try:
        if kind == "table" and obj.get("bbox") and st.session_state.get("pdf_bytes"):
            img = crop_table_image(st.session_state["pdf_bytes"], obj["page"] - 1, obj["bbox"], dpi=300)
        elif kind == "figure" and obj.get("bbox") and st.session_state.get("pdf_bytes"):
            img = crop_figure_image(st.session_state["pdf_bytes"], obj["page"] - 1, obj["bbox"], dpi=300)
    except Exception:
        img = None

    # 이미지 표시 (최대폭 700px 래퍼 + 반응형)
    if img is not None:
        st.markdown("<div style='max-width:400px /* 🔧 이미지 최대폭을 800→500으로 살짝 축소 (반응형 유지) */;margin:0 auto;'>", unsafe_allow_html=True)
        st.image(img, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)


# ============================== 검색 유틸 ==============================
def _tok(s: str) -> List[str]:
    """간단 토크나이저: 한글/영문 단어 + 숫자(소수/콤마/%)"""
    return re.findall(r"[가-힣A-Za-z]+|\d+(?:[.,]\d+)?%?", (s or "").lower())


def _search_text_pages(query: str, chunks: Dict[str, Any], k: int = 3, per_len: int = 1000) -> List[Dict[str, Any]]:
    """본문 페이지 검색: BM25 있으면 사용, 없으면 키워드 점수"""
    pages = chunks.get("texts", []) or []
    if not pages:
        return []

    docs = [p.get("text") or "" for p in pages]
    pnos = [p.get("page") for p in pages]
    qtok = _tok(query)

    # 1) BM25
    if BM25Okapi is not None:
        tokenized = [_tok(d) for d in docs]
        bm = BM25Okapi(tokenized)
        scores = bm.get_scores(qtok)
        order = sorted(range(len(docs)), key=lambda i: scores[i], reverse=True)[:k]
        out = []
        for i in order:
            txt = docs[i].strip()
            if not txt: continue
            out.append({"page": pnos[i], "snippet": txt[:per_len], "score": float(scores[i])})
        return out

    # 2) 키워드 점수
    weights = {w: 2.0 for w in qtok}
    scored = []
    for i, txt in enumerate(docs):
        toks = _tok(txt)
        if not toks: continue
        score = sum(weights.get(t, 0.0) for t in toks)
        scored.append((i, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    out = []
    for i, sc in scored[:k]:
        t = docs[i].strip()
        if not t: continue
        out.append({"page": pnos[i], "snippet": t[:per_len], "score": float(sc)})
    return out


# ============================== 텍스트 정리 ==============================
def _format_paragraphs(text: str, bullets: bool = False) -> str:
    """
    문단/문장 줄바꿈을 강제하고, 기존에 붙어온 불릿(◦ • - · *) 등을 제거한 뒤
    옵션에 따라 앞에 '◦ '만 붙여 깔끔하게 출력한다.
    """
    if not text:
        return ""

    # 1) <br> 같은 태그가 섞여 오면 개행으로 치환
    t = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)

    # 2) 우선 명시적 개행 기준으로 쪼갬. (없으면 문장부호 기준)
    raw_parts = [p for p in re.split(r"\n+", t) if p.strip()]
    if not raw_parts:
        raw_parts = re.split(r"(?<=[\.!?])\s+(?=[^\s])", t.strip())

    out: List[str] = []
    for p in raw_parts:
        s = p.strip()
        if not s:
            continue
        # 3) 앞에 이미 붙어있는 불릿류 제거 (◦ • · * - – 등)
        s = re.sub(r"^[\u2022•◦\-\–\·\*]+\s*", "", s).strip()

        # 4) 불릿 옵션에 따라 접두어 부착
        out.append(("◦ " + s) if bullets else s)

    # 5) 줄바꿈 유지 (pre-wrap 스타일과 함께 쓰면 원하는 모양)
    return "\n".join(out)

def _cleanup_text_for_grounds(text: str) -> str:
    if not text: 
        return ""
    cleaned: List[str] = []
    for raw in text.split("\n"):
        ln = raw.strip()
        if not ln:
            continue
        # --- 걸러낼 패턴들 ---
        if re.search(r"\|.+\|", ln): continue                     # 표 형태 라인
        if re.match(r"^\s*[-:|]+\s*$", ln): continue              # 구분선
        if re.match(r"^\s*(?:<\s*표|<\s*그림|표\s*\d|그림\s*\d)", ln): continue  # 표/그림 캡션
        if re.match(r"^\s*제?\s*\d+\s*장", ln): continue          # 장 제목
        if re.match(r"^\d{1,2}\s*$", ln): continue                # 숫자 단독
        if ln.lower() in {"목차", "표 목차", "그림 목차", "contents", "table of contents"}: continue
        if re.match(r"^[ivxlcdm]+$", ln.lower()): continue        # 로마 숫자
        if "차트" in ln or "그림" in ln or "표 " in ln: continue  # 목차성 라인
        if "목차" in ln: continue
        # --- 실제 내용만 남기기 ---
        cleaned.append(ln)
    return "\n".join(cleaned)


def _format_answer(answer: str) -> str:
    """LLM 답변을 1. / ◦ 형식으로 문단 나눔"""
    if not answer: return ""
    lines = [ln.strip() for ln in answer.split("\n") if ln.strip()]
    formatted, current = [], []
    for ln in lines:
        if re.match(r"^\d+\.", ln):
            if current: formatted.append("\n".join(current))
            current = [ln]  # 새 항목 시작
        else:
            current.append(f"◦ {ln}" if not ln.startswith("◦") else ln)
    if current: formatted.append("\n".join(current))
    return "\n\n".join(formatted)  # 항목 사이 빈 줄

# 🔧 추가: 근거 상위 3개만 선택
def _select_top_grounds(text: str, max_n: int = 3) -> str:
    if not text: return ""
    sents = re.split(r"(?<=[.!?])\s+", text.strip())
    uniq = []
    for s in sents:
        s = s.strip()
        if not s or s in uniq: continue
        uniq.append(s)
        if len(uniq) >= max_n: break
    return "\n".join([f"◦ {u}" for u in uniq])


# ============================== 헬퍼 ==============================
def _find_table_full(chunks: Dict[str, Any], label: str) -> Optional[Dict[str, Any]]:
    """라벨(예: 2-1)로 표 찾기"""
    for t in chunks.get("tables", []):
        if str(t.get("label", "")).strip() == str(label).strip():
            return t
    return None


def _find_figure_full(chunks: Dict[str, Any], label: str) -> Optional[Dict[str, Any]]:
    """라벨(예: 3-2)로 그림 찾기"""
    for f in chunks.get("figures", []):
        if str(f.get("label", "")).strip() == str(label).strip():
            return f
    return None


def _neighbor_text(chunks: Dict[str, Any], page: int) -> str:
    """해당 페이지 ±1 본문 텍스트 결합"""
    texts = [x for x in chunks.get("texts", []) if abs(x.get("page", 0) - page) <= 1]
    return "\n".join([(t.get("text") or "") for t in texts])[:2500]


def render_markdown_table(md_table: str):
    """
    마크다운 표 문자열을 Pandas DataFrame으로 변환 후 Streamlit 표로 출력
    """
    try:
        lines = [ln.strip() for ln in md_table.splitlines() if "|" in ln]
        if not lines:
            st.markdown(md_table)  # 표가 아니면 그냥 마크다운 출력
            return

        # 첫 줄 = 헤더, 두 번째 줄 = 구분선, 나머지 = 데이터
        header = [h.strip() for h in lines[0].split("|") if h.strip()]
        rows = []
        for ln in lines[2:]:
            parts = [p.strip() for p in ln.split("|")]
            if any(parts):
                row = [p for p in parts if p != ""]
                if row:
                    rows.append(row)

        if not rows:
            st.markdown(md_table)
            return

        df = pd.DataFrame(rows, columns=header)
        st.table(df)  # ✅ 예쁜 Streamlit 표 출력
    except Exception:
        st.markdown(md_table)


# ================================== 표 변환 보조함수 ==================================
# 사용자가 "표"라고 요청했을 때(_qa_pipeline/_qa_pipeline_tables_only 내부)만 호출됩니다.
# - 입력 텍스트(ctx)에 숫자/단위가 충분히 포함되면 LLM에게 "마크다운 표"만 생성하도록 요청
# - 표로 만들기 애매하면 None을 반환해서 상위 로직이 아무 것도 추가하지 않도록 설계
from typing import Optional

def make_table_from_text(text: str, max_chars: int = 1800) -> Optional[str]:
    """
    본문 텍스트에서 수치 나열을 감지하면, 표(마크다운)로 변환해 주는 보조 함수.
    - 반환: 마크다운 표 문자열 또는 None
    - 안전장치:
        * 숫자/단위 패턴이 충분하지 않으면 None
        * 너무 긴 입력은 잘라서 프롬프트에 사용
        * LLM 결과가 표 형태가 아니면 None
        * 과도하게 긴 표는 줄 수를 제한
    """
    if not text:
        return None

    # 1) "표로 만들 가치가 있는가?" 간단 휴리스틱
    #    - 숫자/단위 패턴이 하나도 없으면 표 시도 자체를 하지 않음(불필요한 LLM 호출 방지)
    digit_count = sum(1 for ch in text if ch.isdigit())
    numeric_patterns = [
        r"\d{4}\.\d{1,2}",                   # 2021.10 같은 연-월
        r"\d+(?:,\d{3})+(?:\.\d+)?",         # 12,345.67 같은 천단위+소수
        r"\d+\.\d+",                         # 3.14 같은 소수
        r"\d+%",                             # 퍼센트
        r"\d+\s*(?:원|KRW|만원|억원|조원)",     # 금액/통화
        r"kWh|kW|MW|GWh|tCO2e|ppm|ppb",      # 단위(에너지/환경)
    ]
    looks_numeric = any(re.search(p, text) for p in numeric_patterns)
    if not (looks_numeric or digit_count >= 10):
        return None

    # 2) 과도하게 긴 텍스트는 잘라서 사용 (토큰 낭비 방지)
    src = (text or "")[:max_chars]

    # 3) LLM에 "표만" 생성하도록 명확히 지시 (설명/코드펜스 금지)
    prompt = (
        "아래 텍스트의 수치/단위를 표(마크다운)로만 간결하게 정리해줘.\n"
        "- 마크다운 표만 출력 (설명 문장/코드블록 금지).\n"
        "- 첫 열은 '항목' 또는 '구분'.\n"
        "- 값에는 단위(%, 원, kWh 등)를 포함.\n"
        "- 열은 최대 4개 이내로 요약.\n"
        "- 행/열 제목은 간결하게.\n"
        "- 불필요한 주석/출처/문장 추가 금지.\n\n"
        f"[원문 텍스트]\n{src}"
    )

    try:
        # NOTE: llm.explain_tables를 써도 되지만, 현재 파일에서 이미 쓰는 answer_with_context로 통일
        md = answer_with_context("텍스트를 표로 정리", prompt, page_label=None).strip()
    except Exception:
        return None

    # 4) 모델이 가끔 ```로 감싸는 경우 제거
    md = re.sub(r"^```.*?\n", "", md)
    md = re.sub(r"\n```$", "", md)

    # 5) 최소한의 마크다운 표 형태 검사
    #    - 파이프(|)가 없으면 표가 아님
    if "|" not in md:
        return None

    # 6) 표가 너무 길면 컷 (UI 보호)
    lines = [ln.rstrip() for ln in md.splitlines() if ln.strip()]
    if len(lines) > 50:
        lines = lines[:50] + ["| ... | ... |", "| (중략) | (중략) |"]

    return "\n".join(lines)

# ============================== 스타일 ==============================
def _inject_css():
    """공통/로컬 CSS 주입"""
    base = get_css()
    local = f"""
    <style>
      /* 사용자 질문 말풍선(우측) */
      .hp-msg.user {{ display:flex; justify-content:flex-end; margin: 6px 0; }}
      .hp-msg.user .bubble {{
        background:{ACCENT}; color:#fff; padding:12px 16px; border-radius:16px;
        max-width:72%; font-size:16px; white-space:pre-wrap; box-shadow:0 1px 2px rgba(0,0,0,.06);
      }}

      /* 답변 카드 */
      .hp-card {{ background:#fff; border:1px solid #e9ecef; border-radius:16px;
                 padding:16px 18px; margin:12px 0; box-shadow:0 2px 6px rgba(0,0,0,.04); }}
      .hp-card__title {{ font-weight:900; font-size:25px; margin-bottom:10px; }}
      .hp-card__text {{ white-space:pre-wrap; line-height:1.7; font-size:16px; }}

      /* 원문 요약 박스 */
      .hp-answer-box1 {{
        background:#ffffff;
        padding:12px 14px; font-size:16px; line-height:1.7; white-space:pre-wrap;
      }}

      /* 회색 요약 박스 */
      .hp-answer-box {{
        background:#f5f6f8; border:1px solid #e6e8eb; border-radius:12px;
        padding:14px 16px; font-size:16px; line-height:1.7; white-space:pre-wrap;
      }}

      /* 그림/표 제목 */
      .hp-figtitle {{ text-align:center; font-weight:800; font-size:20px; margin:6px 0 8px 0; }}

      /* 🔧 질문-답변 사이 여백/흰 박스 제거 */
      .hp-msg.user + div:has(.hp-card) {{ margin-top: 0 !important; }}
      .hp-card:first-child {{ margin-top: 6px; }}

      /* ✅ 채팅 입력창을 화면 하단에 고정 (푸터 스타일) */
      section[data-testid="stChatInput"] {{
          position: fixed;
          bottom: 0;
          left: 320px;  /* 사이드바 폭 고려 */
          right: 0;
          background: white;
          padding: 10px 16px;
          border-top: 1px solid #ddd;
          z-index: 100;
      }}
    </style>
    """
    st.markdown(f"<style>{base}</style>", unsafe_allow_html=True)
    st.markdown(local, unsafe_allow_html=True)


# ============================== 엔트리 ==============================
def run():
    route = st.session_state.get("route", "landing")
    if route == "landing":
        landing_page()
    elif route == "loading":
        loading_page()
    else:
        analysis_page()
