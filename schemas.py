from pydantic import BaseModel, EmailStr, Field
from datetime import datetime


class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserOut(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int  # inactividad, no vida total del token
    user: UserOut


class QueryRequest(BaseModel):
    project_id: str
    question: str = Field(..., min_length=1)
    branches: list[str] = Field(default_factory=list)
    conversation_id: str | None = Field(
        default=None, description="Si se omite, se crea una conversación nueva."
    )


class SourceOut(BaseModel):
    chunk_id: int | None = None
    source_type: str | None = None
    source: str | None = None
    repository: str | None = None
    document: str | None = None
    branch: str | None = None
    commit: str | None = None
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    page: int | None = None
    tab: str | None = None
    artifact_type: str | None = None
    score: float | None = None


class QueryResponse(BaseModel):
    conversation_id: str
    project_id: str
    question: str
    answer: str
    sources: list[SourceOut]
    context_chunks_used: int | None = None
    provider: str | None = None
    model: str | None = None
    response_time_ms: float | None = None


class RagHealthOut(BaseModel):
    status: str | None = None
    database: str | None = None
    vector_store: str | None = None
    embedding_service: str | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    llm_service: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None


class RagMetricsOut(BaseModel):
    total_queries: int | None = None
    successful_queries: int | None = None
    failed_queries: int | None = None
    average_response_time_ms: float | None = None


class BackendStatsOut(BaseModel):
    total_users: int
    total_projects: int
    total_conversations: int
    total_queries: int
    average_response_time_ms: float | None = None


class StatusOut(BaseModel):
    rag: RagHealthOut | None = None
    rag_error: str | None = None
    rag_metrics: RagMetricsOut | None = None
    rag_metrics_error: str | None = None
    backend: BackendStatsOut


class MessageOut(BaseModel):
    question: str
    answer: str
    sources: list[SourceOut]
    created_at: datetime


class ConversationOut(BaseModel):
    conversation_id: str
    project_id: str
    created_at: datetime
    updated_at: datetime


class ProjectCreate(BaseModel):
    project_id: str | None = Field(
        default=None,
        min_length=2,
        max_length=80,
        description="Identificador que se usará al preguntar (ej. 'demo-final-1'). "
        "Si se omite, se genera a partir del nombre.",
    )
    name: str = Field(..., min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class ProjectOut(BaseModel):
    project_id: str
    name: str
    description: str | None = None
    created_by: str
    created_at: datetime


class ProjectIndexDeleteOut(BaseModel):
    project_id: str
    deleted_chunks: int


class IngestionOut(BaseModel):
    type: str  # "document" | "repository"
    source: str  # nombres de archivo separados por coma, o la repository_url
    branches: list[str] | None = None
    files_processed: int | None = None
    chunks_created: int | None = None
    created_by: str
    created_at: datetime


class ActivityEventOut(BaseModel):
    type: str  # "project_created" | "document" | "repository"
    # project_id/project_name/source solo se llenan para un admin; un usuario
    # regular solo recibe el tipo de evento y la fecha (aviso genérico, sin
    # detalle a consultar).
    project_id: str | None = None
    project_name: str | None = None
    source: str | None = None  # nombre(s) de archivo o repository_url; None para project_created
    created_at: datetime


class CompareRequest(BaseModel):
    project_id: str
    repository_url: str
    branch_a: str
    branch_b: str
    question: str = Field(
        default="¿Qué diferencias relevantes existen entre estas dos ramas?", min_length=1
    )


class ChangeOut(BaseModel):
    status: str | None = None
    path: str | None = None
    previous_path: str | None = None


class CompareResponse(BaseModel):
    conversation_id: str
    project_id: str
    repository: str | None = None
    branch_a: str
    branch_b: str
    question: str
    answer: str
    changes: list[ChangeOut]
    sources: list[SourceOut]
    context_chunks_used: int | None = None
    provider: str | None = None
    model: str | None = None
    response_time_ms: float | None = None
