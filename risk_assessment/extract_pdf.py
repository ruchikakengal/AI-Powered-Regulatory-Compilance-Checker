import PyPDF2
from langchain.text_splitter import RecursiveCharacterTextSplitter

def extract_clauses(pdf_path):
    clauses = []

    full_text = ""
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += "\n" + text

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", ".", ";"]
    )
    chunks = splitter.split_text(full_text)

    for chunk in chunks:
        chunk_clean = chunk.strip()
        if len(chunk_clean.split()) >= 5:
            clauses.append(chunk_clean)

    return clauses
