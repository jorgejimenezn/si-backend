import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.config import settings
from app.dependencies import get_current_user

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
async def list_branches(payload: BranchesRequest, current_user: dict = Depends(get_current_user)):
    return await _call_rag("/api/v1/repositories/branches", payload.model_dump())


@router.post("/ingest")
async def ingest_repository(payload: IngestRequest, current_user: dict = Depends(get_current_user)):
    # Indexar un repo completo puede tardar mas que una consulta normal.
    return await _call_rag("/api/v1/repositories/ingest", payload.model_dump(), timeout=180.0)