from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.config import settings
from app.dependencies import require_admin
from app.database import ingestions_collection, projects_collection

router = APIRouter(prefix="/api/v1/repositories", tags=["Repositorios"])


class BranchesRequest(BaseModel):
    repository_url: str


class IngestRequest(BaseModel):
    project_id: str
    repository_url: str
    branches: list[str]


async def _call_rag(path: str, payload: dict, timeout: float = 60.0) -> dict:
    url = f"{settings.rag_api_base_url}{path}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload)
    except httpx.RequestError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"No se pudo contactar al servicio RAG: {exc}"
        ) from exc
    if response.status_code != 200:
        raise HTTPException(response.status_code, f"El RAG respondió con error: {response.text}")
    return response.json()


@router.post("/branches")
async def list_branches(payload: BranchesRequest, current_user: dict = Depends(require_admin)):
    """Solo un admin puede explorar ramas (paso previo a indexar un repo)."""
    return await _call_rag("/api/v1/repositories/branches", payload.model_dump())


@router.post("/ingest")
async def ingest_repository(payload: IngestRequest, current_user: dict = Depends(require_admin)):
    """Indexar un repo completo puede tardar mas que una consulta normal.
    Solo un admin puede indexar repositorios."""
    project = await projects_collection.find_one({"project_id": payload.project_id})
    if project is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Ese project_id no existe. Créalo primero con POST /api/v1/projects.",
        )
    result = await _call_rag("/api/v1/repositories/ingest", payload.model_dump(), timeout=180.0)

    await ingestions_collection.insert_one(
        {
            "project_id": payload.project_id,
            "type": "repository",
            "source": payload.repository_url,
            "branches": payload.branches,
            "files_processed": result.get("total_files"),
            "chunks_created": result.get("total_chunks"),
            "created_by": str(current_user["_id"]),
            "created_at": datetime.now(timezone.utc),
        }
    )

    return result
