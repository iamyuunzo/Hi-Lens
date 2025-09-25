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

from __future__ import annotations
import time, hashlib, datetime as dt, re
from typing import Dict, Any, List, Optional

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
    _inject_css()
    render_sidebar()

    pdf_name = st.session_state.get("pdf_name") or "분석 문서"
    chunks   = st.session_state.get("chunks") or {}
    summary  = st.session_state.get("summary") or ""
    _ensure_thread()

    n_t, n_f, n_x = len(chunks.get("tables", [])), len(chunks.get("figures", [])), len(chunks.get("texts", []))
    st.markdown(
        f"<div class='hp-header'><div class='title'>📄 {pdf_name}</div>"
        f"<div class='summary'>텍스트 {n_x} · 표 {n_t} · 그림 {n_f}</div></div>", unsafe_allow_html=True
    )

    tab_chat, tab_toc = st.tabs(["💬 대화", "📑 표·그림 목차"])

    # ----------------------- 대화 탭 (전체 원문 QA) -----------------------
    with tab_chat:
        usr_q = st.chat_input("PDF 원문에 대해 질문해보세요.", key="inp-chat")
        if usr_q and usr_q.strip():
            ans, grounds = _qa_pipeline(usr_q, chunks)   # 전체 원문 대상
            _append_dialog(which="chat", user=usr_q, answer=ans, grounds=grounds)
            st.rerun()

        # 원문 요약
        with st.expander("원문 요약", expanded=False):
            if summary:
                st.write(_format_paragraphs(summary, bullets=True))
            else:
                st.info("요약이 아직 준비되지 않았습니다.")

        # 추천 질문
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

    # ------------------- 표·그림 목차 탭 (표/그림 중심 QA) -------------------
    with tab_toc:
        # 대화탭과 '완전히 동일한' chat_input UI
        toc_q = st.chat_input("표·그림에 대해 질문해보세요.", key="inp-toc")
        if toc_q and toc_q.strip():
            ans, grounds = _qa_pipeline_tables_only(toc_q, chunks)  # 표/그림 중심
            _append_dialog(which="toc", user=toc_q, answer=ans, grounds=grounds)
            st.rerun()

        # 목차 토글(표/그림 버튼): 기존 기능 유지
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


# ============================ QA 파이프라인 ============================
def _qa_pipeline(query: str, chunks: Dict[str, Any]) -> (str, str):
    """전체 원문 QA: 표 RAG + 본문 검색 결합"""
    table_parts: List[str] = []
    grounds_parts: List[str] = []

    rag = RAGIndex(); rag.build_from_chunks(chunks)

    # 1) 표/그림 관련 상위
    table_hits = rag.search_tables(query, k=3)
    for hit in range(len(table_hits)):
        pass
    table_hits = rag.search_tables(query, k=3)
    for hit in table_hits:
        title = (hit.get("title") or "").strip()
        pno   = hit.get("page_label", "?")
        prev  = (hit.get("text") or "").strip()
        nb    = _neighbor_text(chunks, hit.get("page_index", 0) + 1)
        table_parts.append(f"(표/그림 p.{pno}) {title}\n{prev}\n{nb}")
        if nb: grounds_parts.append(nb)

    # 2) 본문 텍스트 검색
    text_hits = _search_text_pages(query, chunks, k=3, per_len=1200)
    for h in text_hits:
        table_parts.append(f"(본문 p.{h['page']})\n{h['snippet']}")
        grounds_parts.append(h["snippet"])

    # 3) 컨텍스트 합성
    ctx = "\n\n---\n\n".join([p for p in table_parts if p]).strip()
    if not ctx:
        ctx = "\n".join([(t.get("text") or "") for t in chunks.get("texts", [])[:3]])[:2000]

    ans = answer_with_context(query, ctx, page_label=None)
    grounds = _cleanup_text_for_grounds("\n\n".join(grounds_parts))
    return ans, grounds


def _qa_pipeline_tables_only(query: str, chunks: Dict[str, Any]) -> (str, str):
    """표/그림 중심 QA: 표/그림 미리보기 + 인접 본문만 사용"""
    table_parts: List[str] = []
    grounds_parts: List[str] = []

    rag = RAGIndex(); rag.build_from_chunks(chunks)
    hits = rag.search_tables(query, k=5)
    for hit in hits:
        title = (hit.get("title") or "").strip()
        pno   = hit.get("page_label", "?")
        prev  = (hit.get("text") or "").strip()
        nb    = _neighbor_text(chunks, hit.get("page_index", 0) + 1)
        table_parts.append(f"(표/그림 p.{pno}) {title}\n{prev}\n{nb}")
        if nb: grounds_parts.append(nb)

    ctx = "\n\n".join([p for p in table_parts if p]).strip()[:4000]
    if not ctx:
        # 표/그림이 없으면 최소한의 본문 제공(빈응답 방지)
        ctx = "\n".join([(t.get("text") or "") for t in chunks.get("texts", [])[:2]])[:1500]

    ans = answer_with_context(query, ctx, page_label=None)
    grounds = _cleanup_text_for_grounds("\n\n".join(grounds_parts))
    return ans, grounds


# ================================ 대화/렌더 ================================
def _append_dialog(which: str, user: str, answer: str, item: Optional[Dict] = None, grounds: Optional[str] = None):
    """대화/목차 탭 메시지 추가"""
    key = "toc_dialogs" if (which == "toc" or item) else "chat"
    st.session_state.setdefault(key, []).append({"user": user, "answer": answer, "item": item, "grounds": grounds})


def _render_dialogs(which: str):
    dialogs = st.session_state.get("toc_dialogs" if which == "toc" else "chat", [])
    for d in dialogs:
        st.markdown(f"<div class='hp-msg user'><div class='bubble'>{d['user']}</div></div>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center;'> </p>", unsafe_allow_html=True)
        st.markdown("<div class='hp-card__title'>🤔 Hi-Lens의 답변</div>", unsafe_allow_html=True)

        if d.get("item"):
            _render_item_preview(d["item"])

        # Hi-Lens 답변 (회색 박스 → 단락형)
        formatted = _format_paragraphs(d["answer"], bullets=False)
        st.markdown(f"<div class='hp-answer-box'>{formatted}</div>", unsafe_allow_html=True)

        # 원문 근거 (번호 매기기)
        if d.get("grounds"):
            with st.expander("📑 원문 근거 보기", expanded=False):
                grounds_text = _cleanup_text_for_grounds(d["grounds"])
                top3 = _select_top_grounds(grounds_text, max_n=3)
                numbered = []
                for i, line in enumerate(top3.split("\n"), 1):
                    numbered.append(f"{i}. {line}")
                st.markdown("\n".join(numbered))


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
    if not text: return ""
    sents = re.split(r"(?<=[\.!?])\s+(?=[^\s])", text.strip())
    out = []
    for s in sents:
        s = s.strip()
        if not s: continue
        out.append(("◦ " + s) if bullets else s)
    return "\n".join(out)

def _cleanup_text_for_grounds(text: str) -> str:
    if not text: return ""
    cleaned: List[str] = []
    for raw in text.split("\n"):
        ln = raw.strip()
        if not ln: continue
        if re.search(r"\|.+\|", ln): continue
        if re.match(r"^\s*[-:|]+\s*$", ln): continue
        if re.match(r"^\s*(?:<\s*표|[\[\(]?\s*그림)\s*\d", ln): continue
        if re.match(r"^\s*제?\s*\d+\s*장", ln): continue
        if re.match(r"^\d{1,2}\s*$", ln): continue
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
