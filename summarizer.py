# =========================
# summarizer.py
# (계층 요약: 메타/목차 제외 → 내용 페이지 선별 → 페이지요약 → 최종 문서 요약)
# =========================
from __future__ import annotations
from typing import List, Callable, Dict, Any, Optional
import re
from llm import llm_chat, SUMMARIZER_DEFAULT_SYSTEM

# ───────────────────────────────────────────────
# 휴리스틱: 메타/목차 페이지 제외 + 내용 스코어링
# ───────────────────────────────────────────────
_KEYWORDS = [
    "정책", "변화", "동향", "추이", "증가", "감소", "비중", "점유율", "수요", "공급",
    "가격", "시장", "투자", "설비", "전망", "과제", "시사점", "결론", "성과", "통계",
    "배출", "온실가스", "재생에너지", "전력", "효율", "보조금", "세제", "규제", "요금"
]

def _is_probably_meta_or_toc(text: str) -> bool:
    """
    목차/표지/발간정보/저자/초록/요약/서문/감사의글 등 '메타' 페이지를 제외.
    """
    head = (text or "")[:1600]
    if re.search(r"(목\s*차|표\s*목차|그림\s*목차|표지|발간|저자|연구진|초록|요약|요지|서문|감사의글)", head):
        return True
    if len(re.findall(r"[A-Za-z]{4,}", head)) > 60 and len(head) < 1000:
        return True
    return False

def _content_score(text: str) -> float:
    """간단 점수: 키워드 매칭 + 숫자(%, 연도·금액 등) 개수."""
    t = text or ""
    kw = sum(1 for k in _KEYWORDS if k in t)
    nums = len(re.findall(r"\d{4}년|\d+(?:\.\d+)?\s?%|\d{1,3}(?:,\d{3})+|원/kWh|원/MJ|toe|MWh|kWh|MJ", t))
    return kw * 1.0 + nums * 0.3

# ───────────────────────────────────────────────
# 프롬프트 정의
# ───────────────────────────────────────────────
_PAGE_SUMMARY_PROMPT = """
다음 '페이지 본문'을 2~3문장으로 요약하되, 반드시 아래 형식을 지키세요.

[형식]
- 불릿 2~3개
- 각 불릿은 1문장, 25자~60자
- '정책 변화·시장 동향·핵심 주제'만 포함
- 메타데이터(제목/저자/발간정보/초록/서문) 금지
- 문서 밖 추측 금지

[페이지 본문]
{page_text}
""".strip()

_FINAL_SUMMARY_PROMPT = """
아래는 문서의 '페이지별 요약'입니다. 이를 통합해서 간단한 핵심 요약을 작성하세요.

[출력 형식 (Markdown)]
#### 문서 요약
1. 이 문서는 [무슨 주제/범위]에 대한 보고서입니다.
2. (p.xx) 섹션별 중요 요약 1
3. (p.yy) 섹션별 중요 요약 2
4. (p.zz) 섹션별 중요 요약 3

[규칙]
- 번호 매기기 형식(1., 2., 3., …) 사용
- 각 항목은 1문장, 25~60자
- 2~4번 항목에는 반드시 (p.번호) 근거 포함
- 세부 수치/정책 시사점은 포함하지 않음
- 메타데이터(제목/저자/발간정보/초록/서문) 제외
- 문서 밖 추측 금지

[페이지별 요약]
{page_summaries}
""".strip()

# ───────────────────────────────────────────────
# 계층 요약 함수
# ───────────────────────────────────────────────
def summarize_from_chunks(
    chunks: Dict[str, Any],
    max_pages: int = 20,
    per_page_limit: int = 2800,
    progress_cb: Optional[Callable[[str, float], None]] = None
) -> str:
    """
    계층 요약 파이프라인:
      ① 메타/목차 페이지 제외
      ② 내용 페이지 스코어링 후 상위 N개 선별
      ③ 페이지 단위 요약(불릿)
      ④ 최종 통합 요약(문서 요약)
    """
    pages = chunks.get("texts", []) or []
    if not pages:
        return "본문 발췌가 없습니다."

    # 1) 메타 제외 + 스코어링
    cands = []
    for it in pages:
        pno = it.get("page")
        txt = (it.get("text") or "").strip()
        if not txt:
            continue
        if _is_probably_meta_or_toc(txt):
            continue
        cands.append((pno, txt, _content_score(txt)))

    if not cands:
        cands = [(it.get("page"), (it.get("text") or ""), 0.0) for it in pages[:3]]

    # 2) 상위 페이지 선별
    cands.sort(key=lambda x: x[2], reverse=True)
    selected = cands[:max_pages]

    # 3) 페이지 요약
    page_sums: List[str] = []
    total = len(selected)
    for i, (pno, txt, _) in enumerate(selected, 1):
        if progress_cb:
            progress_cb(f"페이지 요약 중… (p.{pno})", i / (total + 1))
        excerpt = txt[:per_page_limit]
        up = _PAGE_SUMMARY_PROMPT.format(page_text=excerpt)
        s = llm_chat(SUMMARIZER_DEFAULT_SYSTEM, up)
        page_sums.append(f"(p.{pno}) {s}")

    # 4) 최종 요약
    if progress_cb:
        progress_cb("최종 요약 통합 중…", total / (total + 1))
    joined = "\n\n".join(page_sums)
    final = llm_chat(
        SUMMARIZER_DEFAULT_SYSTEM,
        _FINAL_SUMMARY_PROMPT.format(page_summaries=joined[:12000])
    )
    if progress_cb:
        progress_cb("완료", 1.0)
    return final
