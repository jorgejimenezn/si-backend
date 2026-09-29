from fastapi import APIRouter, Depends

from app.database import (
    conversations_collection,
    messages_collection,
    projects_collection,
    users_collection,
)
from app.dependencies import get_current_user
from app.rag_client import RagApiError, get_rag_health, get_rag_metrics
from app.schemas import BackendStatsOut, RagHealthOut, RagMetricsOut, StatusOut

router = APIRouter(prefix="/api/v1/status", tags=["Estado y observabilidad"])


async def _backend_stats() -> BackendStatsOut:
    total_users = await users_collection.count_documents({})
    total_projects = await projects_collection.count_documents({})
    total_conversations = await conversations_collection.count_documents({})

    total_queries = await messages_collection.count_documents({})
    avg_result = await messages_collection.aggregate(
        [
            {"$match": {"response_time_ms": {"$ne": None}}},
            {"$group": {"_id": None, "avg": {"$avg": "$response_time_ms"}}},
        ]
    ).to_list(length=1)
    average_response_time_ms = avg_result[0]["avg"] if avg_result else None

    return BackendStatsOut(
        total_users=total_users,
        total_projects=total_projects,
        total_conversations=total_conversations,
        total_queries=total_queries,
        average_response_time_ms=average_response_time_ms,
    )


@router.get("", response_model=StatusOut)
async def get_status(current_user: dict = Depends(get_current_user)):
    """Observabilidad (punto 17 del alcance): estado del RAG y sus dependencias
    (Postgres/pgvector, embeddings, modelo), métricas de consultas del RAG, y
    estadísticas propias del backend (usuarios, proyectos, conversaciones,
    consultas registradas y su tiempo de respuesta promedio).

    Si el RAG no responde, no se cae todo el endpoint: se informa el error en
    rag_error / rag_metrics_error y igual se devuelven las estadísticas del
    backend, para que el dashboard siga mostrando algo."""
    rag: RagHealthOut | None = None
    rag_error: str | None = None
    try:
        rag = RagHealthOut(**await get_rag_health())
    except RagApiError as exc:
        rag_error = exc.detail

    rag_metrics: RagMetricsOut | None = None
    rag_metrics_error: str | None = None
    try:
        rag_metrics = RagMetricsOut(**await get_rag_metrics())
    except RagApiError as exc:
        rag_metrics_error = exc.detail

    return StatusOut(
        rag=rag,
        rag_error=rag_error,
        rag_metrics=rag_metrics,
        rag_metrics_error=rag_metrics_error,
        backend=await _backend_stats(),
    )
