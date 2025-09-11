# pages/compare-page.py
# ------------------------------------------------------------
# 좌: 질문 → /search로 컨텍스트 조회 (연결 없으면 '목업 모드' 결과)
# 우: 탭(원문/대화기록 자리)
# 실제 LLM 호출은 키/모델 스펙 확정 후 추가
# ------------------------------------------------------------
import streamlit as st
from retriever_client import search_chunks
from prompts import SYSTEM_PROMPT, build_user_prompt

st.title("📖 PDF 비교/질의")

left, right = st.columns([1, 1], gap="large")

with left:
    st.subheader("🤖 LLM 질의 (컨텍스트 검색 포함)")
    q = st.text_input("PDF 내용에 대해 질문해 보세요", placeholder="예) 11차 계획의 석탄 비중은?")
    run = st.button("질문하기", use_container_width=True)

    if run and q.strip():
        # 1) 컨텍스트 검색: 팀 /search API 또는 목업 응답
        contexts = search_chunks(q)

        # 2) LLM에 보낼 사용자 프롬프트 구성(미리보기)
        user_prompt = build_user_prompt(q, contexts)

        st.caption("🔧 SYSTEM PROMPT")
        st.code(SYSTEM_PROMPT)

        st.caption("📦 USER PROMPT(컨텍스트 포함)")
        st.code(user_prompt)

        st.caption("🔎 검색 컨텍스트 미리보기")
        st.json(contexts)

with right:
    tab1, tab2 = st.tabs(["📑 PDF 원문(미리보기 자리)", "💬 대화기록(데모)"])
    with tab1:
        st.info("실서비스에서는 PDF.js/iframe으로 원문 뷰어를 임베드하세요.")
    with tab2:
        st.write("대화기록 저장/표시는 추후 LLM 연결 시 구현 예정.")
