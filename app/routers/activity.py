from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.database import ingestions_collection, projects_collection
from app.dependencies import get_current_user
from app.schemas import ActivityEventOut

router = APIRouter(prefix="/api/v1/activity", tags=["Actividad"])


@router.get("", response_model=list[ActivityEventOut])
async def list_activity(
    since: datetime | None = Query(
        default=None,
        description="Solo eventos posteriores a esta fecha (ISO 8601). Si se omite, "
        "se devuelven los ultimos eventos sin filtrar por fecha.",
    ),
    current_user: dict = Depends(get_current_user),
):
    """Feed simple de actividad reciente: proyectos creados y documentos/repos
    indexados. Abierto a cualquier usuario autenticado (no solo admin) para que
    todos se enteren de contenido nuevo sin depender de refrescar manualmente.
    Un usuario regular solo ve el tipo de evento (aviso de que algo se cargó);
    el detalle (que proyecto, que archivo/repo) queda reservado a un admin.
    Pensado para sondeo periodico desde el frontend pasando `since` = la ultima
    vez que se consultó."""
    is_admin = current_user.get("role") == "admin"

    project_filter: dict = {}
    ingestion_filter: dict = {}
    if since is not None:
        project_filter["created_at"] = {"$gt": since}
        ingestion_filter["created_at"] = {"$gt": since}

    new_projects = await projects_collection.find(project_filter).sort(
        "created_at", -1
    ).limit(50).to_list(length=None)

    new_ingestions = await ingestions_collection.find(ingestion_filter).sort(
        "created_at", -1
    ).limit(50).to_list(length=None)

    # Nombre de proyecto para cada ingesta, sin una consulta por documento.
    # Solo hace falta si el usuario es admin (un usuario regular no lo recibe).
    names: dict[str, str] = {}
    if is_admin:
        project_ids = {doc["project_id"] for doc in new_ingestions}
        if project_ids:
            async for doc in projects_collection.find({"project_id": {"$in": list(project_ids)}}):
                names[doc["project_id"]] = doc["name"]

    events: list[ActivityEventOut] = []
    for p in new_projects:
        events.append(
            ActivityEventOut(
                type="project_created",
                project_id=p["project_id"] if is_admin else None,
                project_name=p["name"] if is_admin else None,
                source=None,
                created_at=p["created_at"],
            )
        )
    for i in new_ingestions:
        events.append(
            ActivityEventOut(
                type=i["type"],
                project_id=i["project_id"] if is_admin else None,
                project_name=(names.get(i["project_id"], i["project_id"]) if is_admin else None),
                source=i.get("source") if is_admin else None,
                created_at=i["created_at"],
            )
        )

    events.sort(key=lambda e: e.created_at)
    return events
