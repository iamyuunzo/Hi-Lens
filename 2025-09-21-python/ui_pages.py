# ui_pages.py
# -*- coding: utf-8 -*-
from __future__ import annotations

"""
화면 구성 (UI 전용 수정)
- 랜딩: 상단 유령 입력박스만 숨기고(업로더는 유지), 컨테이너를 중앙 정렬 + 상단 고정 여백(--header-gap)
- 공통 사이드바: PDF 단위 기록/복원
- 분석: 기존 기능/로직 유지
"""

import re
import hashlib
import time
import datetime as dt
from typing import Dict, Any, List, Tuple, Optional

import streamlit as st
from styles import get_css

from extract import (
    build_chunks, find_table_by_label, find_figure_by_label,
    crop_table_image, crop_figure_image,
)

# ===== LLM 어댑터(없으면 폴백) =====
try:
    from llm import answer_with_context
except Exception:
    def answer_with_context(q: str, ctx: str) -> str:
        lines = [ln.strip() for ln in (ctx or "").splitlines() if ln.strip()]
        return "요약: " + (lines[0][:220] if lines else (ctx or "")[:220])

try:
    from llm import generate_query_tags
except Exception:
    def generate_query_tags(pages: List[Dict], k: int = 12) -> List[str]:
        txt = " ".join(p.get("text","") for p in pages)
        years = sorted(set(re.findall(r"20\\d{2}", txt)))[-3:]
        base = [f"{'~'.join(years)} 연도별 지표 비교해줘"] if years else []
        base += [w+" 추이를 표로 보여줘" for w in ["가구원수","에너지","도시가스","연료비","소비지출"]]
        out, seen = [], set()
        for t in base:
            t = re.sub(r"\\s+", " ", t).strip()
            if t and t not in seen:
                out.append(t); seen.add(t)
            if len(out) >= k: break
        return out

# ================== 세션/스레드 유틸 ==================
def _pdf_id() -> Optional[str]:
    data = st.session_state.get("pdf_bytes")
    return hashlib.sha1(data).hexdigest()[:12] if data else None

def _threads() -> List[Dict[str,Any]]:
    return st.session_state.setdefault("_threads", [])

def _find_thread(tid: str) -> Optional[Dict[str,Any]]:
    for t in _threads():
        if t["tid"] == tid:
            return t
    return None

def _current_thread() -> Optional[Dict[str,Any]]:
    tid = st.session_state.get("_current_tid")
    return _find_thread(tid) if tid else None

def _ensure_thread():
    if _current_thread():
        return
    pid = _pdf_id()
    name = st.session_state.get("pdf_name") or "문서"
    for t in _threads():
        if t.get("pdf_id") == pid and t.get("pdf_name") == name:
            st.session_state["_current_tid"] = t["tid"]
            return
    tid = f"{pid}-{int(time.time())}"
    t = {
        "tid": tid, "pdf_id": pid, "pdf_name": name,
        "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "messages": [], "pdf_bytes": st.session_state.get("pdf_bytes"),
        "chunks": {},
    }
    _threads().append(t)
    st.session_state["_current_tid"] = tid

def _append_to_thread(item: Dict[str,Any]):
    th = _current_thread()
    if th: th["messages"].append(item)

# ================== 공통 사이드바 ==================
def render_sidebar():
    st.sidebar.markdown("<div class='hp-brand'><span class='dot'></span>Hi-PolicyLens</div>", unsafe_allow_html=True)
    st.sidebar.caption("현대해상 내부 리서치 보조")

    if st.sidebar.button("🏠 홈으로 가기", use_container_width=True):
        st.session_state["route"] = "landing"; st.experimental_rerun()

    st.sidebar.markdown("---")
    st.sidebar.subheader("PDF 분석 기록")

    st.sidebar.markdown("<div class='hp-log-list'>", unsafe_allow_html=True)
    for t in reversed(_threads()):
        label = f"📄 {t['pdf_name']} · {t['ts']} · 질문 {len(t['messages'])}개"
        if st.sidebar.button(label, key=f"hist-{t['tid']}", use_container_width=True):
            st.session_state["_current_tid"] = t["tid"]
            st.session_state["pdf_name"] = t["pdf_name"]
            st.session_state["pdf_bytes"] = t.get("pdf_bytes")
            st.session_state["chunks"] = t.get("chunks", {})
            st.session_state["chat"] = t.get("messages", [])
            st.session_state["route"] = "analysis"
            st.experimental_rerun()
    st.sidebar.markdown("</div>", unsafe_allow_html=True)

    st.sidebar.markdown("---")
    st.sidebar.markdown("<div class='hp-guide'>", unsafe_allow_html=True)
    st.sidebar.subheader("사용자 가이드")
    st.sidebar.markdown(
        """
        - 사이드바 **기록**에서 이전 분석 PDF를 다시 불러올 수 있습니다.  
        - 오른쪽 **목차 패널**에서 빠른 태그/표/그림을 탐색하세요.  
        - 표/그림은 **원본 크게 보기**로 확대 가능합니다.
        """.strip()
    )
    st.sidebar.markdown("</div>", unsafe_allow_html=True)

# ================== 랜딩 ==================
def landing_page():
    st.markdown(f"<style>{get_css()}</style>", unsafe_allow_html=True)
    render_sidebar()

    # 랜딩: 챗 입력만 숨김(업로더는 유지), 스크롤 제거 + 중앙 정렬
    # 🔴 여기서 --header-gap(상단 고정 여백)을 적용
    st.markdown("""
    <style>
      [data-testid='stChatInput'] { display:none !important; }
      /* 랜딩 컨테이너를 '툴바+고정 여백'만큼 아래에서 시작 + 나머지 영역 중앙정렬 */
      .block-container:has(#hp-landing-sentinel){ padding-top: 0 !important; }
      div[data-testid='stVerticalBlock']:has(> #hp-landing-sentinel){
        height: calc(100vh - var(--top-offset) - var(--header-gap));
        margin-top: var(--header-gap);
        display: flex; flex-direction: column;
        align-items: center; justify-content: center;
      }
      html, body { overflow: hidden !important; }  /* 스크롤 제거 */

      /* 업로더/버튼 폭 정리 */
      div[data-testid='stFileUploaderDropzone']{ max-width: 720px; margin: 0 auto; }
      .stButton > button{ max-width: 720px; margin: 0 auto; display:block; }
    </style>
    """, unsafe_allow_html=True)

    # 센티넬: 이 아래의 요소들을 중앙 정렬 대상으로 묶어줌
    st.markdown("<div id='hp-landing-sentinel'></div>", unsafe_allow_html=True)

    # 중앙 콘텐츠
    st.markdown("<h1 style='text-align:center; font-weight:900;'>👋 Hi-PolicyLens</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#334155; font-weight:700;'>PDF에서 핵심 정보를 원문 발췌하고 표/그림/문단으로 보여주는 맞춤형 도우미</p>", unsafe_allow_html=True)

    upl = st.file_uploader("분석할 PDF를 업로드하세요", type=["pdf"], key="landing_upl")
    start = st.button("🔍 분석 시작", use_container_width=True)

    if start:
        if not upl:
            st.warning("먼저 PDF를 업로드해주세요."); st.stop()
        pdf_bytes = upl.read(); pdf_name = upl.name
        pdf_id = hashlib.sha1(pdf_bytes).hexdigest()[:12]
        tid = f"{pdf_id}-{int(time.time())}"
        _threads().append({
            "tid": tid, "pdf_id": pdf_id, "pdf_name": pdf_name,
            "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "messages": [], "pdf_bytes": pdf_bytes, "chunks": {},
        })
        st.session_state["_current_tid"] = tid
        st.session_state["pdf_bytes"] = pdf_bytes
        st.session_state["pdf_name"]  = pdf_name
        st.session_state["route"] = "loading"
        st.rerun()

# ================== 로딩 ==================
def loading_page():
    st.markdown(f"<style>{get_css()}</style>", unsafe_allow_html=True)
    render_sidebar()

    # 로딩: 랜딩과 동일하게 --header-gap 적용해서 간격 띄움 + 중앙 정렬 + 스크롤 없음
    st.markdown("""
    <style>
      [data-testid='stChatInput']{ display:none !important; }
      .block-container:has(#hp-loading-sentinel){ padding-top: 0 !important; }
      div[data-testid='stVerticalBlock']:has(> #hp-loading-sentinel){
        height: calc(100vh - var(--top-offset) - var(--header-gap));
        margin-top: var(--header-gap);
        display:flex; align-items:center; justify-content:center;
      }
      html, body { overflow: hidden !important; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<div id='hp-loading-sentinel'></div>", unsafe_allow_html=True)
    st.markdown("<div class='hp-loading-card'>", unsafe_allow_html=True)
    st.markdown("<div class='title'>⏳ PDF에서 표/그림/텍스트를 추출하고 있습니다...</div>", unsafe_allow_html=True)

    pdf_bytes = st.session_state.get("pdf_bytes")
    if not pdf_bytes:
        st.warning("업로드된 PDF가 없습니다.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    ph = st.empty()
    def cb(info):
        ph.markdown(
            f"<div class='meter'>p.{info.get('page_label')} | 표={info.get('n_tables')} · 단어={info.get('n_words')} {'· TOC' if info.get('is_toc') else ''}</div>",
            unsafe_allow_html=True
        )

    with st.spinner("분석중..."):
        chunks = build_chunks(pdf_bytes, progress=cb)

    st.session_state["chunks"] = chunks
    st.session_state.setdefault("chat", [])
    st.session_state.setdefault("toc_tab", "그림 목차")
    st.session_state.setdefault("right_open", True)

    th = _current_thread()
    if th is not None:
        th["chunks"] = chunks
        th["pdf_bytes"] = pdf_bytes

    st.session_state["route"] = "analysis"
    st.rerun()

# ================== 분석 페이지 ==================
def analysis_page():
    st.markdown(f"<style>{get_css()}</style>", unsafe_allow_html=True)
    st.markdown("<style>html, body { overflow: auto !important; }</style>", unsafe_allow_html=True)  # 스크롤 복원

    render_sidebar()

    pdf_bytes = st.session_state.get("pdf_bytes")
    pdf_name  = st.session_state.get("pdf_name") or "분석 문서"
    chunks    = st.session_state.get("chunks") or {}

    st.session_state.setdefault("toc_tab", "그림 목차")
    st.session_state.setdefault("right_open", True)
    st.session_state.setdefault("chat", [])

    main_col, right_col = st.columns([1, 1], gap="large")

    with main_col:
        st.markdown("<div class='hp-main-sentinel'></div>", unsafe_allow_html=True)
        _render_header(pdf_name, chunks)
        _render_chat_panel(pdf_bytes, chunks)

        ask = st.chat_input("무엇이든 물어보세요")
        if ask:
            item = _make_item_from_free_query(ask, chunks)
            st.session_state["chat"].append(item)
            _ensure_thread(); _append_to_thread(item)
            st.rerun()

    with right_col:
        st.markdown("<div class='hp-right-sentinel'></div>", unsafe_allow_html=True)
        st.markdown("<div class='hp-right-wrap'>", unsafe_allow_html=True)

        if st.button(("📑 목차 패널 접기" if st.session_state["right_open"] else "📑 목차 패널 열기"),
                     use_container_width=True, key="toggle-right"):
            st.session_state["right_open"] = not st.session_state["right_open"]
            st.experimental_rerun()

        if st.session_state["right_open"]:
            tab = st.radio("보기", ["빠른 태그", "표 목차", "그림 목차"],
                           index=["빠른 태그","표 목차","그림 목차"].index(st.session_state["toc_tab"]),
                           horizontal=True, label_visibility="collapsed")
            st.session_state["toc_tab"] = tab

            q = ""
            if tab == "표 목차":
                q = st.text_input("표 검색", key="toc_q_tab", placeholder="예) 가구, 가격, 2023 ...",
                                  label_visibility="collapsed")
            elif tab == "그림 목차":
                q = st.text_input("그림 검색", key="toc_q_fig", placeholder="예) 추이, 비교, 2023 ...",
                                  label_visibility="collapsed")
            else:
                st.caption("추천 질문(문장형)을 클릭하면 바로 질문됩니다.")

            st.markdown("<div class='hp-right-list'>", unsafe_allow_html=True)
            if tab == "빠른 태그":
                _right_quick_tags(chunks)
            elif tab == "표 목차":
                _right_table_list(chunks, q)
            else:
                _right_figure_list(chunks, q)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.caption("오른쪽 목차 패널이 접혀 있습니다.")
        st.markdown("</div>", unsafe_allow_html=True)

# --------- 헤더 ----------
def _render_header(pdf_name: str, chunks: Dict[str,Any]):
    n_t = len(chunks.get("tables", []))
    n_f = len(chunks.get("figures", []))
    n_x = len(chunks.get("texts", []))
    try: w_total = sum(len((p.get("text") or "").split()) for p in chunks.get("texts", []))
    except Exception: w_total = 0
    w_k = f"{w_total:,}"

    st.markdown(
        f"""
        <div class="hp-header">
          <div class="title">📄 {pdf_name}</div>
          <div class="summary">분석 완료 · 단어수 {w_k} · 텍스트 {n_x} · 표 {n_t} · 그림 {n_f}</div>
        </div>
        <div class="hp-top-spacer"></div>
        """, unsafe_allow_html=True
    )

# --------- 오른쪽 패널 콘텐츠 / 채팅 렌더 함수들(기존 그대로) ----------
def _right_quick_tags(chunks: Dict[str,Any], k:int=18):
    pages = [{"text": p.get("text","")} for p in chunks.get("texts", [])]
    tags = generate_query_tags(pages, k=k) or []
    for i, t in enumerate(tags):
        label = "#" + re.sub(r"\s+", "", t.split()[0])[:12]
        if st.button(label, key=f"rqt-{i}", use_container_width=True):
            ctx = _find_relevant_context(chunks, t)
            item = {"q": t, "kind":"qa"}
            if ctx: item.update({"context":ctx["context"], "context_page":ctx["page"]})
            st.session_state["chat"].append(item)
            _ensure_thread(); _append_to_thread(item)
            st.experimental_rerun()

def _right_table_list(chunks: Dict[str,Any], q: str):
    tabs = chunks.get("toc", {}).get("tables", [])
    for i, t in enumerate(tabs):
        txt = f"<표 {t['label']}> {t['title']}"
        if q and (q not in txt): continue
        if st.button(txt, key=f"rtab-{i}-{t['label']}", use_container_width=True):
            item = {"q": txt, "kind":"table", "label": t["label"]}
            st.session_state["chat"].append(item); _ensure_thread(); _append_to_thread(item); st.experimental_rerun()

def _right_figure_list(chunks: Dict[str,Any], q: str):
    figs = chunks.get("toc", {}).get("figures", [])
    for i, f in enumerate(figs):
        txt = f"[그림 {f['label']}] {f['title']}"
        if q and (q not in txt): continue
        if st.button(txt, key=f"rfig-{i}-{f['label']}", use_container_width=True):
            item = {"q": txt, "kind":"figure", "label": f["label"]}
            st.session_state["chat"].append(item); _ensure_thread(); _append_to_thread(item); st.experimental_rerun()

_IMAGE_MAX = 980
def _render_chat_panel(pdf_bytes: bytes, chunks: Dict[str,Any]):
    for item in st.session_state["chat"]:
        st.markdown("<div class='hp-turn'>", unsafe_allow_html=True)
        st.markdown(f"<div class='hp-msg me'><div class='bubble'>🙋 { (item.get('q') or '').strip() }</div></div>", unsafe_allow_html=True)
        kind = item.get("kind")
        if kind == "table":
            t = find_table_by_label(chunks, item.get("label"))
            if not t:
                st.markdown("<div class='hp-msg'><div class='bubble'>해당 표를 찾지 못했어요.</div></div>", unsafe_allow_html=True)
            else:
                _render_table_item(t, pdf_bytes)
        elif kind == "figure":
            f = find_figure_by_label(chunks, item.get("label"))
            if not f:
                st.markdown("<div class='hp-msg'><div class='bubble'>해당 그림을 찾지 못했어요.</div></div>", unsafe_allow_html=True)
            else:
                _render_figure_item(f, pdf_bytes)
        elif kind == "qa":
            ctx = item.get("context", ""); page = item.get("context_page")
            with st.spinner("근거 문단으로 답변 생성중..."):
                ans = answer_with_context(item.get("q",""), ctx)
            st.markdown(
                f"<div class='hp-msg'><div class='bubble'>{ans}</div>" +
                (f"<div class='sub'>근거: p.{page}</div>" if page else "") + "</div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown("<div class='hp-msg'><div class='bubble'>오른쪽 '목차 패널'이나 빠른 태그를 사용해 질문해보세요.</div></div>", unsafe_allow_html=True)

def _render_table_item(t: Dict[str,Any], pdf_bytes: bytes):
    title = (t.get("title") or t.get("caption") or "").strip(); label = t.get("label") or "?"
    st.markdown(f"<div class='hp-msg'><div class='bubble'>'&lt;표 {label}&gt; {title}' 표를 찾았습니다. 아래 이미지를 참고하세요.</div></div>", unsafe_allow_html=True)
    if t.get("bbox") is not None:
        img = crop_table_image(pdf_bytes, t["page"]-1, t["bbox"], dpi=220); st.image(img, width=_IMAGE_MAX)
    st.markdown(f"<div class='hp-msg'><div class='sub'>원문 근거: p.{t['page']}</div></div>", unsafe_allow_html=True)

def _render_figure_item(f: Dict[str,Any], pdf_bytes: bytes):
    title = (f.get("title") or f.get("caption") or "").strip(); label = f.get("label") or "?"
    st.markdown(f"<div class='hp-msg'><div class='bubble'>'[그림 {label}] {title}' 그림을 찾았습니다. 아래 이미지를 참고하세요.</div></div>", unsafe_allow_html=True)
    if f.get("bbox") is not None:
        img = crop_figure_image(pdf_bytes, f["page"]-1, f["bbox"], dpi=220); st.image(img, width=_IMAGE_MAX)
    st.markdown(f"<div class='hp-msg'><div class='sub'>원문 근거: p.{f['page']}</div></div>", unsafe_allow_html=True)

def _make_item_from_free_query(q: str, chunks: Dict[str,Any]) -> Dict[str,Any]:
    tab, fig = _parse_labels(q)
    if tab:  return {"q": q, "kind":"table", "label": tab}
    if fig:  return {"q": q, "kind":"figure", "label": fig}
    ctx = _find_relevant_context(chunks, q)
    if ctx:  return {"q": q, "kind":"qa", "context": ctx["context"], "context_page": ctx["page"]}
    return {"q": q, "kind":"none"}

def _parse_labels(q: str) -> Tuple[Optional[str], Optional[str]]:
    m_tab = re.search(r"[<\\[]?\\s*표\\s*([0-9]+[-–][0-9]+)\\s*[>\\]]?", q)
    m_fig = re.search(r"[<\\[]?\\s*그림\\s*([0-9]+[-–][0-9]+)\\s*[>\\]]?", q)
    return (m_tab.group(1).replace("–","-") if m_tab else None,
            m_fig.group(1).replace("–","-") if m_fig else None)

def _find_relevant_context(chunks: Dict[str,Any], q: str) -> Optional[Dict[str,Any]]:
    texts = chunks.get("texts", []); best, best_s, best_page = "", 0.0, None
    ql = (q or "").lower()
    for t in texts:
        for para in re.split(r"\n{2,}", t.get("text") or ""):
            s = _score((para or "").lower(), ql)
            if s > best_s: best_s, best, best_page = s, para, t["page"]
    if best_page:
        ctx = " ".join([ln.strip() for ln in best.splitlines() if ln.strip()][:3])
        return {"context": ctx[:1200], "page": best_page}
    return None

def _score(text: str, ql: str) -> float:
    score = 0.0
    for w in re.findall(r"[가-힣a-z0-9]+", ql):
        if len(w) >= 2 and w in text: score += 1.0
    return score
