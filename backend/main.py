"""
IDP Platform — Intelligent Document Processing Backend
FastAPI server providing PDF upload, RAG chat, and structured extraction.
Uses PyMuPDF + Tesseract OCR for fast PDF processing and ChromaDB for vectors.
"""

import os
import io
import uuid
import shutil
import logging
from pathlib import Path
from typing import List, Optional, Any, Dict
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, create_model
from dotenv import load_dotenv
import json
import asyncio
from typing import Generator, AsyncGenerator

# LangChain
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage

# ChromaDB
import chromadb
from chromadb.config import Settings as ChromaSettings

# PDF / OCR
import fitz  # PyMuPDF
from PIL import Image
import pytesseract

# Instructor
import instructor
from openai import OpenAI
import google.generativeai as genai

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tesseract Configuration (Windows compatibility)
# ---------------------------------------------------------------------------
TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Tesseract-OCR\tesseract.exe",
]


def configure_tesseract() -> bool:
    """Configure pytesseract with the correct path on Windows."""
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        pass

    for path in TESSERACT_PATHS:
        if Path(path).exists():
            pytesseract.pytesseract.tesseract_cmd = path
            try:
                pytesseract.get_tesseract_version()
                return True
            except Exception:
                continue

    return False


TESSERACT_AVAILABLE = configure_tesseract()
if TESSERACT_AVAILABLE:
    logger.info("Tesseract OCR is available — scanned PDFs supported")
else:
    logger.warning("Tesseract OCR not found — only text-based PDFs supported")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TEMP_DIR = Path("temp")
CHROMA_DIR = Path("chroma_db")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
TOP_K_CHUNKS = 4
OLLAMA_EMBED_MODEL = "nomic-embed-text"

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    masked = GOOGLE_API_KEY[:8] + "..." + GOOGLE_API_KEY[-4:] if len(GOOGLE_API_KEY) > 12 else "***"
    logger.info("Google API key loaded: %s", masked)

# ---------------------------------------------------------------------------
# In-memory stores (replaced by a DB in production)
# ---------------------------------------------------------------------------
documents_store: Dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Singleton ChromaDB client
# ---------------------------------------------------------------------------
_chroma_client: chromadb.PersistentClient | None = None


def get_chroma_client() -> chromadb.PersistentClient:
    """Return a single persistent Chroma client (created once)."""
    global _chroma_client
    if _chroma_client is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _chroma_client


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    TEMP_DIR.mkdir(exist_ok=True)
    CHROMA_DIR.mkdir(exist_ok=True)
    yield

app = FastAPI(
    title="IDP Platform API",
    description="Intelligent Document Processing — upload, chat & extract",
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

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------
class DocumentInfo(BaseModel):
    document_id: str
    filename: str
    page_count: int
    status: str


class ConversationMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    document_id: str
    message: str
    mode: str = "local"  # "local" | "cloud"
    conversation_history: List[ConversationMessage] = []


class ChatResponse(BaseModel):
    response: str
    sources: List[str] = []


class FieldSchema(BaseModel):
    field_name: str
    data_type: str  # Text | Number | Date | List
    description: str = ""


class ExtractRequest(BaseModel):
    document_id: str
    schema_fields: List[FieldSchema]
    model_choice: str = "local"  # "local" | "cloud"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def raise_clean_error(exc: Exception) -> None:
    """Convert provider quota / auth errors into readable HTTP exceptions."""
    msg = str(exc)
    logger.error("Raw provider error: %s", msg)
    if "429" in msg or "quota" in msg.lower() or "rate" in msg.lower():
        retry_hint = ""
        if "retry" in msg.lower():
            import re
            match = re.search(r"retry in ([\d.]+)s", msg.lower())
            if match:
                retry_hint = f" (Google says retry in ~{int(float(match.group(1)))}s)"
        raise HTTPException(
            status_code=429,
            detail=(
                f"Google API rate limit hit{retry_hint}. "
                "Wait a moment and try again, or switch to the Local model."
            ),
        )
    if "401" in msg or "403" in msg or "API_KEY" in msg:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing GOOGLE_API_KEY. Check backend/.env",
        )
    raise HTTPException(status_code=500, detail=str(exc))


def get_embeddings():
    """Ollama embeddings used for all vector operations."""
    return OllamaEmbeddings(
        model=OLLAMA_EMBED_MODEL,
        base_url=OLLAMA_BASE_URL,
    )


def get_llm(mode: str):
    if mode == "cloud":
        if not GOOGLE_API_KEY:
            raise HTTPException(
                status_code=400,
                detail="GOOGLE_API_KEY is not configured. Set it in backend/.env",
            )
        return ChatGoogleGenerativeAI(
            model=GOOGLE_MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=0.3,
        )
    return ChatOllama(
        model="qwen2.5:32b",
        base_url=OLLAMA_BASE_URL,
        temperature=0.3,
    )


def get_vector_store(document_id: str) -> Chroma:
    """Load a persisted Chroma collection for the given document."""
    return Chroma(
        client=get_chroma_client(),
        collection_name=f"doc_{document_id}",
        embedding_function=get_embeddings(),
    )


# ---------------------------------------------------------------------------
# Enhanced PDF processing with OCR support (PyMuPDF + Tesseract)
# ---------------------------------------------------------------------------
def ocr_embedded_images(page: fitz.Page, pdf_doc: fitz.Document) -> List[str]:
    """
    Extract every embedded image on *page*, OCR each one, and return
    a list of non-trivial text strings found.
    """
    ocr_texts: List[str] = []
    try:
        image_list = page.get_images(full=True)
    except Exception:
        return ocr_texts

    for img_info in image_list:
        xref = img_info[0]
        try:
            base_image = pdf_doc.extract_image(xref)
            if not base_image:
                continue

            img = Image.open(io.BytesIO(base_image["image"]))
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            # Skip tiny images (icons, bullets, decorations)
            if img.width < 100 or img.height < 50:
                continue

            text = pytesseract.image_to_string(
                img, lang="eng", config="--psm 6 --oem 3",
            ).strip()

            if text and len(text) > 10:
                ocr_texts.append(text)
        except Exception as exc:
            logger.debug("Failed to OCR image xref %d: %s", xref, exc)

    return ocr_texts


def extract_text_from_pdf(pdf_path: str, deep_scan: bool = False) -> List[Document]:
    """
    Extract text from PDF using PyMuPDF with automatic OCR fallback
    for scanned / image-based pages via Tesseract.

    When *deep_scan* is True, every page's embedded images are also OCR'd
    and the results merged with the native text layer — capturing text
    inside diagrams, scanned tables, screenshots, etc.

    Returns a list of LangChain Document objects (one per page).
    """
    documents: List[Document] = []

    try:
        pdf_document = fitz.open(pdf_path)
        total_pages = len(pdf_document)

        for page_num in range(total_pages):
            page = pdf_document[page_num]
            native_text = page.get_text().strip()

            if deep_scan and TESSERACT_AVAILABLE:
                image_texts = ocr_embedded_images(page, pdf_document)
                if image_texts:
                    logger.info(
                        "Page %d: deep-scan OCR'd %d embedded image(s)",
                        page_num + 1, len(image_texts),
                    )
                parts = [native_text] + image_texts if native_text else image_texts
                text = "\n\n".join(parts)
            elif len(native_text) < 50 and TESSERACT_AVAILABLE:
                try:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    text = pytesseract.image_to_string(
                        img, lang="eng", config="--psm 6 --oem 3",
                    ).strip()
                    if text:
                        logger.info("Page %d: used OCR (scanned content)", page_num + 1)
                except Exception as ocr_err:
                    logger.warning("OCR failed on page %d: %s", page_num + 1, ocr_err)
                    text = ""
            else:
                text = native_text

            if text:
                documents.append(
                    Document(
                        page_content=text,
                        metadata={
                            "source": pdf_path,
                            "page": page_num + 1,
                            "total_pages": total_pages,
                        },
                    )
                )

        pdf_document.close()

    except Exception as exc:
        logger.error("Failed to process PDF %s: %s", pdf_path, exc)

    return documents


def extract_text_from_pdf_with_progress(
    pdf_path: str,
) -> Generator[dict, None, List[Document]]:
    """
    Generator that yields progress events while extracting text.
    Final yield is the list of Document objects.
    """
    documents: List[Document] = []

    try:
        pdf_document = fitz.open(pdf_path)
        total_pages = len(pdf_document)

        yield {
            "stage": "extracting",
            "message": f"Starting text extraction for {total_pages} pages",
            "current_page": 0,
            "total_pages": total_pages,
            "progress": 0,
        }

        for page_num in range(total_pages):
            page = pdf_document[page_num]
            used_ocr = False

            # Fast text extraction (works for text-based PDFs)
            text = page.get_text().strip()

            # If very little text found, try OCR on the rendered page image
            if len(text) < 50 and TESSERACT_AVAILABLE:
                try:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2× for quality
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    text = pytesseract.image_to_string(
                        img,
                        lang="eng",
                        config="--psm 6 --oem 3",
                    ).strip()
                    if text:
                        used_ocr = True
                        logger.info("Page %d: used OCR (scanned content)", page_num + 1)
                except Exception as ocr_err:
                    logger.warning("OCR failed on page %d: %s", page_num + 1, ocr_err)
                    text = ""

            if text:
                documents.append(
                    Document(
                        page_content=text,
                        metadata={
                            "source": pdf_path,
                            "page": page_num + 1,
                            "total_pages": total_pages,
                        },
                    )
                )

            progress = int(((page_num + 1) / total_pages) * 50)  # 0-50% for extraction
            yield {
                "stage": "extracting",
                "message": f"Page {page_num + 1}/{total_pages}" + (" (OCR)" if used_ocr else ""),
                "current_page": page_num + 1,
                "total_pages": total_pages,
                "progress": progress,
                "used_ocr": used_ocr,
            }

        pdf_document.close()

    except Exception as exc:
        logger.error("Failed to process PDF %s: %s", pdf_path, exc)
        yield {
            "stage": "error",
            "message": f"Failed to process PDF: {exc}",
            "progress": 0,
        }

    return documents


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "ocr_available": TESSERACT_AVAILABLE,
        "pdf_engine": "PyMuPDF",
        "vector_store": "ChromaDB",
    }


@app.post("/upload", response_model=DocumentInfo)
async def upload_document(
    file: UploadFile = File(...),
    deep_scan: bool = Query(False, description="OCR embedded images on every page"),
):
    """Accept a PDF, extract text (with OCR), chunk, and index in ChromaDB."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    document_id = str(uuid.uuid4())[:8]
    file_path = TEMP_DIR / f"{document_id}.pdf"

    # persist file
    with open(file_path, "wb") as buf:
        shutil.copyfileobj(file.file, buf)

    try:
        pages = extract_text_from_pdf(str(file_path), deep_scan=deep_scan)

        if not pages:
            raise ValueError(
                "No text could be extracted from the PDF. "
                "Check if the file is valid or if Tesseract OCR is installed."
            )

        total_chars = sum(len(p.page_content) for p in pages)
        logger.info(
            "Extracted %d pages, %d characters from %s",
            len(pages), total_chars, file.filename,
        )

        # Chunk
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )
        chunks = splitter.split_documents(pages)

        # Embed & store in ChromaDB
        client = get_chroma_client()
        collection_name = f"doc_{document_id}"

        # Remove stale collection if it somehow exists
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass

        Chroma.from_documents(
            documents=chunks,
            embedding=get_embeddings(),
            client=client,
            collection_name=collection_name,
        )

        full_text = "\n\n".join(p.page_content for p in pages)

        documents_store[document_id] = {
            "filename": file.filename,
            "file_path": str(file_path),
            "page_count": len(pages),
            "full_text": full_text,
            "status": "processed",
            "ocr_available": TESSERACT_AVAILABLE,
        }

        return DocumentInfo(
            document_id=document_id,
            filename=file.filename,
            page_count=len(pages),
            status="processed",
        )

    except Exception as exc:
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {exc}")


@app.post("/upload-stream")
async def upload_document_stream(
    file: UploadFile = File(...),
    deep_scan: bool = Query(False, description="OCR embedded images on every page"),
):
    """
    SSE endpoint for uploading with real-time progress updates.
    Returns Server-Sent Events with progress information.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    document_id = str(uuid.uuid4())[:8]
    file_path = TEMP_DIR / f"{document_id}.pdf"

    # Save file first
    with open(file_path, "wb") as buf:
        shutil.copyfileobj(file.file, buf)

    async def generate_events() -> AsyncGenerator[str, None]:
        try:
            # Phase 1: Extract text with progress
            yield f"data: {json.dumps({'stage': 'starting', 'message': 'Starting document processing...', 'progress': 0})}\n\n"
            await asyncio.sleep(0)  # Yield control

            pages: List[Document] = []
            total_pages = 0

            # Open PDF to get page count first
            pdf_doc = fitz.open(str(file_path))
            total_pages = len(pdf_doc)
            pdf_doc.close()

            yield f"data: {json.dumps({'stage': 'extracting', 'message': f'Found {total_pages} pages', 'progress': 2, 'total_pages': total_pages})}\n\n"
            await asyncio.sleep(0)

            # Extract text page by page with progress
            scan_label = "Deep scanning" if deep_scan else "Extracting"
            pdf_doc = fitz.open(str(file_path))
            for page_num in range(total_pages):
                page = pdf_doc[page_num]
                used_ocr = False
                ocr_image_count = 0

                native_text = page.get_text().strip()

                if deep_scan and TESSERACT_AVAILABLE:
                    image_texts = ocr_embedded_images(page, pdf_doc)
                    ocr_image_count = len(image_texts)
                    used_ocr = ocr_image_count > 0
                    parts = ([native_text] if native_text else []) + image_texts
                    text = "\n\n".join(parts)
                elif len(native_text) < 50 and TESSERACT_AVAILABLE:
                    try:
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        text = pytesseract.image_to_string(
                            img, lang="eng", config="--psm 6 --oem 3"
                        ).strip()
                        if text:
                            used_ocr = True
                    except Exception:
                        text = ""
                else:
                    text = native_text

                if text:
                    pages.append(
                        Document(
                            page_content=text,
                            metadata={
                                "source": str(file_path),
                                "page": page_num + 1,
                                "total_pages": total_pages,
                            },
                        )
                    )

                progress = int(2 + ((page_num + 1) / total_pages) * 48)  # 2-50%
                if deep_scan and ocr_image_count > 0:
                    ocr_label = f" (OCR: {ocr_image_count} img)"
                elif used_ocr:
                    ocr_label = " (OCR)"
                else:
                    ocr_label = ""
                yield f"data: {json.dumps({'stage': 'extracting', 'message': f'{scan_label} page {page_num + 1}/{total_pages}{ocr_label}', 'progress': progress, 'current_page': page_num + 1, 'total_pages': total_pages})}\n\n"
                await asyncio.sleep(0)

            pdf_doc.close()

            if not pages:
                yield f"data: {json.dumps({'stage': 'error', 'message': 'No text could be extracted from the PDF', 'progress': 0})}\n\n"
                return

            total_chars = sum(len(p.page_content) for p in pages)
            yield f"data: {json.dumps({'stage': 'chunking', 'message': f'Extracted {total_chars:,} characters, chunking...', 'progress': 52})}\n\n"
            await asyncio.sleep(0)

            # Phase 2: Chunk
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=CHUNK_SIZE,
                chunk_overlap=CHUNK_OVERLAP,
            )
            chunks = splitter.split_documents(pages)
            total_chunks = len(chunks)

            yield f"data: {json.dumps({'stage': 'embedding', 'message': f'Created {total_chunks} chunks, generating embeddings...', 'progress': 55, 'total_chunks': total_chunks})}\n\n"
            await asyncio.sleep(0)

            # Phase 3: Embed in batches with progress
            client = get_chroma_client()
            collection_name = f"doc_{document_id}"

            try:
                client.delete_collection(collection_name)
            except Exception:
                pass

            # Get embeddings instance once
            embeddings = get_embeddings()

            # Embed in batches for better progress tracking
            BATCH_SIZE = 10
            collection = client.get_or_create_collection(name=collection_name)

            for i in range(0, total_chunks, BATCH_SIZE):
                batch = chunks[i : i + BATCH_SIZE]
                batch_texts = [doc.page_content for doc in batch]
                batch_metadatas = [doc.metadata for doc in batch]
                batch_ids = [f"chunk_{i + j}" for j in range(len(batch))]

                # Generate embeddings for this batch
                batch_embeddings = embeddings.embed_documents(batch_texts)

                # Add to collection
                collection.add(
                    ids=batch_ids,
                    embeddings=batch_embeddings,
                    documents=batch_texts,
                    metadatas=batch_metadatas,
                )

                progress = int(55 + ((i + len(batch)) / total_chunks) * 40)  # 55-95%
                yield f"data: {json.dumps({'stage': 'embedding', 'message': f'Embedding chunks {i + 1}-{min(i + BATCH_SIZE, total_chunks)}/{total_chunks}', 'progress': progress, 'embedded_chunks': min(i + BATCH_SIZE, total_chunks), 'total_chunks': total_chunks})}\n\n"
                await asyncio.sleep(0)

            # Phase 4: Finalize
            yield f"data: {json.dumps({'stage': 'finalizing', 'message': 'Finalizing document index...', 'progress': 98})}\n\n"
            await asyncio.sleep(0)

            full_text = "\n\n".join(p.page_content for p in pages)

            documents_store[document_id] = {
                "filename": file.filename,
                "file_path": str(file_path),
                "page_count": len(pages),
                "full_text": full_text,
                "status": "processed",
                "ocr_available": TESSERACT_AVAILABLE,
            }

            # Final success event
            yield f"data: {json.dumps({'stage': 'complete', 'message': 'Document processed successfully!', 'progress': 100, 'document_id': document_id, 'filename': file.filename, 'page_count': len(pages)})}\n\n"

        except Exception as exc:
            logger.exception("Error in streaming upload")
            if file_path.exists():
                file_path.unlink()
            yield f"data: {json.dumps({'stage': 'error', 'message': str(exc), 'progress': 0})}\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/chat", response_model=ChatResponse)
async def chat_with_document(request: ChatRequest):
    """RAG endpoint — retrieve relevant chunks then answer with an LLM.

    Supports multi-turn conversation: pass `conversation_history` with all
    prior user/assistant messages so the LLM can refer back to earlier turns.
    """
    if request.document_id not in documents_store:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        store = get_vector_store(request.document_id)
        retriever = store.as_retriever(search_kwargs={"k": 4})
        relevant_docs = retriever.invoke(request.message)
        context = "\n\n".join(doc.page_content for doc in relevant_docs)

        # Build LangChain message objects from the conversation history.
        # Keep at most the last 20 messages (10 full turns) to stay within
        # context limits while still giving the model enough memory.
        history_messages = []
        for msg in request.conversation_history[-20:]:
            if msg.role == "user":
                history_messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                history_messages.append(AIMessage(content=msg.content))

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a precise document-analysis assistant. "
                    "Answer the user's question using ONLY the document context provided below. "
                    "When the user refers to previous answers or follow-up questions, "
                    "use the conversation history to understand what they mean. "
                    "If the answer is not in the context, say so clearly.\n\n"
                    "Document Context:\n{context}",
                ),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{question}"),
            ]
        )

        llm = get_llm(request.mode)
        chain = prompt | llm
        result = chain.invoke(
            {
                "context": context,
                "question": request.message,
                "history": history_messages,
            }
        )

        sources = sorted(
            {
                f"Page {doc.metadata.get('page', 1)}"
                for doc in relevant_docs
                if "page" in doc.metadata
            }
        )

        return ChatResponse(response=result.content, sources=sources)

    except Exception as exc:
        raise_clean_error(exc)


def _gather_extraction_context(
    document_id: str,
    schema_fields: List[FieldSchema],
    full_text: str,
) -> tuple[str, List[str]]:
    """Use RAG to build a focused context for extraction.

    For each requested field, we query the vector store with the field name
    and description, retrieve the top-k most relevant chunks, deduplicate,
    sort by page number, and return the combined text plus a list of source
    page references.

    For short documents (under 6000 chars) we skip RAG entirely and just
    send the full text — no point in lossy retrieval when it all fits.
    """
    if len(full_text) <= 6000:
        return full_text, []

    store = get_vector_store(document_id)
    seen_contents: set[str] = set()
    all_docs: List[Document] = []

    chunks_per_field = max(3, 8 // len(schema_fields)) if schema_fields else 4

    for field in schema_fields:
        query = f"{field.field_name} {field.description}".strip()
        if not query:
            query = field.field_name
        try:
            results = store.similarity_search(query, k=chunks_per_field)
            for doc in results:
                content_hash = doc.page_content[:200]
                if content_hash not in seen_contents:
                    seen_contents.add(content_hash)
                    all_docs.append(doc)
        except Exception as e:
            logger.warning("RAG retrieval failed for field '%s': %s", field.field_name, e)

    all_docs.sort(key=lambda d: d.metadata.get("page", 0))

    context_parts: List[str] = []
    source_pages: set[str] = set()
    for doc in all_docs:
        page = doc.metadata.get("page")
        if page:
            context_parts.append(f"[Page {page}]\n{doc.page_content}")
            source_pages.add(f"Page {page}")
        else:
            context_parts.append(doc.page_content)

    context = "\n\n---\n\n".join(context_parts)
    sources = sorted(source_pages, key=lambda s: int(s.split()[-1]))
    return context, sources


@app.post("/extract")
async def extract_data(request: ExtractRequest):
    """IDP endpoint — RAG-powered structured extraction via Instructor.

    Uses the vector store to retrieve only the document sections relevant
    to the requested fields, so extraction works on documents of any length.
    """
    if request.document_id not in documents_store:
        raise HTTPException(status_code=404, detail="Document not found.")

    doc = documents_store[request.document_id]
    full_text = doc["full_text"]

    # Build dynamic model from user schema
    field_defs: Dict[str, Any] = {}
    for f in request.schema_fields:
        desc = f.description or f"Extract the {f.field_name}"
        if f.data_type == "Number":
            field_defs[f.field_name] = (
                Optional[float],
                Field(None, description=desc),
            )
        elif f.data_type == "Date":
            field_defs[f.field_name] = (
                Optional[str],
                Field(None, description=desc + " (ISO-8601 date)"),
            )
        elif f.data_type == "List":
            field_defs[f.field_name] = (
                Optional[List[str]],
                Field(default_factory=list, description=desc),
            )
        else:  # Text
            field_defs[f.field_name] = (
                Optional[str],
                Field(None, description=desc),
            )

    DynamicModel = create_model("ExtractedData", **field_defs)

    context, sources = _gather_extraction_context(
        request.document_id, request.schema_fields, full_text,
    )

    extraction_prompt = (
        "You are a precise document data-extraction assistant.\n"
        "Extract the following structured information from the document sections below.\n"
        "Return ONLY the requested fields with accurate values found in the text.\n"
        "If a value is not present in the provided context, return null for that field.\n\n"
        f"Document sections:\n{context}"
    )

    try:
        if request.model_choice == "cloud":
            if not GOOGLE_API_KEY:
                raise HTTPException(
                    status_code=400,
                    detail="GOOGLE_API_KEY is not configured.",
                )

            last_exc = None
            for attempt in range(3):
                try:
                    model = genai.GenerativeModel(model_name=GOOGLE_MODEL)
                    client = instructor.from_gemini(
                        client=model,
                        mode=instructor.Mode.GEMINI_JSON,
                    )
                    result = client.chat.completions.create(
                        messages=[{"role": "user", "content": extraction_prompt}],
                        response_model=DynamicModel,
                        max_retries=1,
                    )
                    return {
                        "status": "success",
                        "data": result.model_dump(),
                        "sources": sources,
                    }
                except Exception as e:
                    last_exc = e
                    err_str = str(e)
                    if "429" in err_str or "quota" in err_str.lower():
                        wait = 20 * (attempt + 1)
                        logger.warning(
                            "Rate limited (attempt %d/3), waiting %ds...",
                            attempt + 1, wait,
                        )
                        await asyncio.sleep(wait)
                        continue
                    raise
            raise last_exc  # type: ignore[misc]
        else:
            client = instructor.from_openai(
                OpenAI(
                    base_url=f"{OLLAMA_BASE_URL}/v1",
                    api_key="ollama",
                ),
                mode=instructor.Mode.JSON,
            )
            result = client.chat.completions.create(
                model="qwen2.5:32b",
                messages=[{"role": "user", "content": extraction_prompt}],
                response_model=DynamicModel,
                max_retries=2,
            )
            return {
                "status": "success",
                "data": result.model_dump(),
                "sources": sources,
            }

    except HTTPException:
        raise
    except Exception as exc:
        raise_clean_error(exc)


@app.get("/documents", response_model=List[DocumentInfo])
async def list_documents():
    """Return all indexed documents."""
    return [
        DocumentInfo(
            document_id=did,
            filename=info["filename"],
            page_count=info["page_count"],
            status=info["status"],
        )
        for did, info in documents_store.items()
    ]
