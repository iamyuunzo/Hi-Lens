# styles.py
# -*- coding: utf-8 -*-
"""
UI 공통 스타일 (기능 로직 변경 없음)

- 랜딩/로딩: 화면 중앙 배치, 스크롤 없음(상단 유령 박스 제거는 ui_pages에서 처리)
- 분석: (대화:목차=8:2) 고정폭, 우측 목차 회색 고정 패널, 중앙 헤더 sticky
"""
def get_css() -> str:
    return r"""
    :root{
        /* 스트림릿 상단 툴바(Deploy …) 높이 보정값 */
        --top-offset: 80px;
        /* 🔴 요청: 상단 헤더와 메인 카드 사이를 항상 띄우는 여백 */
        --header-gap: 50px;

        /* 분석 페이지 비율(8:2) */
        --rightbar-w: 280px;
        --main-w: calc(var(--rightbar-w) * 4);

        /* 팔레트 */
        --bg: #ffffff;
        --panel: #f5f7fb;
        --border: #e6e8ee;
        --muted: #667085;

        --green-bg: #ecfdf5;
        --green-bd: #bbf7d0;
        --green-tx: #065f46;

        --radius: 12px;
        --shadow: 0 1px 2px rgba(16,24,40,.06), 0 1px 1px rgba(16,24,40,.04);
    }

    /* 메인 컨테이너 기본 상단 패딩 (분석에선 유지, 랜딩/로딩에선 ui_pages에서 제거) */
    .block-container{ padding-top: 1.2rem !important; }

    /* ===================== 사이드바 공통 ===================== */
    section[data-testid="stSidebar"] .hp-brand{
        display:flex; align-items:center; gap:10px;
        font-weight: 900; font-size: 1.25rem; letter-spacing: .2px;
        padding: 8px 6px 2px 6px;
    }
    section[data-testid="stSidebar"] .hp-brand .dot{
        width:10px; height:10px; border-radius:50%; background:#6366f1; display:inline-block;
    }
    section[data-testid="stSidebar"] .hp-guide{ margin-top: auto; }

    section[data-testid="stSidebar"] .hp-log-list{ display:flex; flex-direction:column; gap:6px; }
    section[data-testid="stSidebar"] .hp-log-list .stButton > button{
        background:#fff !important; color:#0f172a !important;
        border:1px solid var(--border) !important; border-radius:10px !important;
        padding:8px 10px !important; font-weight:700 !important; font-size: 13px !important;
        box-shadow:none !important; text-align:left; white-space: normal !important;
    }
    section[data-testid="stSidebar"] .hp-log-list .stButton > button:hover{
        background:#eef2ff !important; border-color:#cfd6ea !important;
    }

    /* ===================== 로딩 카드(랜딩과 동일 레이아웃) ===================== */
    .hp-loading-card{
        width: 720px; max-width: 92vw;
        border:1px solid var(--border); border-radius:16px;
        background:#fff; box-shadow: var(--shadow);
        padding: 22px 20px; text-align:center;
    }
    .hp-loading-card .title{
        font-size: 1.35rem; font-weight:900; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
    }
    .hp-loading-card .meter{ color:#475569; font-weight:700; }

    /* ===================== 분석 페이지 ===================== */
    /* (A) 우 컬럼 폭 고정 → 8:2 비주얼 */
    div[data-testid="stColumn"]:has(> div div.hp-right-sentinel){
        flex: 0 0 var(--rightbar-w) !important;
        max-width: var(--rightbar-w) !important;
    }
    /* (B) 중앙 컬럼 폭 고정 */
    div[data-testid="stColumn"]:has(> div div.hp-main-sentinel){
        flex: 0 0 var(--main-w) !important;
        max-width: var(--main-w) !important;
    }

    /* 우 목차 패널: sticky + 내부 스크롤 + 회색 카드 */
    div[data-testid="stVerticalBlock"]:has(> .hp-right-sentinel){
        position: sticky;
        top: calc(var(--top-offset) + 8px);
        height: calc(100vh - var(--top-offset) - 16px);
        overflow: auto;
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 12px;
        box-shadow: var(--shadow);
        padding: 10px 10px 12px;
    }
    .hp-right-wrap .stButton > button{
        background:#fff !important; color:#0f172a !important;
        border:1px solid var(--border) !important; box-shadow: none !important;
        border-radius:10px !important; padding:7px 10px !important;
        font-weight:700 !important; font-size: 13px !important; text-align:left;
    }
    .hp-right-wrap .stButton > button:hover{
        background:#eef2ff !important; border-color:#cfd6ea !important;
    }
    .hp-right-wrap .stRadio [role="radiogroup"]{ gap:8px !important; }
    .hp-right-wrap .stRadio [role="radiogroup"] label{
        padding:4px 8px; border-radius:999px; border:1px solid transparent; font-size:13px;
    }
    .hp-right-wrap .stRadio [role="radiogroup"] label:hover{ background:#eef2ff; border-color:#d7def2; }
    .hp-right-wrap .stTextInput > div > div > input{ font-size:13px !important; padding:6px 10px !important; }
    .hp-right-list{ display:flex; flex-direction:column; gap:6px; }

    /* 중앙 헤더: sticky */
    .hp-header{
        position: sticky; top: var(--top-offset); z-index: 900;
        background: var(--bg); border-bottom: 1px solid var(--border);
        padding: 10px 0 8px;
    }
    .hp-header .title{
        font-size: 1.55rem; font-weight: 900; line-height: 1.25;
        margin: 0 0 8px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .hp-header .summary{
        background: var(--green-bg); color: var(--green-tx);
        border:1px solid var(--green-bd); border-radius: 10px;
        padding:8px 10px; display:flex; align-items:center; gap: 10px;
        box-shadow: var(--shadow); font-weight: 700; font-size: 0.95rem;
    }
    .hp-top-spacer{ height: 6px; }

    /* 대화 turn/bubble */
    .hp-turn{ margin: 16px 0 18px; padding-top: 8px; border-top:1px dashed var(--border); }
    .hp-msg .bubble{
        display:inline-block; padding:10px 12px; border-radius: var(--radius);
        border:1px solid #e5e7eb; background: #ffffff; box-shadow: var(--shadow);
    }
    .hp-msg.me{ text-align:right; }
    .hp-msg.me .bubble{ background: #e0f2fe; border-color:#bae6fd; }
    .hp-msg .sub{ color: var(--muted); font-size:.82rem; margin-top:4px; }

    /* 표/그림 이미지 정렬 깨짐 방지 */
    .stImage img{ display:block; max-width:100%; height:auto; margin: 8px auto; }
    """
