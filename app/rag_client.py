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
