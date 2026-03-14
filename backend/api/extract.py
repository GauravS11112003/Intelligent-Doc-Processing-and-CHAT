import logging
import asyncio
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import Field, create_model

import instructor
from openai import OpenAI
import google.generativeai as genai

from models import ExtractRequest
from dependencies import documents_store, get_vector_store, raise_clean_error
from config import GOOGLE_API_KEY, GOOGLE_MODEL, OLLAMA_BASE_URL
from services.rag import _gather_extraction_context

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Extraction"])

@router.post("/extract")
async def extract_data(request: ExtractRequest):
    """IDP endpoint — RAG-powered structured extraction via Instructor.

    Uses the vector store to retrieve only the document sections relevant
    to the requested fields, so extraction works on documents of any length.
    """
    if request.document_id not in documents_store:
        raise HTTPException(status_code=404, detail="Document not found.")

    doc = documents_store[request.document_id]
    full_text = doc["full_text"]

    field_defs: Dict[str, Any] = {}
    for f in request.schema_fields:
        desc = f.description or f"Extract the {f.field_name}"
        if f.data_type == "Number":
            field_defs[f.field_name] = (Optional[float], Field(None, description=desc))
        elif f.data_type == "Date":
            field_defs[f.field_name] = (Optional[str], Field(None, description=desc + " (ISO-8601 date)"))
        elif f.data_type == "List":
            field_defs[f.field_name] = (Optional[List[str]], Field(default_factory=list, description=desc))
        else:  # Text
            field_defs[f.field_name] = (Optional[str], Field(None, description=desc))

    DynamicModel = create_model("ExtractedData", **field_defs)

    context, sources = _gather_extraction_context(
        request.document_id, request.schema_fields, full_text, get_vector_store
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
                model="qwen3:4b",
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
