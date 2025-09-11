# pages/promptying-page.py
# ------------------------------------------------------------
# Potens(포텐스) API 등으로 직접 프롬프트 실험하는 페이지의 폼.
# 지금은 '요청 바디 예시'만 출력. 실제 스펙 확정되면 requests.post 추가.
# ------------------------------------------------------------
import streamlit as st

st.title("📝 프롬프팅 실험실")

system = st.text_area("시스템 프롬프트", height=160, value=(
    "너는 매우 신중한 분석가다. 원문 인용을 반드시 포함하고 추측은 하지 마라."
))
user = st.text_area("사용자 프롬프트", height=160, value="여기에 질문/명령을 적으세요.")
run = st.button("실행(데모)", use_container_width=True)

if run:
    api_key = st.secrets.get("POTENS_API_KEY", "")
    if not api_key:
        st.warning("POTENS_API_KEY가 없습니다. Streamlit Secrets에 추가하세요.")
    # 실제 호출은 Potens 스펙 확정 후 작성
    demo_payload = {
        "model": "potens-pro",  # (예시)
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "temperature": 0.2
    }
    st.write("요청 바디(예시):")
    st.code(demo_payload, language="json")
    st.info("※ 실제 호출은 Potens API 스펙 확정 후 requests.post 추가 예정.")
