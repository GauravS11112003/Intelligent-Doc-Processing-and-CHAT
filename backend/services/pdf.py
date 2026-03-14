import logging
import io
from typing import List, Generator
from langchain_core.documents import Document
import fitz
from PIL import Image
import pytesseract

from config import TESSERACT_AVAILABLE

logger = logging.getLogger(__name__)

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
