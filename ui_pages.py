# ui_pages.py (최종 수정본)
# ---------------------------------------------------------------
# ✅ 반영 사항
# - 표/그림 목차: 가로로 ‘따닥따닥’ 붙는 그리드 배치 (10열, 자동 줄바꿈)
# - 유저 말풍선: 오른쪽 정렬(포인트컬러), 선택 이미지: 중앙정렬(폭 600 고정)
# - AI 답변: 왼쪽 정렬, 불릿 처리, 질문 간 구분선
# - 하단 입력창: 탭마다 고정 느낌으로 노출(내용만 스크롤)
# - 여백 최소화(목차 버튼, 문단 공백)
# - ⬆️ 추가 반영:
#   1) 표/그림 프리뷰 중앙 정렬
#   2) 요약 들여쓰기 제거
#   3) 대화/표그림 탭 입력 분리
#   4) LLM 연결 (본문=answer_with_context, 표=RAG+explain_tables)
# ---------------------------------------------------------------
from __future__ import annotations
import time, hashlib, datetime as dt
from typing import Dict, Any, List, Optional

import streamlit as st
from styles import get_css, ACCENT
from extract import build_chunks, crop_table_image
try:
    from extract import crop_figure_image
except Exception:
    crop_figure_image = crop_table_image

from llm import answer_with_context, get_provider_name, explain_tables
from summarizer import summarize_from_chunks
from qa_recos import QA_RECOMMENDATIONS
from rag import RAGIndex  # 🔑 RAG 검색 사용


# ───────────────────────────────────────────────
# 세션 초기화/관리
# ───────────────────────────────────────────────
def _init_session_defaults():
    st.session_state.setdefault("route", "landing")
    st.session_state.setdefault("pdf_bytes", None)
    st.session_state.setdefault("pdf_name", "")
    st.session_state.setdefault("chunks", {})
    st.session_state.setdefault("summary", "")
    st.session_state.setdefault("chat", [])
    st.session_state.setdefault("_threads", [])
    st.session_state.setdefault("_current_tid", None)
    st.session_state.setdefault("toc_dialogs", [])


def _pdf_id() -> Optional[str]:
    data = st.session_state.get("pdf_bytes")
    return hashlib.sha1(data).hexdigest()[:12] if data else None


def _threads() -> List[Dict[str, Any]]:
    return st.session_state.setdefault("_threads", [])


def _current_thread() -> Optional[Dict[str, Any]]:
    tid = st.session_state.get("_current_tid")
    for t in _threads():
        if t["tid"] == tid:
            return t
    return None


def _ensure_thread():
    if _current_thread():
        return
    pid = _pdf_id()
    name = st.session_state.get("pdf_name") or "문서"
    tid = f"{pid}-{int(time.time())}"
    _threads().append(
        {
            "tid": tid,
            "pdf_id": pid,
            "pdf_name": name,
            "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "messages": [],
            "pdf_bytes": st.session_state.get("pdf_bytes"),
            "chunks": {},
            "summary": "",
        }
    )
    st.session_state["_current_tid"] = tid


# ───────────────────────────────────────────────
# 사이드바
# ───────────────────────────────────────────────
def render_sidebar():
    st.sidebar.markdown(
        "<div class='hp-brand'><span class='dot'></span>Hi-Lens</div>",
        unsafe_allow_html=True,
    )
    st.sidebar.caption("PDF 요약·발췌·시각화 도우미")
    st.sidebar.info(f"LLM: {get_provider_name()}", icon="🧠")

    if st.sidebar.button("🏠 홈으로", use_container_width=True):
        st.session_state["route"] = "landing"
        st.experimental_rerun()

    st.sidebar.markdown("---")
    st.sidebar.subheader("PDF 분석 기록")
    for t in reversed(_threads()):
        label = f"📄 {t['pdf_name']} · {t['ts']} · 질문 {len(t['messages'])}개"
        if st.sidebar.button(label, key=f"hist-{t['tid']}", use_container_width=True):
            st.session_state.update(
                {
                    "_current_tid": t["tid"],
                    "pdf_name": t["pdf_name"],
                    "pdf_bytes": t.get("pdf_bytes"),
                    "chunks": t.get("chunks", {}),
                    "summary": t.get("summary", ""),
                    "chat": t.get("messages", []),
                    "route": "analysis",
                }
            )
            st.experimental_rerun()


# ───────────────────────────────────────────────
# 랜딩 / 로딩
# ───────────────────────────────────────────────
def landing_page():
    _init_session_defaults()
    st.markdown(f"<style>{get_css()}</style>", unsafe_allow_html=True)
    render_sidebar()

    st.markdown("<h1 style='font-weight:900;'>👋 Hi-Lens</h1>", unsafe_allow_html=True)
    st.markdown("PDF에서 표/그림/문단을 추출해 **질문 → 표/그래프/요약**으로 재구성합니다.", unsafe_allow_html=True)

    upl = st.file_uploader("분석할 PDF를 업로드하세요", type=["pdf"], key="landing_upl")
    if st.button("🔍 분석 시작", use_container_width=True):
        if not upl:
            st.warning("먼저 PDF를 업로드해주세요.")
            st.stop()
        pdf_bytes = upl.read()
        pdf_name = upl.name
        pdf_id = hashlib.sha1(pdf_bytes).hexdigest()[:12]
        tid = f"{pdf_id}-{int(time.time())}"
        _threads().append(
            {
                "tid": tid,
                "pdf_id": pdf_id,
                "pdf_name": pdf_name,
                "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "messages": [],
                "pdf_bytes": pdf_bytes,
                "chunks": {},
                "summary": "",
            }
        )
        st.session_state.update(
            {"_current_tid": tid, "pdf_bytes": pdf_bytes, "pdf_name": pdf_name, "route": "loading"}
        )
        st.rerun()


def loading_page():
    _init_session_defaults()
    st.markdown(
        "<style>section[data-testid='stSidebar']{display:none;} header,footer{display:none;}</style>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='text-align:center;margin-top:120px;'><h2>Hi-Lens가 분석중입니다...</h2></div>", unsafe_allow_html=True)
    bar = st.progress(0.0, text="PDF 처리 시작")

    pdf_bytes = st.session_state.get("pdf_bytes")
    if not pdf_bytes:
        st.warning("업로드된 PDF가 없습니다.")
        return

    chunks = build_chunks(pdf_bytes)
    def _cb(msg, ratio): bar.progress(ratio, text=msg)
    summary = summarize_from_chunks(chunks, max_pages=20, progress_cb=_cb)

    st.session_state["chunks"] = chunks
    st.session_state["summary"] = summary
    th = _current_thread()
    if th: th.update({"chunks": chunks, "summary": summary})

    st.session_state["route"] = "analysis"; st.rerun()


# ───────────────────────────────────────────────
# 분석 페이지
# ───────────────────────────────────────────────
def analysis_page():
    _init_session_defaults()
    st.markdown(f"<style>{get_css()}</style>", unsafe_allow_html=True)
    render_sidebar()

    pdf_name = st.session_state.get("pdf_name") or "분석 문서"
    chunks   = st.session_state.get("chunks") or {}
    summary  = st.session_state.get("summary") or ""
    _ensure_thread()

    n_t, n_f, n_x = len(chunks.get("tables", [])), len(chunks.get("figures", [])), len(chunks.get("texts", []))
    st.markdown(
        f"<div class='hp-header'><div class='title'>📄 {pdf_name}</div>"
        f"<div class='summary'>텍스트 {n_x} · 표 {n_t} · 그림 {n_f}</div></div>",
        unsafe_allow_html=True,
    )

    tab_chat, tab_toc = st.tabs(["💬 대화", "📑 표·그림 목차"])

    # === 대화 탭 ===
    with tab_chat:
        with st.expander("원문 요약", expanded=False):
            if summary:
                clean = summary.replace("#### 문서 요약", "").replace("문서 요약", "")
                lines = [ln.strip() for ln in clean.splitlines() if ln.strip()]
                st.write("\n".join(lines))  # 🔧 들여쓰기 제거
            else:
                st.info("요약이 아직 준비되지 않았습니다.")

        with st.expander("추천 질문", expanded=False):
            recos = QA_RECOMMENDATIONS.get(pdf_name, {})
            for i, (qid, data) in enumerate(recos.items()):
                if st.button(data["question"], key=f"recbtn-{i}"):
                    _append_dialog(user=data["question"], answer=data["answer"])
                    st.experimental_rerun()

        _render_dialogs("chat", scroll_height=600)
        _fixed_input("chat")

    # === 표·그림 목차 탭 ===
    with tab_toc:
        with st.expander("목차 보기", expanded=False):
            toc_tab1, toc_tab2 = st.tabs(["표 목차", "그림 목차"])
            with toc_tab1:
                _render_toc_buttons(chunks.get("toc", {}).get("tables", []), kind="table", chunks=chunks, cols=10)
            with toc_tab2:
                _render_toc_buttons(chunks.get("toc", {}).get("figures", []), kind="figure", chunks=chunks, cols=10)

        _render_dialogs("toc", scroll_height=600)
        _fixed_input("toc")


# ───────────────────────────────────────────────
# 하단 고정 입력창 (탭별 + LLM 연결)
# ───────────────────────────────────────────────
def _fixed_input(which: str):
    st.markdown(
        """
        <style>
        .fixed-input {
            position: sticky;
            bottom: -20px;
            background: white;
            padding: 12px 0 6px 0;
            z-index: 5;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="fixed-input">', unsafe_allow_html=True)
    prompt = "Hi-Lens에게 질문해보세요." if which == "chat" else "이 표/그림에 대해 Hi-Lens에게 질문해보세요."
    usr_q = st.chat_input(prompt, key=f"inp-{which}")

    if usr_q and usr_q.strip():
        chunks = st.session_state.get("chunks") or {}

        if which == "chat":
            # 본문 일부를 모아서 LLM 호출
            context = "\n".join([x.get("text", "") for x in chunks.get("texts", [])[:3]])[:1500]
            ans = answer_with_context(usr_q, context, page_label="?")
            _append_dialog(user=usr_q, answer=ans)

        else:  # toc 탭 → 표 검색 후 LLM 호출
            rag = RAGIndex()
            rag.build_from_chunks(chunks)
            results = rag.search_tables(usr_q, k=2)
            if results:
                table_ctxs = [
                    {"preview_md": r["text"], "page_label": r["page_label"], "title": r.get("title", "")}
                    for r in results
                ]
                ans = explain_tables(usr_q, table_ctxs)
            else:
                ans = "관련 표를 찾지 못했습니다."
            _append_dialog(user=usr_q, answer=ans)

        st.experimental_rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# ───────────────────────────────────────────────
# 대화 렌더링
# ───────────────────────────────────────────────
def _append_dialog(user: str, answer: str, item: Optional[Dict] = None):
    is_toc = bool(item or user.strip().startswith("<표") or user.strip().startswith("<그림"))
    dialogs = st.session_state.setdefault("toc_dialogs" if is_toc else "chat", [])
    dialogs.append({"user": user, "answer": answer, "item": item})


def _render_dialogs(which: str, scroll_height: int = 600):
    dialogs = st.session_state.get("toc_dialogs" if which == "toc" else "chat", [])
    box = st.container(height=scroll_height)
    with box:
        for d in dialogs:
            # 사용자 말풍선
            st.markdown(
                f"""
                <div style="display:flex;justify-content:flex-end;margin:6px 0;">
                    <div style="background:{ACCENT};color:white;
                                padding:10px 14px;border-radius:14px;max-width:70%;">
                        {d['user']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # 선택된 표/그림 프리뷰 (중앙 정렬 보장)
            if d.get("item"):
                st.markdown("<div style='display:flex;justify-content:center;width:100%;'>", unsafe_allow_html=True)
                _render_item_preview(d["item"])
                st.markdown("</div>", unsafe_allow_html=True)

            # AI 답변
            st.markdown("**Hi-Lens의 답변**")
            formatted = _format_answer(d["answer"])
            st.markdown(
                f"""
                <div style='text-align:left;background:#f8f9fa;
                            padding:10px 14px;border-radius:14px;
                            margin:6px 0;white-space:pre-wrap;'>
                    {formatted}
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown("<hr style='margin:12px 0;'>", unsafe_allow_html=True)


# ───────────────────────────────────────────────
# 목차 버튼 (그리드)
# ───────────────────────────────────────────────
def _render_toc_buttons(items: List[Dict[str, Any]], kind: str, chunks: Dict[str, Any], cols: int = 10):
    st.markdown(
        """
        <style>
        div[data-testid="stButton"] { margin: 0 6px 6px 0 !important; }
        div[data-testid="stButton"] > button { padding: 6px 12px !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    if not items:
        st.info("목차가 없습니다.")
        return

    cols_container = st.columns(cols, gap="small")
    for i, it in enumerate(items):
        col = cols_container[i % cols]
        with col:
            label = it["label"]
            text = f"{'표' if kind=='table' else '그림'}<{label}>"
            if st.button(text, key=f"toc-{kind}-{label}"):
                q = f"<{'표' if kind=='table' else '그림'} {label}> 설명해줘"
                if kind == "table":
                    t = _find_table_full(chunks, label)
                    ctx = t.get("preview_md") or "" if t else ""
                    ans = answer_with_context(q, ctx[:1000], page_label=t["page"]) if t else ""
                    _append_dialog(user=q, answer=ans, item={"kind": "table", "obj": t})
                else:
                    f = _find_figure_full(chunks, label)
                    ctx_text = _neighbor_text(chunks, f["page"]) if f else ""
                    ans = answer_with_context(q, ctx_text[:1000], page_label=f["page"]) if f else ""
                    _append_dialog(user=q, answer=ans, item={"kind": "figure", "obj": f})
                st.experimental_rerun()

        if (i % cols) == (cols - 1) and (i != len(items) - 1):
            cols_container = st.columns(cols, gap="small")


# ───────────────────────────────────────────────
# 선택 아이템(표/그림) 프리뷰
# ───────────────────────────────────────────────
def _render_item_preview(item: Dict[str, Any]):
    if not item or "obj" not in item:
        return
    obj = item["obj"]
    if not obj:
        return

    if item["kind"] == "table" and obj.get("bbox") and st.session_state.get("pdf_bytes"):
        img = crop_table_image(st.session_state["pdf_bytes"], obj["page"] - 1, obj["bbox"], dpi=220)
        st.image(img, caption=f"<표 {obj['label']}> p.{obj['page']}", use_column_width=False, width=600)
    elif item["kind"] == "figure" and obj.get("bbox") and st.session_state.get("pdf_bytes"):
        img = crop_figure_image(st.session_state["pdf_bytes"], obj["page"] - 1, obj["bbox"], dpi=220)
        st.image(img, caption=f"[그림 {obj['label']}] p.{obj['page']}", use_column_width=False, width=600)


# ───────────────────────────────────────────────
# 답변 포맷
# ───────────────────────────────────────────────
def _format_answer(text: str) -> str:
    if not text:
        return ""
    lines: List[str] = []
    for ln in text.split("* "):
        if ln.strip():
            clean = ln.strip().lstrip("*").strip()
            lines.append("• " + clean)
    return "\n".join(lines)


# ───────────────────────────────────────────────
# 헬퍼
# ───────────────────────────────────────────────
def _find_table_full(chunks: Dict[str, Any], label: str) -> Optional[Dict[str, Any]]:
    for t in chunks.get("tables", []):
        if str(t.get("label", "")).strip() == str(label).strip():
            return t
    return None


def _find_figure_full(chunks: Dict[str, Any], label: str) -> Optional[Dict[str, Any]]:
    for f in chunks.get("figures", []):
        if str(f.get("label", "")).strip() == str(label).strip():
            return f
    return None


def _neighbor_text(chunks: Dict[str, Any], page: int) -> str:
    texts = [x for x in chunks.get("texts", []) if abs(x.get("page", 0) - page) <= 1]
    return "\n".join([(t.get("text") or "") for t in texts])[:1800]


# ───────────────────────────────────────────────
# 진입점
# ───────────────────────────────────────────────
def run():
    route = st.session_state.get("route", "landing")
    if route == "landing":
        landing_page()
    elif route == "loading":
        loading_page()
    else:
        analysis_page()
