from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.database import users_collection
from app.dependencies import get_current_user, require_admin
from app.schemas import UserCreate, UserOut
from app.security import hash_password

router = APIRouter(prefix="/api/v1/users", tags=["Usuarios"])


def _user_to_out(user: dict) -> UserOut:
    return UserOut(
        id=str(user["_id"]),
        name=user["name"],
        email=user["email"],
        role=user.get("role", "user"),
        created_at=user.get("created_at"),
    )


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate):
    """Registro de usuario. Abierto por ahora (sin invitación) para no bloquear al frontend;
    si el proyecto requiere que solo un admin cree usuarios, se agrega Depends(get_current_user)
    y una validación de rol aquí."""
    doc = {
        "name": payload.name,
        "email": payload.email.lower(),
        "password_hash": hash_password(payload.password),
        "role": "user",
        "created_at": datetime.now(timezone.utc),
    }
    try:
        result = await users_collection.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un usuario con ese email")

    doc["_id"] = result.inserted_id
    return _user_to_out(doc)


@router.get("/me", response_model=UserOut)
async def get_me(current_user: dict = Depends(get_current_user)):
    return _user_to_out(current_user)


@router.get("", response_model=list[UserOut])
async def list_users(current_user: dict = Depends(require_admin)):
    """Listado de todos los usuarios registrados (sin password_hash). Solo admin."""
    cursor = users_collection.find({}).sort("created_at", 1)
    docs = await cursor.to_list(length=None)
    return [_user_to_out(d) for d in docs]
