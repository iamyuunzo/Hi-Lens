# prompts.py
# ------------------------------------------------------------
# 시스템/유저 프롬프트 템플릿.
# "원문 인용 강제" 규칙과 JSON 출력 형식 정의.
# ------------------------------------------------------------

SYSTEM_PROMPT = """
너는 검색 보조자다. 아래 규칙을 반드시 지켜라.
1) 추측 금지. 알 수 없으면 '모른다'고 말한다.
2) 모든 답변에는 반드시 원문 인용(문장 단위)을 포함한다.
3) 인용 항목에는 다음 메타정보를 포함한다: doc_id, page_start, page_end, line_start, line_end.
4) 출력은 아래 JSON 스키마만 사용한다.
{
  "answer": "<요약/정답>",
  "citations": [
    {
      "doc_id": "string",
      "page_start": 0,
      "page_end": 0,
      "line_start": 0,
      "line_end": 0,
      "quote": "원문 그대로 문장"
    }
  ]
}
"""

def build_user_prompt(question: str, contexts: list[dict]) -> str:
    """검색 컨텍스트 + 질문을 하나의 사용자 프롬프트로 합친다."""
    lines = []
    for i, c in enumerate(contexts, 1):
        lines.append(
            f"[{i}] ({c.get('doc_id')} p{c.get('page_start')}-{c.get('page_end')} "
            f"l{c.get('line_start')}-{c.get('line_end')})\n{c.get('text')}\n"
        )
    ctx_block = "\n".join(lines) if lines else "(컨텍스트 없음)"

    return f"""
아래 CONTEXT만 사용해서 답하라(추측 금지).
[CONTEXT]
{ctx_block}

[QUESTION]
{question}
"""
