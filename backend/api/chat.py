from fastapi import APIRouter, HTTPException
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

from models import ChatRequest, ChatResponse
from dependencies import documents_store, get_vector_store, get_llm, raise_clean_error

router = APIRouter(tags=["Chat"])

@router.post("/chat", response_model=ChatResponse)
async def chat_with_document(request: ChatRequest):
    """RAG endpoint — retrieve relevant chunks then answer with an LLM.

    Supports multi-turn conversation: pass `conversation_history` with all
    prior user/assistant messages so the LLM can refer back to earlier turns.
    """
    if request.document_id not in documents_store:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        store = get_vector_store(request.document_id)
        
        # Optimize context window: Less reading = faster answers for local model
        k_val = 2 if request.mode == "local" else 4
        
        try:
            # Filter by similarity: Only inject relevant chunks into context 
            retriever = store.as_retriever(
                search_type="similarity_score_threshold",
                search_kwargs={"k": k_val, "score_threshold": 0.5} 
            )
            relevant_docs = retriever.invoke(request.message)
            if not relevant_docs:  # Fallback if threshold is too strict
                relevant_docs = store.as_retriever(search_kwargs={"k": 1}).invoke(request.message)
        except Exception:
            retriever = store.as_retriever(search_kwargs={"k": k_val})
            relevant_docs = retriever.invoke(request.message)
            
        context = "\n\n".join(doc.page_content for doc in relevant_docs)

        history_messages = []
        for msg in request.conversation_history[-20:]:
            if msg.role == "user":
                history_messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                history_messages.append(AIMessage(content=msg.content))

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a precise document-analysis assistant. "
                    "Answer the user's question using ONLY the document context provided below. "
                    "When the user refers to previous answers or follow-up questions, "
                    "use the conversation history to understand what they mean. "
                    "If the answer is not in the context, say so clearly.\n\n"
                    "Document Context:\n{context}",
                ),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{question}"),
            ]
        )

        llm = get_llm(request.mode)
        chain = prompt | llm
        result = chain.invoke(
            {
                "context": context,
                "question": request.message,
                "history": history_messages,
            }
        )

        sources = sorted(
            {
                f"Page {doc.metadata.get('page', 1)}"
                for doc in relevant_docs
                if "page" in doc.metadata
            }
        )

        return ChatResponse(response=result.content, sources=sources)

    except Exception as exc:
        raise_clean_error(exc)
