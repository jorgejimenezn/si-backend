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
