from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.config import settings
from app.dependencies import require_admin
from app.database import ingestions_collection, projects_collection

router = APIRouter(prefix="/api/v1/documents", tags=["Documentos"])


@router.post("/ingest")
async def ingest_documents(
    project_id: str = Form(...),
    files: list[UploadFile] = File(...),
    current_user: dict = Depends(require_admin),
):
    """Recibe archivos del frontend y los reenvia al servicio RAG para indexarlos.
    El frontend nunca llama directo al RAG; todo pasa por este backend.
    Solo un admin puede subir documentos."""
    project = await projects_collection.find_one({"project_id": project_id})
    if project is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Ese project_id no existe. Créalo primero con POST /api/v1/projects.",
        )

    multipart_files = []
    for f in files:
        content = await f.read()
        multipart_files.append(
            ("files", (f.filename, content, f.content_type or "application/octet-stream"))
        )

    url = f"{settings.rag_api_base_url}/api/v1/documents/ingest"

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                url, data={"project_id": project_id}, files=multipart_files
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"No se pudo contactar al servicio RAG: {exc}"
        ) from exc

    if response.status_code != 200:
        raise HTTPException(
            response.status_code, f"El RAG respondió con error: {response.text}"
        )

    result = response.json()

    await ingestions_collection.insert_one(
        {
            "project_id": project_id,
            "type": "document",
            "source": ", ".join(f.filename for f in files),
            "branches": None,
            "files_processed": len(files),
            "chunks_created": result.get("total_chunks"),
            "created_by": str(current_user["_id"]),
            "created_at": datetime.now(timezone.utc),
        }
    )

    return result
