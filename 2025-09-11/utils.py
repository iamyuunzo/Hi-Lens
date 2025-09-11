# utils.py
# ------------------------------------------------------------
# PDF 텍스트 간단 프리뷰(앞 몇 페이지만). 실 인덱싱은 팀 파이프라인에서 처리.
# ------------------------------------------------------------
import fitz  # PyMuPDF
from io import BytesIO

def extract_text_from_pdf(file_bytes: bytes, max_pages: int = 1) -> str:
    doc = fitz.open(stream=BytesIO(file_bytes), filetype="pdf")
    out = []
    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        out.append(page.get_text())
    doc.close()
    return "\n".join(out).strip()
