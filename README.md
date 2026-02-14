# Hybrid RAG Chatbot — Company Regulations

RAG chatbot over your PDF (e.g. company regulations). Choose a **local** LLM (Ollama) or **cloud** LLM (Google Gemini); embeddings and vector store stay local.

---

## Prerequisites

### 1. Python 3.10+

```bash
python --version
```

### 2. Install dependencies

```bash
cd c:\Projects\chatACU
pip install -r requirements.txt
```

### 3. Tesseract OCR (for scanned document support)

**Required for scanned PDFs** (image-based documents without extractable text).

**Download & Install:**
- Windows: https://github.com/UB-Mannheim/tesseract/wiki
  - Direct link: https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.3.3.20231005.exe
  - Install to default location: `C:\Program Files\Tesseract-OCR\`
  - Installer should add to PATH automatically

**Verify installation:**
```powershell
tesseract --version
```

If the command fails, manually add `C:\Program Files\Tesseract-OCR` to your PATH. See **`INSTALL_OCR.md`** for detailed instructions.

### 4. Ollama (for Local / Privacy mode and for embeddings)

- **Install**: [ollama.com](https://ollama.com) — download and install Ollama.
- **Run Ollama**: ensure the Ollama app is running (required for both chat and embeddings).

Pull the models used by the app. On Windows, if `ollama` is not on PATH, use the full path:

**PowerShell (Windows, if `ollama` is not on PATH):**

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" pull deepseek-r1:8b
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" pull nomic-embed-text
```

**Otherwise (bash / or when `ollama` is on PATH):**

```bash
ollama pull deepseek-r1:8b
ollama pull nomic-embed-text
```

Optional check:

```bash
ollama list
```

You should see `deepseek-r1:8b` and `nomic-embed-text`.

**Local model choice** — The app uses **`deepseek-r1:8b`** by default: strong reasoning, ~5GB, 128K context, MIT license. If you have more VRAM and want higher quality, you can switch to a larger model by changing `OLLAMA_MODEL` in `app.py` and pulling it:

| Model               | Size (approx) | Use when                          |
|---------------------|---------------|-----------------------------------|
| `deepseek-r1:8b`    | ~5 GB         | Default; good balance (current)   |
| `deepseek-r1:14b`   | ~9 GB         | Better reasoning, 16GB+ VRAM      |
| `deepseek-r1:32b`   | ~20 GB        | Best local reasoning, 24GB+ VRAM  |
| `llama3.1:70b`      | ~40 GB        | Top generalist; needs 48GB+ VRAM  |

Example for 14B: `ollama pull deepseek-r1:14b`, then in `app.py` set `OLLAMA_MODEL = "deepseek-r1:14b"`.

### 5. Google API key (only for Cloud / Power mode)

- Get an API key from [Google AI Studio](https://aistudio.google.com/apikey).
- Either set it in the app sidebar when "Cloud (Power Mode)" is selected, or set the env var:

```bash
set GOOGLE_API_KEY=your_key_here
```

---

## Run the app

```bash
streamlit run app.py
```

Then: upload a PDF in the sidebar, pick **Local** or **Cloud**, and ask questions.
