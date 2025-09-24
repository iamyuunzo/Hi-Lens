from llm import explain_tables, answer_with_context, get_provider_name

print("LLM Provider =", get_provider_name())

dummy_table = {
    "title": "정부 지출 추이",
    "page_label": "12",
    "preview_md": """
| 연도 | 정부지출(억원) |
|------|--------------|
| 2020 | 1675 |
| 2021 | 2540 |
| 2022 | 4021 |
| 2023 | 5920 |
| 2024 | 6856 |
""",
}

print("\n=== explain_tables 테스트 ===")
print(explain_tables("정부 지출 추이를 요약해줘", [dummy_table]))

print("\n=== answer_with_context 테스트 ===")
print(answer_with_context(
    "주요 특징을 3줄로 요약해줘",
    "정부 지출은 2020년 1,675억원에서 2024년 6,856억원으로 크게 증가하였다.",
    page_label="12"
))
