import streamlit as st
import pdfplumber
import os
import tempfile
from sentence_transformers import SentenceTransformer
import google.generativeai as genai
import re
from typing import List, Dict
import numpy as np
import pandas as pd

# 페이지 설정
st.set_page_config(
    page_title="PDF 문서 분석 AI v2",
    page_icon="📊",
    layout="wide"
)

# 세션 상태 초기화
if 'embedding_model' not in st.session_state:
    st.session_state.embedding_model = None
if 'documents_loaded' not in st.session_state:
    st.session_state.documents_loaded = False
if 'chunks_data' not in st.session_state:
    st.session_state.chunks_data = []
if 'embeddings' not in st.session_state:
    st.session_state.embeddings = []
if 'page_mapping' not in st.session_state:
    st.session_state.page_mapping = {}

class PDFAnalyzerV2:
    def __init__(self):
        self.embedding_model = None
        self.chunks_data = []
        self.embeddings = []
        self.page_mapping = {}
        
    def initialize_models(self):
        """모델 초기화"""
        if self.embedding_model is None:
            with st.spinner("임베딩 모델을 로딩중입니다..."):
                self.embedding_model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
        return True
    
    def extract_real_page_numbers(self, pdf_path):
        """실제 페이지 번호 추출"""
        page_mapping = {}
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    
                    # 페이지 하단에서 번호 찾기
                    lines = text.split('\n')
                    bottom_lines = lines[-3:]  # 마지막 3줄 확인
                    
                    real_page_num = None
                    for line in bottom_lines:
                        line = line.strip()
                        # 다양한 페이지 번호 패턴
                        patterns = [
                            r'-\s*(\d+)\s*-',      # - 46 -
                            r'^\s*(\d+)\s*$',      # 46
                            r'Page\s*(\d+)',       # Page 46
                            r'(\d+)\s*페이지',      # 46페이지
                            r'(\d+)\s*/\s*\d+',    # 46/100
                        ]
                        
                        for pattern in patterns:
                            match = re.search(pattern, line)
                            if match:
                                real_page_num = int(match.group(1))
                                break
                        if real_page_num:
                            break
                    
                    # 실제 번호를 찾지 못하면 순서 번호 사용
                    if real_page_num is None:
                        real_page_num = i + 1
                    
                    page_mapping[i + 1] = real_page_num
                    
        except Exception as e:
            st.warning(f"페이지 번호 추출 중 오류: {str(e)}")
            # 기본 매핑 (순서대로)
            return {i+1: i+1 for i in range(100)}
        
        return page_mapping
    
    def extract_text_and_tables_from_pdf(self, pdf_file):
        """PDF에서 텍스트와 표 모두 추출 (개선된 버전)"""
        pages_data = []
        
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(pdf_file.read())
                tmp_file_path = tmp_file.name
            
            # 실제 페이지 번호 매핑 생성
            self.page_mapping = self.extract_real_page_numbers(tmp_file_path)
            st.session_state.page_mapping = self.page_mapping
            
            with pdfplumber.open(tmp_file_path) as pdf:
                for page_index, page in enumerate(pdf.pages):
                    sequence_num = page_index + 1
                    real_page_num = self.page_mapping.get(sequence_num, sequence_num)
                    
                    # 텍스트 추출
                    page_text = page.extract_text() or ""
                    
                    # 표 추출 및 처리
                    tables = page.extract_tables()
                    table_text = ""
                    
                    if tables:
                        for table_idx, table in enumerate(tables):
                            table_text += f"\n\n[표 {table_idx + 1} - 페이지 {real_page_num}]\n"
                            
                            # 표 데이터 처리 (merge cell 고려)
                            processed_table = self.process_table_data(table)
                            
                            # 표를 구조화된 텍스트로 변환
                            for row_idx, row in enumerate(processed_table):
                                if row_idx == 0:  # 헤더
                                    table_text += "| " + " | ".join(str(cell) for cell in row) + " |\n"
                                    table_text += "|" + "|".join("---" for _ in row) + "|\n"
                                else:  # 데이터 행
                                    table_text += "| " + " | ".join(str(cell) for cell in row) + " |\n"
                    
                    combined_text = page_text + table_text
                    
                    if combined_text.strip():
                        pages_data.append({
                            'sequence_num': sequence_num,
                            'real_page_num': real_page_num,
                            'text': combined_text.strip(),
                            'has_tables': len(tables) > 0,
                            'table_count': len(tables)
                        })
            
            os.unlink(tmp_file_path)
            return pages_data
            
        except Exception as e:
            st.error(f"PDF 추출 중 오류 발생: {str(e)}")
            return []
    
    def process_table_data(self, table):
        """표 데이터 처리 - merge cell 및 빈 셀 처리"""
        processed_table = []
        
        for row_idx, row in enumerate(table):
            processed_row = []
            prev_cell_value = ""
            
            for cell_idx, cell in enumerate(row):
                if cell is None or str(cell).strip() == "":
                    # 빈 셀 처리
                    if cell_idx > 0 and prev_cell_value:
                        # 이전 셀과 병합된 것으로 추정
                        processed_row.append(f"[{prev_cell_value}]")
                    else:
                        processed_row.append("[빈셀]")
                else:
                    cell_value = str(cell).strip()
                    processed_row.append(cell_value)
                    prev_cell_value = cell_value
            
            processed_table.append(processed_row)
        
        return processed_table
    
    def smart_text_chunking_v2(self, pages_data: List[Dict], chunk_size: int = 1500, overlap: int = 300):
        """개선된 스마트 텍스트 청킹 - 표 제목과 내용 보존"""
        chunks = []
        
        for page_data in pages_data:
            real_page_num = page_data['real_page_num']
            text = page_data['text']
            
            # 표 제목 패턴 감지 및 보존
            table_sections = self.identify_table_sections(text)
            
            if table_sections:
                # 표가 있는 경우 - 표 단위로 청킹
                for section in table_sections:
                    if len(section) > chunk_size:
                        # 큰 표는 적절히 분할
                        sub_chunks = self.split_large_section(section, chunk_size, overlap)
                        for sub_chunk in sub_chunks:
                            chunks.append({
                                'text': sub_chunk,
                                'real_page_num': real_page_num,
                                'chunk_id': len(chunks),
                                'has_table': True
                            })
                    else:
                        chunks.append({
                            'text': section,
                            'real_page_num': real_page_num,
                            'chunk_id': len(chunks),
                            'has_table': True
                        })
            else:
                # 일반 텍스트 청킹
                text_chunks = self.split_text_by_sentences(text, chunk_size, overlap)
                for chunk_text in text_chunks:
                    chunks.append({
                        'text': chunk_text,
                        'real_page_num': real_page_num,
                        'chunk_id': len(chunks),
                        'has_table': False
                    })
        
        return chunks
    
    def identify_table_sections(self, text):
        """텍스트에서 표 섹션 식별"""
        sections = []
        
        # 표 제목 패턴들
        table_patterns = [
            r'<[^>]+>.*?(?=\n\n|\n<|$)',  # <제목> 형태
            r'\[표[^\]]*\].*?(?=\n\n|\n\[|$)',  # [표 X] 형태
            r'표\s*\d+.*?(?=\n\n|표\s*\d+|$)',  # 표 1, 표 2 형태
        ]
        
        for pattern in table_patterns:
            matches = re.finditer(pattern, text, re.DOTALL)
            for match in matches:
                section = match.group().strip()
                if len(section) > 50:  # 너무 짧은 건 제외
                    sections.append(section)
        
        return sections
    
    def split_large_section(self, section, chunk_size, overlap):
        """큰 섹션을 적절히 분할"""
        if len(section) <= chunk_size:
            return [section]
        
        chunks = []
        start = 0
        
        while start < len(section):
            end = start + chunk_size
            
            if end >= len(section):
                chunks.append(section[start:])
                break
            
            # 적절한 분할 지점 찾기 (줄바꿈 기준)
            split_point = section.rfind('\n', start, end)
            if split_point == -1:
                split_point = end
            
            chunks.append(section[start:split_point])
            start = split_point - overlap
            
        return chunks
    
    def split_text_by_sentences(self, text, chunk_size, overlap):
        """문장 단위로 텍스트 분할"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                # 오버랩 처리
                overlap_sentences = current_chunk.split('.')[-2:]
                current_chunk = '. '.join(overlap_sentences).strip() + '. ' + sentence
            else:
                current_chunk += ' ' + sentence
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def create_embeddings(self, chunks: List[Dict], filename: str):
        """임베딩 생성 및 저장"""
        try:
            self.chunks_data = chunks
            self.embeddings = []
            
            with st.spinner(f"문서를 벡터화하고 있습니다... ({len(chunks)}개 청크)"):
                progress_bar = st.progress(0)
                
                for i, chunk_data in enumerate(chunks):
                    chunk_text = chunk_data['text']
                    embedding = self.embedding_model.encode([chunk_text])[0]
                    self.embeddings.append(embedding)
                    
                    progress_bar.progress((i + 1) / len(chunks))
                
                progress_bar.empty()
            
            st.session_state.chunks_data = self.chunks_data
            st.session_state.embeddings = self.embeddings
            
            return True
            
        except Exception as e:
            st.error(f"임베딩 생성 중 오류: {str(e)}")
            return False
    
    def cosine_similarity(self, a, b):
        """코사인 유사도 계산"""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    def hybrid_search_v2(self, query: str, n_results: int = 10) -> List[Dict]:
        """하이브리드 검색 - 키워드 + 의미 검색 + 표 특화"""
        if not self.chunks_data or not self.embeddings:
            return []
        
        try:
            # 1. 표 관련 질문 감지
            is_table_query = self.detect_table_query(query)
            
            # 2. 의미 검색
            query_embedding = self.embedding_model.encode([query])[0]
            semantic_scores = []
            
            for i, embedding in enumerate(self.embeddings):
                similarity = self.cosine_similarity(query_embedding, embedding)
                semantic_scores.append(similarity)
            
            # 3. 키워드 검색
            keyword_scores = self.calculate_keyword_scores(query)
            
            # 4. 점수 결합 및 가중치 적용
            combined_results = []
            for i in range(len(self.chunks_data)):
                chunk_data = self.chunks_data[i]
                
                # 기본 점수 결합
                semantic_weight = 0.6
                keyword_weight = 0.4
                
                # 표 관련 질문이면 표가 있는 청크에 보너스
                table_bonus = 0
                if is_table_query and chunk_data.get('has_table', False):
                    table_bonus = 0.2
                
                # 최종 점수
                final_score = (semantic_scores[i] * semantic_weight + 
                             keyword_scores[i] * keyword_weight + 
                             table_bonus)
                
                combined_results.append({
                    'index': i,
                    'final_score': final_score,
                    'semantic_score': semantic_scores[i],
                    'keyword_score': keyword_scores[i],
                    'table_bonus': table_bonus,
                    'chunk_data': chunk_data
                })
            
            # 점수 순으로 정렬
            combined_results.sort(key=lambda x: x['final_score'], reverse=True)
            
            # 결과 포맷팅
            results = []
            for i, item in enumerate(combined_results[:n_results]):
                chunk_data = item['chunk_data']
                results.append({
                    'text': chunk_data['text'],
                    'real_page_num': chunk_data['real_page_num'],
                    'chunk_id': chunk_data['chunk_id'],
                    'has_table': chunk_data.get('has_table', False),
                    'similarity_score': item['final_score'],
                    'semantic_score': item['semantic_score'],
                    'keyword_score': item['keyword_score'],
                    'table_bonus': item['table_bonus'],
                    'rank': i + 1
                })
            
            return results
            
        except Exception as e:
            st.error(f"검색 중 오류 발생: {str(e)}")
            return []
    
    def detect_table_query(self, query):
        """표 관련 질문 감지"""
        table_keywords = [
            '표', '도표', '차트', '그래프', '데이터', '수치', '통계',
            '결과', '현황', '비교', '분석', '정리', '엑셀', '시트'
        ]
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in table_keywords)
    
    def calculate_keyword_scores(self, query):
        """키워드 매칭 점수 계산"""
        query_lower = query.lower()
        query_words = [word for word in query_lower.split() if len(word) > 1]
        
        keyword_scores = []
        for chunk_data in self.chunks_data:
            text_lower = chunk_data['text'].lower()
            
            score = 0
            for word in query_words:
                # 정확한 단어 매칭
                if word in text_lower:
                    score += text_lower.count(word) * 2
                
                # 부분 매칭
                for text_word in text_lower.split():
                    if word in text_word and len(word) > 2:
                        score += 0.5
            
            # 정규화
            max_possible = len(query_words) * 10
            normalized_score = min(score / max_possible, 1.0) if max_possible > 0 else 0
            keyword_scores.append(normalized_score)
        
        return keyword_scores
    
    def generate_contextual_answer(self, question: str, search_results: List[Dict], api_key: str):
        """맥락을 고려한 답변 생성 (페이지 번호 정확성 개선)"""
        if not search_results:
            return "관련 정보를 찾을 수 없습니다.", []
        
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-pro-latest')
            
            # 페이지별로 결과 그룹화 (실제 페이지 번호 기준)
            page_groups = {}
            for result in search_results:
                page_num = result['real_page_num']
                if page_num not in page_groups:
                    page_groups[page_num] = []
                page_groups[page_num].append(result)
            
            context_parts = []
            source_info = []
            
            for page_num in sorted(page_groups.keys()):
                page_results = page_groups[page_num]
                page_results.sort(key=lambda x: x['similarity_score'], reverse=True)
                
                for i, result in enumerate(page_results[:2]):
                    excerpt_num = len(context_parts) + 1
                    context_parts.append(f"[페이지 {page_num}, 발췌 {excerpt_num}]\n{result['text']}")
                    source_info.append({
                        'real_page_num': page_num,
                        'text': result['text'],
                        'similarity_score': result['similarity_score'],
                        'has_table': result['has_table'],
                        'excerpt_num': excerpt_num
                    })
            
            context = "\n\n".join(context_parts)
            
            prompt = f"""
다음은 PDF 문서에서 발췌한 내용들입니다:

{context}

질문: {question}

지시사항:
1. 위 문서 발췌 내용에서만 답변하세요.
2. 답변은 반드시 원문 그대로 인용하세요. 절대 요약하거나 바꿔쓰지 마세요.
3. 여러 발췌 내용이 관련있다면 모두 포함하세요.
4. 문서에 해당 정보가 없으면 "관련 정보를 찾을 수 없습니다"라고 답하세요.
5. 답변할 때 반드시 정확한 페이지 번호를 명시하세요: [페이지 X, 발췌 Y]
6. 표 데이터의 경우 구조를 최대한 보존하여 인용하세요.
7. 숫자, 날짜, 고유명사는 원문 그대로 정확히 인용하세요.
8. 표를 엑셀 형태로 정리하라는 요청이면 | 구분자를 사용하여 정리하세요.
"""
            
            response = model.generate_content(prompt)
            return response.text, source_info
            
        except Exception as e:
            return f"답변 생성 중 오류 발생: {str(e)}", []

# 메인 애플리케이션
def main():
    st.title("📊 PDF 문서 분석 AI v2")
    st.markdown("**🆕 개선사항:** 정확한 페이지 번호 | 표 처리 강화 | 키워드 검색 개선")
    
    # 사이드바
    with st.sidebar:
        st.header("⚙️ 설정")
        api_key = st.text_input("Google Gemini API 키", type="password", 
                               help="https://aistudio.google.com/app/apikey 에서 발급받으세요")
        
        if not api_key:
            st.warning("API 키를 입력해주세요!")
        
        st.markdown("---")
        st.markdown("### 🆕 v2 개선사항")
        st.markdown("""
        - ✅ **정확한 페이지 번호** (문서 하단 기준)
        - ✅ **키워드 검색 강화** (페이지 번호 없이도 검색)
        - ✅ **표 처리 개선** (merge cell 지원)
        - ✅ **하이브리드 검색** (의미+키워드)
        """)
        
        st.markdown("---")
        st.markdown("### 📖 사용법")
        st.markdown("""
        1. Google Gemini API 키 입력
        2. PDF 파일 업로드
        3. 문서 처리 대기
        4. 질문 입력하여 검색
        """)
    
    # PDF 분석기 초기화
    if 'analyzer' not in st.session_state:
        st.session_state.analyzer = PDFAnalyzerV2()
    
    analyzer = st.session_state.analyzer
    
    # 모델 초기화
    if not st.session_state.get('models_initialized', False):
        if analyzer.initialize_models():
            st.session_state.models_initialized = True
            st.session_state.embedding_model = analyzer.embedding_model
    
    # 파일 업로드
    uploaded_file = st.file_uploader("PDF 파일을 업로드하세요", type=['pdf'])
    
    if uploaded_file is not None:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.info(f"📁 업로드된 파일: {uploaded_file.name}")
        
        with col2:
            process_button = st.button("🚀 v2 처리 시작", type="primary")
        
        if process_button and api_key:
            with st.spinner("PDF 문서를 v2 방식으로 처리하고 있습니다..."):
                # 텍스트 및 표 추출
                st.write("🔍 텍스트 및 표 추출 중...")
                pages_data = analyzer.extract_text_and_tables_from_pdf(uploaded_file)
                
                if pages_data:
                    total_chars = sum(len(page['text']) for page in pages_data)
                    table_pages = sum(1 for page in pages_data if page['has_tables'])
                    
                    st.success(f"✅ 추출 완료: {len(pages_data)}페이지, {total_chars:,}글자, 표 포함 페이지: {table_pages}개")
                    
                    # 페이지 매핑 정보 표시
                    if st.session_state.page_mapping:
                        mapping_info = []
                        for seq, real in list(st.session_state.page_mapping.items())[:5]:
                            mapping_info.append(f"순서{seq}→실제{real}")
                        st.info(f"📄 페이지 매핑 예시: {', '.join(mapping_info)}...")
                    
                    # 스마트 청킹
                    st.write("🧠 스마트 텍스트 분할 중...")
                    chunks = analyzer.smart_text_chunking_v2(pages_data)
                    table_chunks = sum(1 for chunk in chunks if chunk.get('has_table', False))
                    
                    st.success(f"✅ 분할 완료: {len(chunks)}개 청크 (표 포함: {table_chunks}개)")
                    
                    # 임베딩 생성
                    st.write("🗄️ 벡터 데이터베이스 생성 중...")
                    if analyzer.create_embeddings(chunks, uploaded_file.name):
                        st.success("🎉 v2 처리 완료! 이제 개선된 검색을 사용할 수 있습니다.")
                        st.session_state.documents_loaded = True
                    else:
                        st.error("❌ 임베딩 생성 실패")
                else:
                    st.error("❌ 텍스트 추출 실패")
    
    # 질문 섹션
    if st.session_state.documents_loaded and api_key:
        st.markdown("---")
        st.header("💬 개선된 문서 검색")
        
        # 예시 질문들
        st.markdown("**💡 테스트 질문 예시:**")
        example_questions = [
            "전국 기준 설비예비율 산출 결과 표 정리해줘",  # 페이지 번호 없이
            "46쪽 표를 엑셀용으로 정리해줘",  # 페이지 번호 있이
            "주요 재무 지표는 무엇인가?",
            "리스크 요인 분석",
            "향후 전망 및 계획"
        ]
        
        cols = st.columns(2)
        for i, question in enumerate(example_questions):
            with cols[i % 2]:
                if st.button(question, key=f"example_{i}"):
                    st.session_state.current_question = question
        
        # 질문 입력
        question = st.text_input("질문을 입력하세요:", 
                                value=st.session_state.get('current_question', ''),
                                placeholder="예: 설비예비율 표를 엑셀 형태로 정리해줘")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            search_button = st.button("🔍 v2 검색", type="primary")
        with col2:
            clear_button = st.button("🗑️ 초기화")
        
        if clear_button:
            st.session_state.current_question = ""
            st.rerun()
        
        if search_button and question:
            with st.spinner("하이브리드 검색으로 최적의 답변을 생성하고 있습니다..."):
                # 세션에서 데이터 복원
                analyzer.chunks_data = st.session_state.chunks_data
                analyzer.embeddings = st.session_state.embeddings
                analyzer.page_mapping = st.session_state.page_mapping
                
                # 하이브리드 검색
                search_results = analyzer.hybrid_search_v2(question, n_results=10)
                
                if search_results:
                    # 답변 생성
                    answer, source_info = analyzer.generate_contextual_answer(question, search_results, api_key)
                    
                    # 결과 표시
                    st.markdown("### 📋 답변")
                    st.markdown(answer)
                    
                    # 출처 정보 (개선된 페이지 번호)
                    if source_info:
                        st.markdown("### 📍 출처 정보 (실제 페이지 번호)")
                        source_df_data = []
                        for info in source_info:
                            source_df_data.append({
                                "발췌": info['excerpt_num'],
                                "실제 페이지": info['real_page_num'],
                                "관련성": f"{info['similarity_score']:.2%}",
                                "표 포함": "✅" if info['has_table'] else "❌",
                                "길이": f"{len(info['text'])}자"
                            })
                        
                        st.dataframe(source_df_data, use_container_width=True)
                    
                    # 상세 검색 결과
                    with st.expander("🔍 상세 검색 결과 보기"):
                        for i, result in enumerate(search_results[:6]):
                            score_info = (f"종합: {result['similarity_score']:.2%} | "
                                        f"의미: {result['semantic_score']:.2%} | "
                                        f"키워드: {result['keyword_score']:.2%}")
                            if result['table_bonus'] > 0:
                                score_info += f" | 표보너스: +{result['table_bonus']:.1%}"
                            
                            st.markdown(f"**📄 실제 페이지 {result['real_page_num']} | {score_info}**")
                            st.text_area(f"내용 {i+1}", result['text'], height=150, key=f"result_{i}")
                            st.markdown("---")
                else:
                    st.warning("⚠️ 관련 정보를 찾을 수 없습니다.")
    
    elif not api_key:
        st.warning("⚠️ Google Gemini API 키를 입력해주세요.")
    elif not st.session_state.documents_loaded:
        st.info("📄 PDF 파일을 업로드하고 v2 처리를 시작해주세요.")
    
    # 하단 정보
    st.markdown("---")
    st.markdown("**🔧 v2 특징:** 실제 페이지 번호 | 표 구조 보존 | 하이브리드 검색 | merge cell 지원")

if __name__ == "__main__":
    main()
