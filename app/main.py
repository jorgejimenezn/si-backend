from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import ensure_indexes
from app.routers import auth, query, users

app = FastAPI(
    title="Software Intelligence - Backend",
    description="API de backend: usuarios, autenticación y orquestación hacia el servicio RAG.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(auth.router)
app.include_router(query.router)


@app.on_event("startup")
async def startup():
    await ensure_indexes()


@app.get("/health", tags=["Salud"])
async def health():
    return {"status": "ok"}
