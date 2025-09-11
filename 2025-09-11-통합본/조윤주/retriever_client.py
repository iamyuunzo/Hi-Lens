# retriever_client.py
# ------------------------------------------------------------
# 팀원이 만든 /search API 호출 래퍼.
# RETRIEVER_BASE_URL이 비어있으면 '목업 모드'로 더미 컨텍스트를 반환.
# ------------------------------------------------------------
import requests
import streamlit as st

def _get_conf():
    base_url = st.secrets.get("RETRIEVER_BASE_URL", "")  # ""면 목업
    api_key  = st.secrets.get("RETRIEVER_API_KEY", "")
    top_k    = int(st.secrets.get("TOP_K", 8))
    return base_url, api_key, top_k

def search_chunks(query: str, k: int | None = None):
    base_url, api_key, default_k = _get_conf()
    k = k or default_k

    # 1) 목업 모드: 실서버 없이도 전체 플로우 테스트 가능
    if not base_url:
        return [
            {
                "doc_id": "예시_문서.pdf",
                "page_start": 12,
                "page_end": 12,
                "line_start": 10,
                "line_end": 24,
                "text": "여기는 목업 모드 예시 문장입니다. /search API가 연결되면 실데이터가 들어옵니다.",
                "score": 0.83
            }
        ]

    # 2) 실제 /search 호출
    url = f"{base_url.rstrip('/')}/search"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {"query": query, "k": k}
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()
