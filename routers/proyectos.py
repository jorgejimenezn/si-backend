import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.database import ingestions_collection, projects_collection
from app.dependencies import get_current_user, require_admin
from app.rag_client import RagApiError, delete_project_index, get_project_sources
from app.schemas import (
    IngestionOut,
    ProjectCreate,
    ProjectIndexDeleteOut,
    ProjectOut,
    ProjectSourcesOut,
    ProjectUpdate,
)

router = APIRouter(prefix="/api/v1/projects", tags=["Proyectos"])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "proyecto"


def _project_to_out(doc: dict) -> ProjectOut:
    return ProjectOut(
        project_id=doc["project_id"],
        name=doc["name"],
        description=doc.get("description"),
        created_by=doc["created_by"],
        created_at=doc["created_at"],
    )


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate, current_user: dict = Depends(require_admin)):
    """Crear un proyecto en el catálogo. Solo un admin puede hacerlo.
    Los usuarios regulares solo pueden listar y elegir uno ya existente."""
    project_id = payload.project_id.strip() if payload.project_id else _slugify(payload.name)

    doc = {
        "project_id": project_id,
        "name": payload.name,
        "description": payload.description,
        "created_by": str(current_user["_id"]),
        "created_at": datetime.now(timezone.utc),
    }
    try:
        await projects_collection.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Ya existe un proyecto con project_id='{project_id}'"
        )

    return _project_to_out(doc)


@router.get("", response_model=list[ProjectOut])
async def list_projects(current_user: dict = Depends(get_current_user)):
    """Cualquier usuario autenticado puede ver el catálogo de proyectos y elegir uno
    para preguntarle — esto es lo único que necesita un usuario regular."""
    cursor = projects_collection.find({}).sort("created_at", -1)
    docs = await cursor.to_list(length=None)
    return [_project_to_out(d) for d in docs]


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: str, current_user: dict = Depends(get_current_user)):
    doc = await projects_collection.find_one({"project_id": project_id})
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proyecto no encontrado")
    return _project_to_out(doc)


@router.get("/{project_id}/sources", response_model=ProjectSourcesOut)
async def get_sources(project_id: str, current_user: dict = Depends(get_current_user)):
    """Todo lo indexado en el proyecto (repos con sus ramas/commits, documentos) con
    conteo de fragmentos — lo que el frontend usa para llenar los selectores de
    alcance de /query (branches, document, commit). Abierto a cualquier usuario
    autenticado: a diferencia de /ingestions (quien/cuando se cargo, admin-only),
    esto es lo que YA hay para preguntar, no un registro de auditoria."""
    project = await projects_collection.find_one({"project_id": project_id})
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proyecto no encontrado")

    try:
        result = await get_project_sources(project_id)
    except RagApiError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    return ProjectSourcesOut(**result)


@router.get("/{project_id}/ingestions", response_model=list[IngestionOut])
async def list_project_ingestions(project_id: str, current_user: dict = Depends(require_admin)):
    """Historial de que se ha indexado en un proyecto (documentos y repos), mas
    reciente primero. Para el panel de administracion de proyectos. Solo admin."""
    project = await projects_collection.find_one({"project_id": project_id})
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proyecto no encontrado")

    cursor = ingestions_collection.find({"project_id": project_id}).sort("created_at", -1)
    docs = await cursor.to_list(length=None)
    return [IngestionOut(**d) for d in docs]


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: str, payload: ProjectUpdate, current_user: dict = Depends(require_admin)
):
    """Administrar (editar nombre/descripción) — solo admin."""
    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No enviaste nada para actualizar")

    doc = await projects_collection.find_one_and_update(
        {"project_id": project_id},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proyecto no encontrado")
    return _project_to_out(doc)


@router.delete("/{project_id}/index", response_model=ProjectIndexDeleteOut)
async def delete_project_index_endpoint(
    project_id: str, current_user: dict = Depends(require_admin)
):
    """Vacía el índice del RAG (fragmentos y embeddings) de un proyecto, sin borrarlo
    del catálogo — útil para re-indexar desde cero sin perder el project_id/nombre.
    Solo admin."""
    project = await projects_collection.find_one({"project_id": project_id})
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proyecto no encontrado")

    try:
        result = await delete_project_index(project_id)
    except RagApiError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    return ProjectIndexDeleteOut(**result)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: str, current_user: dict = Depends(require_admin)):
    """Solo admin. Borra el proyecto del catálogo del backend y, de paso, intenta
    vaciar su índice en el RAG (fragmentos/embeddings) para no dejar basura huérfana.
    Si el RAG no responde, igual se borra del catálogo (best-effort)."""
    result = await projects_collection.delete_one({"project_id": project_id})
    if result.deleted_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proyecto no encontrado")

    try:
        await delete_project_index(project_id)
    except RagApiError:
        pass  # el catálogo ya se borró; el índice huérfano no es accesible vía /query

    await ingestions_collection.delete_many({"project_id": project_id})

    return None
