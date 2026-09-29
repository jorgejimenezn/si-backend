import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import conversations_collection, messages_collection, projects_collection
from app.dependencies import get_current_user
from app.rag_client import RagApiError, query_rag
from app.schemas import (
    ConversationOut,
    MessageOut,
    QueryRequest,
    QueryResponse,
    SourceOut,
)

router = APIRouter(prefix="/api/v1", tags=["Consultas (orquestador RAG)"])

MAX_HISTORY_TURNS = 10  # cuantos turnos previos se le mandan al RAG como contexto


async def _load_history(conversation_id: str) -> list[dict]:
    cursor = (
        messages_collection.find({"conversation_id": conversation_id})
        .sort("created_at", 1)
        .limit(MAX_HISTORY_TURNS)
    )
    docs = await cursor.to_list(length=None)
    return [{"user": d["question"], "assistant": d["answer"]} for d in docs]


async def _get_or_create_conversation(
    conversation_id: str | None, user_id: str, project_id: str
) -> str:
    now = datetime.now(timezone.utc)

    if conversation_id:
        conv = await conversations_collection.find_one(
            {"conversation_id": conversation_id, "user_id": user_id}
        )
        if conv is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "Conversación no encontrada (o no te pertenece)",
            )
        await conversations_collection.update_one(
            {"conversation_id": conversation_id}, {"$set": {"updated_at": now}}
        )
        return conversation_id

    new_id = str(uuid.uuid4())
    await conversations_collection.insert_one(
        {
            "conversation_id": new_id,
            "user_id": user_id,
            "project_id": project_id,
            "created_at": now,
            "updated_at": now,
        }
    )
    return new_id


@router.post("/query", response_model=QueryResponse)
async def query(payload: QueryRequest, current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["_id"])

    project = await projects_collection.find_one({"project_id": payload.project_id})
    if project is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Ese project_id no existe en el catálogo. Pide la lista con GET /api/v1/projects.",
        )

    conversation_id = await _get_or_create_conversation(
        payload.conversation_id, user_id, payload.project_id
    )
    history = await _load_history(conversation_id)

    try:
        rag_response = await query_rag(
            project_id=payload.project_id,
            question=payload.question,
            conversation_history=history,
            branches=payload.branches,
        )
    except RagApiError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, exc.detail) from exc

    now = datetime.now(timezone.utc)
    await messages_collection.insert_one(
        {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "project_id": payload.project_id,
            "question": payload.question,
            "answer": rag_response.get("answer", ""),
            "sources": rag_response.get("sources", []),
            "context_chunks_used": rag_response.get("context_chunks_used"),
            "provider": rag_response.get("provider"),
            "model": rag_response.get("model"),
            "response_time_ms": rag_response.get("response_time_ms"),
            "created_at": now,
        }
    )

    return QueryResponse(
        conversation_id=conversation_id,
        project_id=payload.project_id,
        question=payload.question,
        answer=rag_response.get("answer", ""),
        sources=[SourceOut(**s) for s in rag_response.get("sources", [])],
        context_chunks_used=rag_response.get("context_chunks_used"),
        provider=rag_response.get("provider"),
        model=rag_response.get("model"),
        response_time_ms=rag_response.get("response_time_ms"),
    )


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    project_id: str | None = None, current_user: dict = Depends(get_current_user)
):
    query_filter = {"user_id": str(current_user["_id"])}
    if project_id:
        query_filter["project_id"] = project_id

    cursor = conversations_collection.find(query_filter).sort("updated_at", -1)
    docs = await cursor.to_list(length=None)
    return [ConversationOut(**d) for d in docs]


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def get_conversation_messages(
    conversation_id: str, current_user: dict = Depends(get_current_user)
):
    conv = await conversations_collection.find_one(
        {"conversation_id": conversation_id, "user_id": str(current_user["_id"])}
    )
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversación no encontrada")

    cursor = messages_collection.find({"conversation_id": conversation_id}).sort(
        "created_at", 1
    )
    docs = await cursor.to_list(length=None)
    return [
        MessageOut(
            question=d["question"],
            answer=d["answer"],
            sources=[SourceOut(**s) for s in d.get("sources", [])],
            created_at=d["created_at"],
        )
        for d in docs
    ]
