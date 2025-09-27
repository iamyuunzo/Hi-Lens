# 🧡 Hi-Lens
<br><br>

<p align="center">
<img width="600" height="408" alt="image" src="https://github.com/user-attachments/assets/0db8f191-eb0e-44a7-92ce-ddd558b8077b" />
</p>

<div align="center">

**_로컬 AI 메이커스랩 1팀, 현대해상 대체투자2팀의 PDF 요약·발췌·시각화 도우미 'Hi-Lens' 입니다._** <br>
<br>

</div>

<br>

## 🟠 프로젝트 소개
- **Comento(코멘토)** 주관 **로컬 AI 메이커스랩**
  - Topic - **_'현대해상 대체투자2팀 - 인프라 투자 스터디의 어려움을 겪는 현직자의 문제를 해결할 수 있는 보고서 툴'_** <br>

- 현업자가 인프라 대체 투자를 위해 자주 사용하는 **KEEI(에너지경제연구원)** 의 PDF 원문 분석을 기준으로 MVP 프로토타입을 구현했습니다.
- 현업자분께서 *_'400억 정도의 연료 전지 관련 투자건에 있어 Hi-Lens의 서비스가 실제로 도움이 되었다.'_* 는 평을 하였고, **사용편의성(8/10), 처리속도(7/10), 정확성(10/10), 답변완전성(9/10)** 이라는 높은 피드백 평가를 받았습니다.


<br>

## 🕰️ 프로젝트 기간
- **_25.09.01. ~ 25.09.26.<br><br>_**

<br>

## 💁🏻 Team
| <img src="https://i.pinimg.com/736x/19/1d/fc/191dfcfe09061160dc7d842a21e3d3f0.jpg" width="280"/> | <img src="https://i.pinimg.com/1200x/e8/af/93/e8af9320376ef490e1c8eeb76930857e.jpg" width="250"/> | <img src="https://i.pinimg.com/736x/3b/53/af/3b53af1d90e9fb9077844e9f273ba99f.jpg" width="250"/> | <img src="https://i.pinimg.com/736x/2b/f0/7c/2bf07cb51234173ebfc5e5bde1bba73f.jpg" width="250"/> |
|:--------------------------------------:|:---------------------------------------:|:------------------------------------:|:------------------------------------:|
| [**조윤주**](https://github.com/iamyuunzo) | [**남희수**](https://github.com/msu1603-web)| [**류채민**](https://github.com/ryunnwave) | [**소재만**](https://github.com/chssdk-web) |
| 경남대학교 전자SW공학과<br>**기획 및 주요 개발 담당**  | 부산대학교 경영학과<br>**기획 및 PPT 담당 (PM)** | 울산대학교 경영경제융합학부<br>**기획 및 발표 담당 (PM)** | 경상대학교 도시공학과<br>**기획 및 서브 개발 담당** |

<br><br>

## 💫 프로토타입 소개
#### "PDF/문서 원문 기반 분석, LLM을 이용해서 질의응답/요약/표·그림 근거 추출 tool"

### 🧰 Tech Stack

| 구분 | 사용 기술 |
|------|-----------|
| **Front-end / UI** | Streamlit |
| **Back-end / Logic** | Python |
| **AI / LLM** | OpenAI GPT, Pontens. AI, Google Gemini (API 키 교체 가능) |
| **PDF 처리** | PyMuPDF (표/그림 bbox 탐지 및 크롭), pypdf (페이지 텍스트 추출) |
| **검색 / RAG** | rank-bm25 (BM25 검색), sentence-transformers (+torch, 선택, 임베딩 검색) |
| **데이터 / 이미지** | pandas, numpy (표 가공/렌더링), Pillow (이미지 핸들링), pytesseract (OCR 폴백, 선택) |
| **환경 관리** | python-dotenv (.env 로컬 관리) |

<br>

### ⚙️ Features

| 기능 | 설명 |
|------|------|
| **PDF 원문 요약** | 업로드한 PDF 전체를 AI가 분석하여 핵심 내용을 간략하게 요약 제공 |
| **추천 질문 생성** | 문서 내용을 기반으로 추가 질문(FAQ 스타일) 자동 제안 |
| **표 / 그림 목차 생성** | PDF 내 시각화 자료(표, 이미지, 그래프 등)를 탐지하여 목차화하고, 각 항목별 간단 요약 표시 |
| **표 추출 / 변환** | 단순 마크다운이 아닌 **pandas DataFrame**으로 변환하여 깔끔한 표 형태로 표시 (실험적 기능) |
| **질의응답 (Q&A)** | PDF 원문 및 표/그림 내용을 근거로 AI가 답변 제공. 추측 없이 “없으면 없다”라고 답변하도록 설계 (할루시네이션 방지) |
| **원문 근거 제시** | 모든 답변에 대해 해당되는 PDF 페이지/문맥을 함께 제시하여 신뢰성 확보 |
| **OCR 지원 (선택)** | 스캔된 PDF/이미지 내 표를 인식하여 텍스트로 변환 (Tesseract 필요) |

<br>

### 📄 Pages

<details>
<summary><b>1. Landing Page</b></summary>

- LLM 대화 기록, PDF Input, LLM 종류 확인 가능  
<img width="600" height="400" alt="image" src="https://github.com/user-attachments/assets/54fa8d9b-04d5-49d2-b2d0-9ee33cb20897" />

</details>

<details>
<summary><b>2. Loading Page</b></summary>

- Python으로 PDF 원문 분석 후 LLM에게 분석 내용을 넘김  
- 현업자의 니즈 중 하나인 **할루시네이션 방지**를 위해 LLM이 추론/창작을 하지 못하도록 규칙 설정  
<img width="600" height="400" alt="image" src="https://github.com/user-attachments/assets/ddbe5f7f-1735-47cd-afd5-4a6adb7921ae" />

</details>

<details>
<summary><b>3. Analysis Page (대화 탭)</b></summary>

- PDF 원문 관련 요약 및 추천 질문  
<img width="600" height="400" alt="image" src="https://github.com/user-attachments/assets/da3523d3-e3a9-47df-923c-250c11e9fb8b" />

- PDF 원문 관련 질의응답 가능  
<img width="600" height="400" alt="image" src="https://github.com/user-attachments/assets/3cc44c0d-a9c6-459f-987e-5a40c4fde617" />

</details>

<details>
<summary><b>4. Analysis Page (표 / 그림 목차 탭)</b></summary>

- PDF 원문 안의 표, 이미지, 그래프 등의 시각화 자료들을 인식하여 각각 목차로 정리  
<img width="600" height="400" alt="image" src="https://github.com/user-attachments/assets/ae507620-02b5-4fe8-989c-bb82b556557e" />

- 각 목차 안의 버튼 클릭 시 LLM이 관련 내용을 찾아서 요약하고 원문 출처까지 제공  
<img width="600" height="400" alt="image" src="https://github.com/user-attachments/assets/93533f96-af64-4050-913f-caa35598b117" />  
<img width="600" height="400" alt="image" src="https://github.com/user-attachments/assets/790a8a55-7240-4ab6-abcf-d91d128def6b" />

</details>

<br>

## 💫 향후 고도화 계획
- 통합 DB 구축 : KEEI 한정이 아니라 여러 보고서를 넣어 비교 분석 할 수 있도록 구현
- 맞춤형 표 생성 : 추출된 텍스트에서 필요한 정보만 선별하여 새로운 맞춤형 표 제공
- 웹 개발 시작 : 현재 Python과 Streamlit의 한계로 다른 적절한 언어를 사용하여 리팩토링 계획

<br>

## 🧑‍🤝‍🧑 발표 자료
- [Hi-Lens 최종 발표.pdf](https://github.com/user-attachments/files/22571971/Hi-Lens.pdf)

