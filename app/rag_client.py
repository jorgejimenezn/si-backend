import httpx

from app.config import settings


class RagApiError(Exception):
    """Se lanza cuando el RAG responde con error o no responde."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def query_rag(
    project_id: str,
    question: str,
    conversation_history: list[dict],
    branches: list[str] | None = None,
) -> dict:
    payload = {
        "project_id": project_id,
        "question": question,
        "branches": branches or [],
        "conversation_history": conversation_history,
        "debug": False,
    }
    url = f"{settings.rag_api_base_url}/api/v1/query"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
    except httpx.RequestError as exc:
        raise RagApiError(502, f"No se pudo contactar al servicio RAG: {exc}") from exc

    if response.status_code != 200:
        raise RagApiError(
            response.status_code,
            f"El RAG respondió con error: {response.text}",
        )

    return response.json()


async def compare_branches(
    project_id: str,
    repository_url: str,
    branch_a: str,
    branch_b: str,
    question: str,
) -> dict:
    """Diff real entre dos ramas + explicación del RAG con evidencia de archivos."""
    payload = {
        "project_id": project_id,
        "repository_url": repository_url,
        "branch_a": branch_a,
        "branch_b": branch_b,
        "question": question,
        "debug": False,
    }
    url = f"{settings.rag_api_base_url}/api/v1/compare"

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)
    except httpx.RequestError as exc:
        raise RagApiError(502, f"No se pudo contactar al servicio RAG: {exc}") from exc

    if response.status_code != 200:
        raise RagApiError(
            response.status_code,
            f"El RAG respondió con error: {response.text}",
        )

    return response.json()


async def get_rag_health() -> dict:
    """Estado del RAG: Postgres/pgvector, servicio de embeddings y del modelo."""
    url = f"{settings.rag_api_base_url}/api/v1/health"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
    except httpx.RequestError as exc:
        raise RagApiError(502, f"No se pudo contactar al servicio RAG: {exc}") from exc

    if response.status_code != 200:
        raise RagApiError(response.status_code, f"El RAG respondió con error: {response.text}")

    return response.json()


async def get_rag_metrics() -> dict:
    """Metricas acumuladas de consultas del RAG (para observabilidad)."""
    url = f"{settings.rag_api_base_url}/api/v1/metrics"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
    except httpx.RequestError as exc:
        raise RagApiError(502, f"No se pudo contactar al servicio RAG: {exc}") from exc

    if response.status_code != 200:
        raise RagApiError(response.status_code, f"El RAG respondió con error: {response.text}")

    return response.json()


async def delete_project_index(project_id: str) -> dict:
    """Elimina del RAG todos los fragmentos y embeddings de un project_id.
    No borra el proyecto del catalogo del backend (eso lo maneja proyectos.py aparte)."""
    url = f"{settings.rag_api_base_url}/api/v1/projects/{project_id}/index"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.delete(url)
    except httpx.RequestError as exc:
        raise RagApiError(502, f"No se pudo contactar al servicio RAG: {exc}") from exc

    if response.status_code != 200:
        raise RagApiError(
            response.status_code,
            f"El RAG respondió con error: {response.text}",
        )

    return response.json()
