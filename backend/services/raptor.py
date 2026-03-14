import logging
import asyncio
from typing import List, AsyncGenerator, Dict, Any
from langchain_core.documents import Document
import google.generativeai as genai

from config import GOOGLE_API_KEY, GOOGLE_MODEL

logger = logging.getLogger(__name__)

async def generate_raptor_summaries(
    chunks: List[Document],
    document_id: str,
    level: int = 1,
    max_levels: int = 3
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Recursively summarize groups of chunks to build a hierarchical tree (RAPTOR).
    Yields progress dicts: {"message": str} and finally {"result": List[Document]}
    """
    if not GOOGLE_API_KEY:
        logger.warning("No GOOGLE_API_KEY found. Skipping RAPTOR summarization.")
        yield {"result": []}
        return

    # If we have 3 or fewer chunks, we've reached the top of the tree.
    if len(chunks) <= 3 or level > max_levels:
        yield {"result": []}
        return

    # Group adjacent chunks dynamically to prevent massive rate limits on big docs
    GROUP_SIZE = max(5, (len(chunks) + 19) // 20)
    groups = [chunks[i : i + GROUP_SIZE] for i in range(0, len(chunks), GROUP_SIZE)]
    
    logger.info(f"Generating Level {level} RAPTOR summaries for {len(groups)} groups.")
    yield {"message": f"Level {level}: Summarizing {len(groups)} sections..."}

    # Process groups concurrently with a semaphore to avoid rate limits
    semaphore = asyncio.Semaphore(5)
    
    async def summarize_group(group_idx: int, group: List[Document]):
        async with semaphore:
            # We cap at 800k chars just to ensure we don't blow past Gemini's 1M limit
            text = "\n\n---\n\n".join(doc.page_content for doc in group)[:800000]
            prompt = (
                "You are an expert document summarizer.\n"
                "Please provide a comprehensive summary of the following text segments. "
                "Retain the most critical information, entities, and overall themes.\n\n"
                f"Text:\n{text}"
            )
            
            last_exc = None
            for attempt in range(3):
                try:
                    def call_gemini():
                        model = genai.GenerativeModel(model_name=GOOGLE_MODEL)
                        response = model.generate_content(prompt)
                        return response.text
                    
                    summary_text = await asyncio.to_thread(call_gemini)
                    
                    return Document(
                        page_content=summary_text,
                        metadata={
                            "source": "raptor",
                            "level": level,
                            "document_id": document_id,
                            "is_summary": True,
                            "group_idx": group_idx
                        }
                    )
                except Exception as e:
                    last_exc = e
                    # Wait and retry if error (likely rate limit or quota)
                    await asyncio.sleep(2 ** attempt)
            
            logger.warning("Failed to summarize group %d after 3 attempts: %s", group_idx, last_exc)
            return None

    tasks = [asyncio.create_task(summarize_group(i, group)) for i, group in enumerate(groups)]
    results = []
    
    for i, coro in enumerate(asyncio.as_completed(tasks)):
        res = await coro
        results.append(res)
        yield {"message": f"Level {level}: Summarized {i + 1}/{len(groups)} sections..."}
    
    valid_summaries = [r for r in results if r is not None]
    
    if not valid_summaries:
        yield {"result": []}
        return

    # Recurse on the new summaries to build the next level up
    next_level_summaries = []
    async for payload in generate_raptor_summaries(
        chunks=valid_summaries,
        document_id=document_id,
        level=level + 1,
        max_levels=max_levels
    ):
        if "result" in payload:
            next_level_summaries = payload["result"]
        else:
            yield payload

    yield {"result": valid_summaries + next_level_summaries}
