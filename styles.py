# styles.py
# -*- coding: utf-8 -*-
"""
전역 스타일: Pretendard 폰트 + 포인트 컬러 테마
- Primary(남색): #0f2e69
- Accent(주황):  #dc8d32
"""

PRIMARY = "#0f2e69"  # 남색
ACCENT  = "#dc8d32"  # 주황
BG_LITE = "#f6f8fb"
BORDER  = "#e6e8ee"
TEXT    = "#22304b"

def get_css() -> str:
    return f"""
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

    :root {{
      --primary: {PRIMARY};
      --accent: {ACCENT};
      --bg-lite: {BG_LITE};
      --border: {BORDER};
      --text: {TEXT};
    }}

    html, body, [class*="css"] {{
      font-family: "Pretendard", -apple-system, BlinkMacSystemFont, "Segoe UI",
                   Roboto, "Helvetica Neue", Arial, "Apple SD Gothic Neo",
                   "Noto Sans KR", "Malgun Gothic", "Apple Color Emoji",
                   "Segoe UI Emoji", "Segoe UI Symbol" !important;
      color: var(--text);
    }}

    /* 상단 헤더 카드 */
    .hp-header {{
      padding: 12px 16px;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: white;
      display:flex; justify-content:space-between; align-items:center;
      margin-bottom: 12px;
    }}
    .hp-header .title {{
      font-weight: 800; font-size: 18px; color: var(--primary);
    }}
    .hp-header .summary {{
      font-size: 12px; color: #5b6b88;
    }}

    /* 브랜드(사이드바) */
    .hp-brand {{
      font-weight: 800; font-size: 18px; color: var(--primary);
      display:flex; align-items:center; gap:8px;
      margin: 8px 0 12px 0;
    }}
    .hp-brand .dot {{
      width:10px; height:10px; border-radius:50%;
      background: var(--accent); display:inline-block;
    }}

    /* 섹션 카드 */
    .hp-card {{
      border: 1px solid var(--border);
      background: white;
      border-radius: 12px;
      padding: 14px;
    }}

    /* 추천 질문 카드(슬라이더 느낌) */
    .q-card {{
      border: 1px dashed var(--border);
      background: #fff;
      border-radius: 12px;
      padding: 12px 14px;
      font-weight: 600;
      cursor: pointer;
      transition: all .15s ease;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .q-card:hover {{ border-color: var(--accent); color: var(--primary); }}

    /* 탭 상단 색상 정리 */
    .stTabs [data-baseweb="tab-list"] {{
      gap: 6px;
      border-bottom: 1px solid var(--border);
    }}
    .stTabs [data-baseweb="tab"] {{
      padding: 8px 12px;
      font-weight: 700;
      color: var(--primary);
      border-radius: 8px 8px 0 0;
      background: #eef3fb;
    }}
    .stTabs [aria-selected="true"] {{
      background: white !important;
      border: 1px solid var(--border);
      border-bottom-color: white !important;
    }}

    /* 버튼 색상 통일 */
    .stButton>button {{
      border: 1px solid var(--border);
      background: white;
      color: var(--primary);
      font-weight: 700;
      border-radius: 10px;
    }}
    .stButton>button:hover {{
      border-color: var(--accent);
      color: var(--accent);
      background: #fff9f1;
    }}

    /* 작은 캡션 */
    .hp-cap {{
      font-size: 12px;
      color: #7c8aa5;
    }}

    /* 목차 행 스타일 */
    .toc-item {{
      width: 100%;
      text-align: left;
      padding: 8px 10px;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: #fff;
      margin-bottom: 8px;
      transition: all .12s;
      font-weight: 600;
      color: var(--primary);
    }}
    .toc-item:hover {{ border-color: var(--accent); color: var(--accent); }}

    /* 미세 여백 */
    .gap8 {{ height: 8px; }}
    .gap12 {{ height: 12px; }}
    .gap16 {{ height: 16px; }}
    """
