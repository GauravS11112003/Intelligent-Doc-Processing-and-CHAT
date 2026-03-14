from pydantic import BaseModel
from typing import List

class DocumentInfo(BaseModel):
    document_id: str
    filename: str
    page_count: int
    status: str

class ConversationMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    document_id: str
    message: str
    mode: str = "local"  # "local" | "cloud"
    conversation_history: List[ConversationMessage] = []

class ChatResponse(BaseModel):
    response: str
    sources: List[str] = []

class FieldSchema(BaseModel):
    field_name: str
    data_type: str  # Text | Number | Date | List
    description: str = ""

class ExtractRequest(BaseModel):
    document_id: str
    schema_fields: List[FieldSchema]
    model_choice: str = "local"  # "local" | "cloud"
