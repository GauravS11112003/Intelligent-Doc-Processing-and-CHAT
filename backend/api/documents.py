from typing import List
from fastapi import APIRouter
from models import DocumentInfo
from dependencies import documents_store

router = APIRouter(tags=["Documents"])

@router.get("/documents", response_model=List[DocumentInfo])
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
