"""
IDP Platform — Intelligent Document Processing Backend
FastAPI server providing PDF upload, RAG chat, and structured extraction.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import TEMP_DIR, CHROMA_DIR, TESSERACT_AVAILABLE
from api import chat, extract, upload, documents

@asynccontextmanager
async def lifespan(app: FastAPI):
    TEMP_DIR.mkdir(exist_ok=True)
    CHROMA_DIR.mkdir(exist_ok=True)
    yield

app = FastAPI(
    title="IDP Platform API",
    description="Intelligent Document Processing — upload, chat & extract (Modular)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded PDFs as static files
TEMP_DIR.mkdir(exist_ok=True)
app.mount("/files", StaticFiles(directory=str(TEMP_DIR)), name="files")

# Include Modular Routers
app.include_router(upload.router)
app.include_router(chat.router)
app.include_router(extract.router)
app.include_router(documents.router)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "ocr_available": TESSERACT_AVAILABLE,
        "pdf_engine": "PyMuPDF",
        "vector_store": "ChromaDB",
    }
