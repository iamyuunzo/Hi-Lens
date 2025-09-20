# styles.py
# -*- coding: utf-8 -*-

def get_css() -> str:
    """
    메인 바디 안에 '목차 사이드패널'을 넣기 위한 CSS.
    - 오버레이/고정 포지션 사용 X. Streamlit columns 안에서만 동작.
    - 패널 헤더는 sticky, 패널 본문은 내부 스크롤.
    """
    return """
    :root{
      --hp-toc-top-offset: 62px;      /* sticky 시작 위치(상단 여백 보정) */
    }

    /* ===== 목차 패널(메인 컬럼 내부) ===== */
    .hp-toc-panel{
      border-right: 1px solid rgba(0,0,0,.08);
      padding-right: .5rem;
      height: 100%;
    }

    /* 패널 헤더: 항상 위에 붙음 */
    .hp-toc-header{
      position: sticky;
      top: var(--hp-toc-top-offset);
      background: #ffffff;
      z-index: 2;
      padding: .25rem 0 .5rem 0;
      border-bottom: 1px solid rgba(0,0,0,.06);
      margin-bottom: .5rem;
    }

    /* 패널 본문: 내부 스크롤(바깥 페이지는 스크롤 안 함) */
    /* viewport 높이에서 상단/하단 여백을 빼서 적당한 가시 높이 확보 */
    #hp-toc-scroll{
      max-height: calc(100vh - var(--hp-toc-top-offset) - 120px);
      overflow-y: auto;
      padding-right: .25rem;
    }

    /* 목차 버튼(한 줄짜리 아이템) */
    .hp-toc-item{
      width:100%; text-align:left;
      border:1px solid rgba(0,0,0,.12);
      background:#fff; border-radius:10px;
      padding:.45rem .6rem; margin:.28rem 0;
      font-size:.92rem; cursor:pointer;
    }
    .hp-toc-item:hover{ background:#f6f7f9; }

    /* 후보 칩 바 */
    .hp-cand-bar{ display:flex; flex-wrap:wrap; gap:.5rem; margin:.5rem 0 1rem 0; }
    .hp-chip{
      display:inline-block; padding:.35rem .6rem; border-radius:999px;
      border:1px solid rgba(0,0,0,.12); background:#fff; font-size:.85rem;
      cursor:pointer; user-select:none;
    }
    .hp-chip:hover{ background:#f3f4f6; }
    .hp-cap{ color:#6b7280; font-size:.8rem; margin-top:.25rem; }
    """
