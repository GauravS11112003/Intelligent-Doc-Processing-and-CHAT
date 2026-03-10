# ACU Project AI - Intelligent Document Processing (IDP) Platform

## 1. Project Overview

**ACU Project AI** is a robust **Intelligent Document Processing (IDP)** platform designed to ingest, analyze, and extract structured insights from PDF documents. It bridges the gap between static documents and actionable data by leveraging modern **Retrieval-Augmented Generation (RAG)** and **Large Language Models (LLMs)**.

The system allows users to upload PDF documents (including scanned images), chat with them in natural language, and extract specific structured data fields (like dates, invoice numbers, or names) based on a custom schema.

---

## 2. Why We Are Doing This

Traditional document processing is manual, error-prone, and slow. 
-   **Problem**: Unstructured data (PDFs, images) is hard to query and automate.
-   **Solution**: An AI-powered pipeline that "reads" documents like a human but at the speed of software.

**Key Goals:**
1.  **Automation**: Remove manual data entry by extracting structured JSON from unstructured PDFs.
2.  **Accessibility**: Allow users to "talk" to their documents to find information instantly.
3.  **Flexibility**: Support both local privacy-focused models (Ollama/Qwen) and powerful cloud models (Google Gemini).
4.  **Resilience**: Handle both digital PDFs and scanned image-based PDFs (via OCR).

---

## 3. Architecture

The project follows a modern **Client-Server** architecture, separating the heavy AI processing from the reactive user interface.

### High-Level Stack

| Component | Technology | Role |
| :--- | :--- | :--- |
| **Frontend** | **Next.js 16 (React 19)** | User Interface, State Management, Real-time updates |
| **Backend** | **FastAPI (Python)** | API Server, Orchestration, File Handling |
| **AI / LLM** | **LangChain + Ollama / Gemini** | RAG Logic, Embeddings, Inference |
| **Vector DB** | **ChromaDB** | Storing and retrieving document embeddings |
| **OCR Engine** | **PyMuPDF + Tesseract** | Extracting text from PDFs and Images |

### System Diagram

```mermaid
graph TD
    User[User] -->|Uploads PDF| FE[Next.js Frontend]
    FE -->|Streaming Upload| BE[FastAPI Backend]
    
    subgraph "Backend Processing"
        BE -->|1. Extract Text| OCR[PyMuPDF / Tesseract]
        OCR -->|Text| Chunker[Text Splitter]
        Chunker -->|Chunks| Embed[Ollama Embeddings]
        Embed -->|Vectors| DB[(ChromaDB)]
    end
    
    subgraph "RAG & Extraction"
        FE -->|Chat / Extract Query| BE
        BE -->|Query Vector| DB
        DB -->|Relevant Chunks| LLM[LLM (Ollama / Gemini)]
        LLM -->|Answer / JSON| BE
        BE -->|Response| FE
    end
```

---

## 4. How It Works (Technical Deep Dive)

### Phase 1: Ingestion & Indexing
1.  **Upload**: The user uploads a PDF. The backend accepts it via a streaming endpoint to provide real-time progress.
2.  **Text Extraction**:
    -   **Digital PDFs**: Text is extracted directly using `PyMuPDF`.
    -   **Scanned PDFs**: If text is missing or sparse, the system automatically falls back to **Tesseract OCR** to "read" the images.
    -   **Deep Scan**: An optional mode forces OCR on all embedded images to capture text inside charts or screenshots.
3.  **Chunking**: The continuous text is split into smaller, manageable "chunks" (e.g., 1000 characters) with overlap to preserve context across boundaries.
4.  **Embedding**: Each chunk is converted into a numerical vector (embedding) using a local model (`nomic-embed-text`).
5.  **Storage**: Vectors are stored in **ChromaDB**, allowing for fast semantic search later.

### Phase 2: Retrieval-Augmented Generation (RAG)
When a user asks a question:
1.  The question is embedded into the same vector space.
2.  **ChromaDB** finds the top 4 most similar chunks from the document.
3.  These chunks are passed as "context" to the LLM along with the user's question.
4.  The LLM answers the question using *only* the provided facts, reducing hallucinations.

### Phase 3: Structured Extraction
When a user defines a schema (e.g., "Invoice Number", "Date", "Total Amount"):
1.  The system performs a targeted RAG search for each field to find relevant sections of the document.
2.  It constructs a specialized prompt for the LLM using the `instructor` library.
3.  The LLM is forced to output valid **JSON** matching the defined schema.
4.  The result is returned as structured data, ready for API consumption or database entry.

---

## 5. Key Features

### 1. Hybrid AI Support
-   **Local Mode**: Runs entirely on your machine using **Ollama** (e.g., `qwen2.5`). Private, free, offline-capable.
-   **Cloud Mode**: Uses **Google Gemini 2.0 Flash**. Faster, higher reasoning capability, requires an API key.

### 2. Intelligent OCR
-   Automatically detects if a PDF is a scanned image and switches to OCR.
-   Extracts text from images embedded within digital PDFs.

### 3. Interactive UI
-   **Chat Panel**: A ChatGPT-like interface for talking to documents.
-   **Extraction Builder**: A UI to define fields (Text, Number, Date, List) and see results instantly.
-   **PDF Viewer**: Preview the document alongside the analysis.

---

## 6. Directory Structure

### `backend/` (The Brain)
-   `main.py`: The entry point. Contains all API endpoints (`/upload`, `/chat`, `/extract`).
-   `chroma_db/`: Persistent storage for vector data.
-   `temp/`: Temporary storage for uploaded files.

### `frontend/` (The Face)
-   `src/app/page.tsx`: The main dashboard.
-   `src/components/chat-panel.tsx`: Logic for the chat interface.
-   `src/components/extract-panel.tsx`: Logic for the structured data extraction.
-   `src/components/upload-zone.tsx`: Drag-and-drop file upload with progress bars.

---

## 7. Future Roadmap
-   **Multi-File Chat**: Chat across multiple uploaded documents simultaneously.
-   **Export Options**: Download extracted data as CSV or Excel.
-   **Advanced OCR**: Support for handwriting recognition and layout preservation.
-   **User Auth**: Multi-user support with private workspaces.
