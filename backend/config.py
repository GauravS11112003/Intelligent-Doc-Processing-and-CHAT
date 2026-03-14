import os
import logging
from pathlib import Path
from dotenv import load_dotenv

import pytesseract

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

# ---------------------------------------------------------------------------
# App Configuration
# ---------------------------------------------------------------------------
TEMP_DIR = Path("temp")
CHROMA_DIR = Path("chroma_db")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
TOP_K_CHUNKS = 4
OLLAMA_EMBED_MODEL = "nomic-embed-text"
