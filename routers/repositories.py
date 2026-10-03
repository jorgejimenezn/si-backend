from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.config import settings
from app.dependencies import require_admin
from app.database import ingestions_collection, projects_collection
from app.schemas import CommitsIngestRequest, CommitsRequest

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


@router.post("/commits")
async def list_commits(payload: CommitsRequest, current_user: dict = Depends(require_admin)):
    """Commits recientes de una rama remota, para elegir cuales indexar con
    /commits/ingest. No indexa nada. Solo admin (mismo criterio que /branches)."""
    # El clon es superficial (depth = limit): pedir mas commits implica
    # descargar mas historial, igual que explorar ramas.
    return await _call_rag(
        "/api/v1/repositories/commits", payload.model_dump(exclude_none=True)
    )


@router.post("/commits/ingest")
async def ingest_commits(
    payload: CommitsIngestRequest, current_user: dict = Depends(require_admin)
):
    """Indexa hasta 10 commits puntuales (codigo + metadata + diff) sin tocar
    otras ramas/commits ya indexados del proyecto. Clona el historial completo,
    puede tardar en repos grandes. Solo admin."""
    project = await projects_collection.find_one({"project_id": payload.project_id})
    if project is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Ese project_id no existe. Créalo primero con POST /api/v1/projects.",
        )
    result = await _call_rag(
        "/api/v1/repositories/commits/ingest", payload.model_dump(), timeout=180.0
    )

    await ingestions_collection.insert_one(
        {
            "project_id": payload.project_id,
            "type": "commit",
            "source": payload.repository_url,
            "commits": payload.commits,
            "files_processed": result.get("total_files"),
            "chunks_created": result.get("total_chunks"),
            "created_by": str(current_user["_id"]),
            "created_at": datetime.now(timezone.utc),
        }
    )

    return result
