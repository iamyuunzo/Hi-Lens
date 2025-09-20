# llm.py
# -*- coding: utf-8 -*-
# LLM Switch + "표 설명 전용" 간단 보조
#
# ✅ 요약
#  - explain_tables(): 표 미리보기(markdown)만 근거로 짧은 bullet 설명 생성.
#  - LLM이 없거나 실패 시, 규칙 기반 설명으로 안전하게 대체.
#
# 환경변수(.env)
#  - OPENAI_API_KEY 또는 POTENSDAT_API_KEY(+POTENSDAT_BASE_URL)
#  - LLM_MODEL (기본 gpt-4o-mini)

import os
import re
from collections import Counter
from typing import Dict, List

openai_client = None
provider = "none"
DEFAULT_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

POTENSDAT_API_KEY = os.getenv("POTENSDAT_API_KEY")
POTENSDAT_BASE_URL = os.getenv("POTENSDAT_BASE_URL", "https://api.potensdat.ai/v1")
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY")

try:
    from openai import OpenAI
    if POTENSDAT_API_KEY:
        openai_client = OpenAI(api_key=POTENSDAT_API_KEY, base_url=POTENSDAT_BASE_URL)
        provider = "potensdat"
    elif OPENAI_API_KEY:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        provider = "openai"
except Exception:
    openai_client = None
    provider = "none"

def get_provider_name() -> str:
    return provider.upper() if provider != "none" else "OFF (요약만)"

EXPLAIN_TABLES_PROMPT = """
너는 '정책 PDF 표 분석 보조원'이다. 반드시 아래 규칙을 지켜라.

규칙
- 오직 '제공된 표 미리보기(마크다운)'와 '페이지 번호'만 근거로 삼아라.
- 표에 없는 수치/항목은 추정하거나 만들어내지 말라(환각 금지).
- 출력은 최대 5줄 bullet. 각 bullet은 '무슨 표인지'와 '핵심 변화/특징'을 짧게.
- 필요하면 bullet 끝에 (p.번호)로 근거 페이지를 표시.

출력 형식
- (핵심 요점 1)
- (핵심 요점 2)
- (핵심 요점 3)
- (필요시 추가)
""".strip()

def explain_tables(query: str, table_contexts: List[Dict]) -> str:
    ctx_lines = []
    for i, t in enumerate(table_contexts, 1):
        title = (t.get("title") or "").strip()
        head = f"[표{i}] p.{t['page_label']}" + (f" · {title}" if title else "")
        ctx_lines.append(head)
        ctx_lines.append((t.get("preview_md") or "")[:3000])
        ctx_lines.append("")
    ctx_txt = "\n".join(ctx_lines).strip()

    if openai_client:
        try:
            res = openai_client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": EXPLAIN_TABLES_PROMPT},
                    {"role": "user",   "content": f"사용자 질문: {query}\n\n표 미리보기:\n{ctx_txt}"}
                ],
                temperature=0.0,
            )
            out = (res.choices[0].message.content or "").strip()
            lines = [ln for ln in out.splitlines() if ln.strip()]
            if len(lines) > 8:
                lines = lines[:8]
            return "\n".join(lines)
        except Exception:
            pass

    # LLM이 없을 때의 규칙 기반 대체
    bullets = []
    for t in table_contexts[:3]:
        md = t.get("preview_md","")
        page = t.get("page_label","?")
        # 열 수 간단 추정
        cols = 0
        for line in md.splitlines():
            if line.startswith("|") and "---" not in line:
                cols = max(cols, line.count("|")-1)
        bullets.append(f"- (p.{page}) 관련 표 감지 · 대략 {cols}열 구성. 질문 키워드와 맞는 항목 확인.")
    return "\n".join(bullets)

def generate_query_tags(pages: List[Dict], k: int = 8) -> List[str]:
    """문서 내용으로부터 '질문형 태그' 자동 생성 (LLM 우선, 실패 시 빈도 기반)."""
    texts = [p.get("text", "") or "" for p in pages]
    joined = "\n\n".join(texts)
    if len(joined) > 8000:
        one_third = len(joined) // 3
        joined = joined[:2500] + "\n\n" + joined[one_third:one_third+2500] + "\n\n" + joined[-2500:]

    global openai_client, DEFAULT_MODEL
    if openai_client:
        try:
            prompt = (
                "아래 문서 내용을 보고, 사용자가 바로 누를 수 있는 '짧은 질문형 태그'를 한국어로 "
                f"{k}개 생성해줘.\n"
                "- 각 태그는 20~28자 짧은 문장, 표/지표/기간 비교를 요청하는 형태(예: '2019~2023년 연료비 추이 표로 보여줘')\n"
                "- 줄바꿈으로만 구분, 번호/불릿/마크다운 금지\n\n"
                f"[문서요약]\n{joined}\n"
            )
            res = openai_client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            raw = (res.choices[0].message.content or "").strip()
            tags = [re.sub(r"^[0-9\-\.\s]+", "", ln).strip() for ln in raw.splitlines() if ln.strip()]
            out, seen = [], set()
            for t in tags:
                t = re.sub(r"\s+", " ", t)[:28]
                if t and t not in seen:
                    seen.add(t); out.append(t)
                if len(out) >= k: break
            if out: return out
        except Exception:
            pass

    # 대체(LLM 없음) — 간단 빈도 기반
    base = " ".join(texts).lower()
    years = sorted(set(re.findall(r"20\d{2}", base)))[-3:]
    toks = re.findall(r"[가-힣A-Za-z]{2,}", base)
    commons = [w for w, _ in Counter(toks).most_common(40)]

    cands = []
    if years:
        cands.append(f"{'~'.join(years)} 연도별 지표 비교해줘")
    for w in commons:
        if len(cands) >= k*2: break
        if w in ("표","그림","이미지","참고문헌"):  # 무의미 토큰 제거
            continue
        cands.append(f"{w} 관련 지표를 표로 보여줘")

    out, seen = [], set()
    for c in cands:
        c = re.sub(r"\s+", " ", c).strip()
        if c and c not in seen:
            seen.add(c); out.append(c)
        if len(out) >= k: break
    return out or ["전체 요약을 표로 정리해줘"]
