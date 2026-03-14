import logging
from typing import List, Dict, Any, Optional

from langchain_core.documents import Document

def _gather_extraction_context(
    document_id: str,
    schema_fields: List[Any],
    full_text: str,
    get_vector_store_fn: Any
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

    store = get_vector_store_fn(document_id)
    seen_contents: set[str] = set()
    all_docs: List[Document] = []

    chunks_per_field = max(3, 8 // len(schema_fields)) if schema_fields else 4
    logger = logging.getLogger(__name__)

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
