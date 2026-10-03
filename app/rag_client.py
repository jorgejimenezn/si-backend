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
    document: str | None = None,
    commit: str | None = None,
    repository: str | None = None,
    debug: bool = False,
) -> dict:
    # El RAG solo acepta UN alcance a la vez (todo el proyecto, branches,
    # document, o commit [+ repository]); se manda solo lo que venga con
    # contenido para no disparar su validacion de combinacion invalida
    # (422) cuando el cliente simplemente dejo branches en su default [].
    payload: dict = {
        "project_id": project_id,
        "question": question,
        "conversation_history": conversation_history,
        "debug": debug,
    }
    if branches:
        payload["branches"] = branches
    if document:
        payload["document"] = document
    if commit:
        payload["commit"] = commit
    if repository:
        payload["repository"] = repository

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


async def list_commits(repository_url: str, branch: str | None, limit: int) -> dict:
    """Commits recientes de una rama remota (no indexa nada, solo para elegir SHA)."""
    payload: dict = {"repository_url": repository_url, "limit": limit}
    if branch:
        payload["branch"] = branch
    url = f"{settings.rag_api_base_url}/api/v1/repositories/commits"

    try:
        # El clon es superficial pero proporcional a "limit"; en repos grandes
        # con limit alto puede tardar igual que listar ramas.
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
    except httpx.RequestError as exc:
        raise RagApiError(502, f"No se pudo contactar al servicio RAG: {exc}") from exc

    if response.status_code != 200:
        raise RagApiError(response.status_code, f"El RAG respondió con error: {response.text}")

    return response.json()


async def ingest_commits(project_id: str, repository_url: str, commits: list[str]) -> dict:
    """Indexa hasta 10 commits puntuales (codigo + metadata + diff) sin tocar
    otras ramas/commits ya indexados. Clona el historial completo, puede tardar
    en repos grandes."""
    payload = {
        "project_id": project_id,
        "repository_url": repository_url,
        "commits": commits,
    }
    url = f"{settings.rag_api_base_url}/api/v1/repositories/commits/ingest"

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(url, json=payload)
    except httpx.RequestError as exc:
        raise RagApiError(502, f"No se pudo contactar al servicio RAG: {exc}") from exc

    if response.status_code != 200:
        raise RagApiError(response.status_code, f"El RAG respondió con error: {response.text}")

    return response.json()


async def get_project_sources(project_id: str) -> dict:
    """Todo lo indexado en un proyecto (repos+ramas+commits, documentos) con sus
    conteos de fragmentos. Un proyecto sin indice da 200 con listas vacias, no 404."""
    url = f"{settings.rag_api_base_url}/api/v1/projects/{project_id}/sources"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
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
