# services/document_service.py

import io
import re
from fastapi import UploadFile, HTTPException
from pypdf import PdfReader
from docx import Document as DocxDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter

from services.supabase_service import supabase, document_exists
from tools.rag_tool import embeddings


def extract_text(file: UploadFile, content: bytes) -> str:
    filename = file.filename.lower()

    if filename.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    elif filename.endswith(".docx"):
        doc = DocxDocument(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs)

    else:
        raise HTTPException(status_code=400, detail="File must be .pdf or .docx")


# ---- Strategy 1: Structure-aware chunking ----
def split_by_structure(text: str) -> list[str]:
    heading_pattern = r'\n(?=(?:Week \d+|Day \d+|Capstone Project|Program Overview)[:\s])'
    sections = re.split(heading_pattern, text)
    return [s.strip() for s in sections if s.strip()]


# ---- Strategy 2: Recursive character splitting ----
def split_recursively(section: str, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    return splitter.split_text(section)


def chunk_document(text: str) -> list[str]:
    final_chunks = []
    sections = split_by_structure(text)

    for section in sections:
        if len(section) <= 800:
            final_chunks.append(section)
        else:
            # NOTE: semantic chunking (per-sentence embedding) was tried here
            # but disabled — it burns one Gemini embedding call per sentence,
            # which blows through the free-tier per-minute rate limit on any
            # reasonably sized document. Recursive splitting is used for all
            # larger sections instead, as a deliberate free-tier trade-off.
            final_chunks.extend(split_recursively(section))

    return final_chunks


async def process_document(file: UploadFile, user_id: str, session_id: str) -> dict:
    if document_exists(file.filename, session_id):
        return {"duplicate": True, "filename": file.filename}

    content = await file.read()
    text = extract_text(file, content)

    if not text.strip():
        raise HTTPException(status_code=400, detail="No extractable text found in document")

    chunks = chunk_document(text)

    doc_result = supabase.table("kb_documents").insert({
        "user_id": user_id,
        "session_id": session_id,
        "filename": file.filename,
    }).execute()
    document_id = doc_result.data[0]["id"]

    chunk_rows = []
    for chunk_text in chunks:
        vector = embeddings.embed_query(chunk_text)
        chunk_rows.append({
            "document_id": document_id,
            "content": chunk_text,
            "embedding": vector,
        })

    supabase.table("kb_chunks").insert(chunk_rows).execute()

    return {
        "duplicate": False,
        "document_id": document_id,
        "filename": file.filename,
        "chunks_created": len(chunk_rows),
    }