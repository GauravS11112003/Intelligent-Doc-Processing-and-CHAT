import logging
from typing import Dict, Optional
from fastapi import HTTPException
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_chroma import Chroma
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
import google.generativeai as genai

from config import (
    CHROMA_DIR,
    OLLAMA_EMBED_MODEL,
    OLLAMA_BASE_URL,
    GOOGLE_API_KEY,
    GOOGLE_MODEL,
)

logger = logging.getLogger(__name__)

# Configure Google GenAI if key is present
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
_chroma_client: Optional[chromadb.PersistentClient] = None

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
        model="qwen3:4b",
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
