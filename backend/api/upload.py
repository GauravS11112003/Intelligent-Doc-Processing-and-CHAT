import uuid
import shutil
import json
import asyncio
import logging
from typing import AsyncGenerator
from fastapi import APIRouter, UploadFile, File, Query, HTTPException
from fastapi.responses import StreamingResponse
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

from models import DocumentInfo
from dependencies import get_chroma_client, get_embeddings, documents_store
from config import TEMP_DIR, CHUNK_SIZE, CHUNK_OVERLAP, TESSERACT_AVAILABLE
from services.pdf import extract_text_from_pdf, ocr_embedded_images

import fitz
from PIL import Image
import pytesseract
from langchain_core.documents import Document

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Upload"])

@router.post("/upload", response_model=DocumentInfo)
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


@router.post("/upload-stream")
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
            yield f"data: {json.dumps({'stage': 'starting', 'message': 'Starting document processing...', 'progress': 0})}\n\n"
            await asyncio.sleep(0)  # Yield control

            pages: list[Document] = []
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
                    # In a streaming endpoint, use to_thread so we don't block SSE yielding
                    image_texts = await asyncio.to_thread(ocr_embedded_images, page, pdf_doc)
                    ocr_image_count = len(image_texts)
                    used_ocr = ocr_image_count > 0
                    parts = ([native_text] if native_text else []) + image_texts
                    text = "\n\n".join(parts)
                elif len(native_text) < 50 and TESSERACT_AVAILABLE:
                    try:
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        
                        def do_ocr(image):
                            return pytesseract.image_to_string(image, lang="eng", config="--psm 6 --oem 3")
                            
                        text = await asyncio.to_thread(do_ocr, img)
                        text = text.strip()
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
            
            # Phase 2.5: RAPTOR Summarization
            yield f"data: {json.dumps({'stage': 'chunking', 'message': f'Created {len(chunks)} raw chunks. Generating RAPTOR summaries...', 'progress': 53})}\n\n"
            await asyncio.sleep(0)
            
            from services.raptor import generate_raptor_summaries
            raptor_summaries = []
            async for payload in generate_raptor_summaries(chunks, document_id):
                if "result" in payload:
                    raptor_summaries = payload["result"]
                else:
                    msg = payload.get("message", "Generating RAPTOR summaries...")
                    yield f"data: {json.dumps({'stage': 'chunking', 'message': msg, 'progress': 53})}\n\n"
                    await asyncio.sleep(0)
            
            if raptor_summaries:
                chunks.extend(raptor_summaries)

            total_chunks = len(chunks)
            yield f"data: {json.dumps({'stage': 'embedding', 'message': f'Total {total_chunks} chunks (including RAPTOR nodes), embedding...', 'progress': 55, 'total_chunks': total_chunks})}\n\n"
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

                # Generate embeddings for this batch in a background thread
                batch_embeddings = await asyncio.to_thread(embeddings.embed_documents, batch_texts)

                # Add to collection in a background thread
                def add_to_collection():
                    collection.add(
                        ids=batch_ids,
                        embeddings=batch_embeddings,
                        documents=batch_texts,
                        metadatas=batch_metadatas,
                    )
                await asyncio.to_thread(add_to_collection)

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
