# ui_pages.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import re
from typing import Dict, Any, Optional, List, Tuple

import streamlit as st
from styles import get_css
from extract import (
    build_chunks, find_table_by_label, find_figure_by_label,
    crop_table_image, crop_figure_image,
)

# ---------------- 공통 사이드바 ----------------
def render_sidebar():
    st.sidebar.title("HOME 버튼")
    if st.sidebar.button("🏠 홈으로"):
        st.session_state.clear(); st.session_state["route"] = "landing"; st.rerun()
    st.sidebar.markdown("---")
    st.sidebar.subheader("대화 내용 기록")
    st.sidebar.caption("추후 DB로 연결하여 PDF별 대화 기록 보기가 가능합니다.")
    st.sidebar.markdown("---")
    st.sidebar.subheader("사용자 가이드")
    st.sidebar.markdown(
        "- **표**는 되도록 데이터프레임, 애매하면 **원본 이미지**로 보여줍니다.\n"
        "- **그림/그래프**는 원본 이미지를 그대로 보여줍니다.\n"
        "- 숫자 질문은 표의 구조화된 값만 사용해 답합니다."
    )

# ---------------- 랜딩 ----------------
def landing_page():
    st.markdown(f"<style>{get_css()}</style>", unsafe_allow_html=True)
    render_sidebar()
    st.markdown("## 👋 Hi-PolicyLens")
    st.markdown("**PDF에서 핵심 정보를 원문 발췌하고 표/그림으로 보여주는 맞춤형 도우미**")
    upl = st.file_uploader("분석할 PDF를 업로드하세요", type=["pdf"])
    if st.button("🔍 분석 시작", use_container_width=True):
        if not upl: st.warning("먼저 PDF를 업로드해주세요."); return
        st.session_state["pdf_bytes"] = upl.read()
        st.session_state["pdf_name"]  = upl.name
        st.session_state["route"] = "loading"; st.rerun()

# ---------------- 로딩 ----------------
def loading_page():
    st.markdown(f"<style>{get_css()}</style>", unsafe_allow_html=True)
    render_sidebar()
    st.markdown("### ⏳ Hi-PolicyLens가 PDF를 분석중입니다...")

    pdf_bytes = st.session_state.get("pdf_bytes")
    if not pdf_bytes: st.warning("업로드된 PDF가 없습니다."); return
    ph = st.empty()
    def cb(info):
        ph.markdown(f"**p.{info.get('page_label')}** | 표={info.get('n_tables')} 단어={info.get('n_words')} "
                    f"{'TOC' if info.get('is_toc') else ''}  \n"
                    f"· 표 미리보기: {(info.get('table_sample') or '').replace(chr(10),' ')[:120]}...")
    with st.spinner("PDF에서 표/그림/텍스트를 추출하고 있습니다..."):
        chunks = build_chunks(pdf_bytes, progress=cb)
    st.session_state["chunks"] = chunks
    st.session_state.setdefault("toc_open", True)
    st.session_state.setdefault("chat", [])
    st.session_state["route"] = "analysis"; st.rerun()

# ---------------- 분석 ----------------
def analysis_page():
    st.markdown(f"<style>{get_css()}</style>", unsafe_allow_html=True)
    # TOC 패널 내부 스크롤/칩 스타일
    st.markdown("""
    <style>
    .hp-toc {background:#fff;border:1px solid var(--secondary-bg);border-radius:8px;padding:8px;}
    .hp-toc h4{margin:6px 0 10px 2px;}
    #hp-toc-scroll{max-height:420px;overflow-y:auto;padding-right:6px;}
    .hp-chip{display:inline-block;padding:6px 10px;margin:4px;border:1px solid #ddd;border-radius:999px;
             background:#f8f9fb;cursor:pointer;font-size:0.92rem;}
    .hp-chip:hover{background:#eef2ff;border-color:#c7d2fe;}
    </style>""", unsafe_allow_html=True)

    render_sidebar()
    chunks = st.session_state.get("chunks"); pdf = st.session_state.get("pdf_bytes"); name = st.session_state.get("pdf_name")
    if not chunks or not pdf: st.warning("전처리 결과가 없습니다."); return
    st.session_state.setdefault("toc_open", True)
    st.session_state.setdefault("chat", [])
    st.session_state.setdefault("img_max_w", 900)

    # 상단 제목 + 목차 토글 버튼
    c1, c2 = st.columns([0.18, 0.82])
    with c1:
        if st.button(("◀ 목차 닫기" if st.session_state["toc_open"] else "▶ 목차 열기"), key="toggle_toc_btn"):
            st.session_state["toc_open"] = not st.session_state["toc_open"]; st.rerun()
    with c2:
        st.markdown(f"### 📄 {name}")
        st.caption(f"분석 완료: 표 {len(chunks.get('tables',[]))}개, 그림 {len(chunks.get('figures',[]))}개, 텍스트 {len(chunks.get('texts',[]))}개")

    # 레이아웃: 목차 열림이면 2컬럼
    if st.session_state["toc_open"]:
        toc_col, main_col = st.columns([0.95, 3], gap="large")
        with toc_col:  _render_toc_panel(chunks)
        with main_col: _render_chat_panel(pdf, chunks)
    else:
        _render_chat_panel(pdf, chunks)

    # --- 하단 고정 챗 입력 (NotebookLM 스타일) ---
    ask = st.chat_input("무엇이든 물어보세요")
    if ask:
        item = _make_chat_item_from_query(ask, chunks)
        st.session_state["chat"].append(item)
        st.rerun()

# ------------- TOC 패널(탭) -------------
DEFAULT_QUICK_TAGS = ["#연료비", "#에너지", "#가격", "#가구원", "#전력요금", "#도시가스", "#원/kWh", "#원/MJ", "#소득", "#지출"]

def _render_toc_panel(chunks: Dict[str, Any]):
    st.markdown('<div class="hp-toc">', unsafe_allow_html=True)
    st.markdown("#### 📑 목차(표/그림) 빠른 이동")

    tab1, tab2, tab3 = st.tabs(["빠른 검색", "표 목차", "그림 목차"])

    with tab1:
        st.caption("원클릭 빠른 검색")
        cols = st.columns(2)
        with cols[0]:
            for i, t in enumerate(DEFAULT_QUICK_TAGS[:len(DEFAULT_QUICK_TAGS)//2]):
                if st.button(t, key=f"qtag-{i}", use_container_width=True):
                    st.session_state["chat"].append(_make_chat_item_from_query(t.replace("#",""), chunks)); st.rerun()
        with cols[1]:
            for i, t in enumerate(DEFAULT_QUICK_TAGS[len(DEFAULT_QUICK_TAGS)//2:], start=100):
                if st.button(t, key=f"qtag-{i}", use_container_width=True):
                    st.session_state["chat"].append(_make_chat_item_from_query(t.replace("#",""), chunks)); st.rerun()

    with tab2:
        q = st.text_input("표 목차 검색", key="toc_q_tables", placeholder="예) 가구, 가격, 2023 ...")
        st.markdown('<div id="hp-toc-scroll">', unsafe_allow_html=True)
        for i, t in enumerate(chunks.get("toc",{}).get("tables", [])):
            txt = f"<표 {t['label']}> {t['title']}"
            if q and q not in txt: continue
            if st.button(txt, key=f"toc-tab-{i}-{t['label']}", use_container_width=True):
                st.session_state["chat"].append({"q": txt, "kind":"table", "label": t["label"]}); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with tab3:
        q = st.text_input("그림 목차 검색", key="toc_q_figs", placeholder="예) 추이, 비교, 2023 ...")
        st.markdown('<div id="hp-toc-scroll">', unsafe_allow_html=True)
        for i, f in enumerate(chunks.get("toc",{}).get("figures", [])):
            txt = f"[그림 {f['label']}] {f['title']}"
            if q and q not in txt: continue
            if st.button(txt, key=f"toc-fig-{i}-{f['label']}", use_container_width=True):
                st.session_state["chat"].append({"q": txt, "kind":"figure", "label": f["label"]}); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

# ------------- 채팅(누적) -------------
def _render_chat_panel(pdf_bytes: bytes, chunks: Dict[str, Any]):
    # 이전 히스토리 렌더
    for i, item in enumerate(st.session_state["chat"]):
        _render_chat_item(item, pdf_bytes, chunks, idx=i)

def _render_chat_item(item: Dict[str, Any], pdf_bytes: bytes, chunks: Dict[str, Any], idx: int = 0):
    st.markdown(f"#### 🙋 질문: {item.get('q','')}")
    kind = item.get("kind")
    if kind == "table":
        t = item.get("t") or (find_table_by_label(chunks, item.get("label")) if item.get("label") else None)
        if not t: st.info("해당 표를 찾지 못했어요."); return
        _render_table_item(t, pdf_bytes, chunks)
    elif kind == "figure":
        f = find_figure_by_label(chunks, item.get("label")) if item.get("label") else None
        if not f: st.info("해당 그림을 찾지 못했어요."); return
        _render_figure_item(f, pdf_bytes)
    else:
        st.info("딱 맞는 항목을 못 찾았어요. `<표 2-6>` 또는 `[그림 3-1]` 처럼 라벨로 물어보세요.")

def _render_table_item(t: Dict[str, Any], pdf_bytes: bytes, chunks: Dict[str, Any]):
    max_w = int(st.session_state.get("img_max_w", 900))
    try:
        if t.get("bbox") is not None:
            img = crop_table_image(pdf_bytes, t["page"] - 1, t["bbox"], dpi=220)
            st.image(img, caption=f"<표 {t.get('label') or '?'}> | p.{t['page']} | {t.get('caption') or ''}", width=max_w)
            with st.expander("원본 크게 보기", expanded=False):
                st.image(img, use_column_width=True)
        st.caption(f"원문 근거: p.{t['page']}  |  캡션: {(t.get('caption') or '').strip()[:100]}")
    except Exception as e:
        st.warning(f"이미지 크롭 중 오류: {e}")

def _render_figure_item(f: Dict[str, Any], pdf_bytes: bytes):
    max_w = int(st.session_state.get("img_max_w", 900))
    try:
        if f.get("bbox") is not None:
            img = crop_figure_image(pdf_bytes, f["page"] - 1, f["bbox"], dpi=220)
            st.image(img, caption=f"[그림 {f.get('label') or '?'}] | p.{f['page']} | {f.get('caption') or ''}", width=max_w)
            with st.expander("원본 크게 보기", expanded=False):
                st.image(img, use_column_width=True)
        st.caption(f"원문 근거: p.{f['page']}  |  캡션: {(f.get('caption') or '').strip()[:100]}")
    except Exception as e:
        st.warning(f"그림 크롭 중 오류: {e}")

# ---------- 질의 해석 ----------
def _make_chat_item_from_query(q: str, chunks: Dict[str, Any]) -> Dict[str, Any]:
    tab, fig = _parse_labels(q)
    if tab: return {"q": q, "kind": "table", "label": tab}
    if fig: return {"q": q, "kind": "figure", "label": fig}
    # 기본은 표 우선 검색
    cands = _search_tables(chunks, q)
    if cands: return {"q": q, "kind": "table", "t": cands[0]}
    return {"q": q, "kind": "none"}

def _parse_labels(q: str):
    q = q.strip()
    m_tab = re.search(r"[<\[]?\s*표\s*([0-9]+[-–][0-9]+)\s*[>\]]?", q)
    m_fig = re.search(r"[<\[]?\s*그림\s*([0-9]+[-–][0-9]+)\s*[>\]]?", q)
    return (m_tab.group(1).replace("–","-") if m_tab else None,
            m_fig.group(1).replace("–","-") if m_fig else None)

def _search_tables(chunks: Dict[str, Any], q: str) -> List[Dict[str, Any]]:
    scored = []
    for t in chunks.get("tables", []):
        text = (t.get("caption") or "") + " " + (t.get("title") or "")
        s = _score(text, q)
        if s > 0: scored.append((s, t))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [t for _, t in scored[:3]]

def _score(text: str, q: str) -> float:
    t = (text or "").lower(); q = (q or "").lower()
    score = 0.0
    for w in re.findall(r"[가-힣a-z0-9]+", q):
        if len(w) >= 2 and w in t: score += 1.0
    for y in set(re.findall(r"20\d{2}", q)):
        if y in t: score += 1.2
    return score
