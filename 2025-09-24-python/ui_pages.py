# ui_pages.py — 최신 반영본
# 구조:
# 사용자 질문 (오른쪽 말풍선)
# Hi-Lens의 답변 (타이틀)
#   └ 표/그림 제목
#   └ 표/그림 이미지
#   └ LLM 요약 (줄글, 문장 단위 줄바꿈)
#   └ 📑 원문 근거 (줄글, 표 제거, 문장 단위 줄바꿈)

from __future__ import annotations
import time, hashlib, datetime as dt, re
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
from rag import RAGIndex


# ================================ 세션/유틸 ================================
def _init_session_defaults():
    st.session_state.setdefault("route", "landing")
    st.session_state.setdefault("pdf_bytes", None)
    st.session_state.setdefault("pdf_name", "")
    st.session_state.setdefault("chunks", {})
    st.session_state.setdefault("summary", "")
    st.session_state.setdefault("chat", [])
    st.session_state.setdefault("toc_dialogs", [])
    st.session_state.setdefault("_threads", [])
    st.session_state.setdefault("_current_tid", None)


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
    st.markdown(f"<style>{get_css()}</style>", unsafe_allow_html=True)
    render_sidebar()
    st.markdown("<h1 style='font-weight:900;'>👋 Hi-Lens</h1>", unsafe_allow_html=True)
    st.markdown("PDF에서 표/그림/문단을 추출해 **질문 → 표/그래프/요약**으로 재구성합니다.", unsafe_allow_html=True)
    upl = st.file_uploader("분석할 PDF를 업로드하세요", type=["pdf"], key="landing_upl")
    if st.button("🔍 분석 시작", use_container_width=True):
        if not upl: st.warning("먼저 PDF를 업로드해주세요."); st.stop()
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
    st.markdown("<style>section[data-testid='stSidebar']{display:none;} header,footer{display:none;}</style>", unsafe_allow_html=True)
    st.markdown("<div style='text-align:center;margin-top:120px;'><h2>Hi-Lens가 분석중입니다...</h2></div>", unsafe_allow_html=True)
    bar = st.progress(0.0, text="PDF 처리 시작")
    pdf_bytes = st.session_state.get("pdf_bytes")
    if not pdf_bytes: st.warning("업로드된 PDF가 없습니다."); return
    chunks = build_chunks(pdf_bytes)
    def _cb(msg, ratio): bar.progress(ratio, text=msg)
    summary = summarize_from_chunks(chunks, max_pages=20, progress_cb=_cb)
    st.session_state["chunks"], st.session_state["summary"] = chunks, summary
    th = _current_thread()
    if th: th.update({"chunks": chunks, "summary": summary})
    st.session_state["route"] = "analysis"; st.rerun()


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
        f"<div class='summary'>텍스트 {n_x} · 표 {n_t} · 그림 {n_f}</div></div>", unsafe_allow_html=True
    )

    tab_chat, tab_toc = st.tabs(["💬 대화", "📑 표·그림 목차"])

    # ----------------------- 대화 탭 -----------------------
    with tab_chat:
        usr_q = st.chat_input("Hi-Lens에게 질문해보세요.", key="inp-chat")
        if usr_q and usr_q.strip():
            context = "\n".join([x.get("text", "") for x in chunks.get("texts", [])[:6]])[:3000]
            ans = answer_with_context(usr_q, context, page_label="?")
            _append_dialog(which="chat", user=usr_q, answer=ans, grounds=context)
            st.rerun()

        with st.expander("원문 요약", expanded=False):
            if summary:
                clean = summary.replace("#### 문서 요약", "").replace("문서 요약", "")
                lines = [ln.strip() for ln in clean.splitlines() if ln.strip()]
                st.write("\n".join(lines))
            else:
                st.info("요약이 아직 준비되지 않았습니다.")

        with st.expander("추천 질문", expanded=False):
            recos = QA_RECOMMENDATIONS.get(pdf_name, {})
            for i, (_, data) in enumerate(recos.items()):
                if st.button(data["question"], key=f"recbtn-{i}"):
                    _append_dialog(which="chat", user=data["question"], answer=data["answer"], grounds=data.get("grounds"))
                    st.rerun()

        _render_dialogs("chat", scroll_height=600)

    # ------------------- 표·그림 목차 탭 -------------------
    with tab_toc:
        toc_q = st.chat_input("표·그림에 대해 더 궁금한 내용을 물어보세요.", key="inp-toc")
        if toc_q and toc_q.strip():
            rag = RAGIndex(); rag.build_from_chunks(chunks)
            results = rag.search_tables(toc_q, k=3)
            if results:
                table_ctxs = []
                for r in results:
                    nb = _neighbor_text(chunks, r.get("page", 0))
                    table_ctxs.append({
                        "preview_md": r.get("text", ""),
                        "page_label": r.get("page_label", "?"),
                        "title": r.get("title", ""),
                        "neighbor_text": nb,
                    })
                ans = explain_tables(toc_q, table_ctxs)
                grounds = "\n\n".join([c["neighbor_text"] for c in table_ctxs if c.get("neighbor_text")])
            else:
                ans, grounds = "관련 표를 찾지 못했습니다.", ""
            _append_dialog(which="toc", user=toc_q, answer=ans, grounds=grounds)
            st.rerun()

        with st.expander("목차 보기", expanded=False):
            toc_tab1, toc_tab2 = st.tabs(["표 목차", "그림 목차"])
            with toc_tab1:
                _render_toc_buttons(chunks.get("toc", {}).get("tables", []), kind="table", chunks=chunks, cols=10)
            with toc_tab2:
                _render_toc_buttons(chunks.get("toc", {}).get("figures", []), kind="figure", chunks=chunks, cols=10)

        _render_dialogs("toc", scroll_height=600)


# ================================ 대화/렌더 ================================
def _append_dialog(which: str, user: str, answer: str, item: Optional[Dict] = None, grounds: Optional[str] = None):
    key = "toc_dialogs" if (which == "toc" or item) else "chat"
    dialogs = st.session_state.setdefault(key, [])
    dialogs.append({"user": user, "answer": answer, "item": item, "grounds": grounds})


def _render_dialogs(which: str, scroll_height: int = 600):
    dialogs = st.session_state.get("toc_dialogs" if which == "toc" else "chat", [])
    box = st.container(height=scroll_height)
    with box:
        for d in dialogs:
            # 사용자 질문 (오른쪽 말풍선)
            st.markdown(
                f"""
                <div style="display:flex;justify-content:flex-end;margin:6px 0;">
                    <div style="background:{ACCENT};color:white;
                                padding:8px 12px;border-radius:14px;max-width:70%;font-size:14px;">
                        {d['user']}
                    </div>
                </div>
                """, unsafe_allow_html=True
            )

            # Hi-Lens 답변 타이틀
            st.markdown("**Hi-Lens의 답변**")

            # 표/그림 제목 + 이미지
            if d.get("item"):
                obj = d["item"]["obj"]
                if obj and obj.get("title"):
                    st.markdown(f"**{obj['title']}**")
                _render_item_preview(d["item"])

            # LLM 요약 (문장 단위 줄바꿈)
            formatted = _format_paragraphs(d["answer"])
            st.markdown(
                f"<div style='text-align:left;background:#f8f9fa;padding:10px 14px;"
                f"border-radius:14px;margin:6px 0;white-space:pre-wrap;font-size:14px;'>{formatted}</div>",
                unsafe_allow_html=True,
            )

            # 원문 근거 (줄글, 표 제거)
            if d.get("grounds"):
                with st.expander("📑 원문 근거 보기", expanded=False):
                    grounds_text = re.sub(r"\|.*\|", "", d["grounds"])  # 표 제거
                    formatted_ground = _format_paragraphs(grounds_text)
                    st.markdown(f"<div style='white-space:pre-wrap'>{formatted_ground}</div>", unsafe_allow_html=True)

            st.markdown("<hr style='margin:12px 0;'>", unsafe_allow_html=True)


# ============================ 목차 버튼/프리뷰 ============================
def _render_toc_buttons(items: List[Dict[str, Any]], kind: str, chunks: Dict[str, Any], cols: int = 10):
    st.markdown(
        """
        <style>
        div[data-testid="stButton"] > button {
            padding: 4px 8px !important;
            font-size: 13px !important;
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
            text  = f"{'표' if kind=='table' else '그림'}<{label}>"
            if st.button(text, key=f"toc-{kind}-{label}"):
                if kind == "table":
                    t   = _find_table_full(chunks, label)
                    q   = f"<표 {label}> 설명해줘"
                    ctx = (t or {}).get("preview_md") or ""
                    nb  = _neighbor_text(chunks, (t or {}).get("page", 0)) if t else ""
                    ans = answer_with_context(q, (ctx + "\n\n" + nb)[:1800], page_label=(t or {}).get("page"))
                    _append_dialog(which="toc", user=q, answer=ans,
                                   item={"kind": "table", "obj": t},
                                   grounds=nb)
                else:
                    f   = _find_figure_full(chunks, label)
                    q   = f"<그림 {label}> 설명해줘"
                    nb  = _neighbor_text(chunks, (f or {}).get("page", 0)) if f else ""
                    ctx = (f or {}).get("preview_md", "") or ""
                    ans = answer_with_context(q, (ctx + "\n\n" + nb)[:1800], page_label=(f or {}).get("page"))
                    _append_dialog(which="toc", user=q, answer=ans,
                                   item={"kind": "figure", "obj": f},
                                   grounds=nb)
                st.rerun()
        if (i % cols) == (cols - 1) and (i != len(items) - 1):
            cols_container = st.columns(cols, gap="small")


def _render_item_preview(item: Dict[str, Any]):
    """표/그림 썸네일"""
    if not item or "obj" not in item: return
    obj = item["obj"]
    if not obj: return

    img, caption = None, ""
    if item["kind"] == "table" and obj.get("bbox") and st.session_state.get("pdf_bytes"):
        img = crop_table_image(st.session_state["pdf_bytes"], obj["page"] - 1, obj["bbox"], dpi=300)
        caption = f"<표 {obj.get('label')}> p.{obj.get('page')}"
    elif item["kind"] == "figure" and obj.get("bbox") and st.session_state.get("pdf_bytes"):
        img = crop_figure_image(st.session_state["pdf_bytes"], obj["page"] - 1, obj["bbox"], dpi=300)
        caption = f"[그림 {obj.get('label')}] p.{obj.get('page')}"
    else:
        return

    try:
        st.image(img, caption=caption, width=700, use_container_width=False)
    except TypeError:
        st.image(img, caption=caption, width=700)


# ============================== 포맷/헬퍼 ===============================
def _format_paragraphs(text: str) -> str:
    """문장 단위로 줄바꿈"""
    if not text: return ""
    sentences = re.split(r"(?<=[다임음요]\.)\s+", text)
    out = []
    for s in sentences:
        s = s.strip()
        if s:
            out.append(s)
    return "\n".join(out)


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
    """해당 페이지 ±1 본문 텍스트"""
    texts = [x for x in chunks.get("texts", []) if abs(x.get("page", 0) - page) <= 1]
    return "\n".join([(t.get("text") or "") for t in texts])[:2500]


# ============================== 엔트리 ===============================
def run():
    route = st.session_state.get("route", "landing")
    if route == "landing":
        landing_page()
    elif route == "loading":
        loading_page()
    else:
        analysis_page()
