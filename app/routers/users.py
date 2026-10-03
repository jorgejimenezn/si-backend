from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.database import sessions_collection, users_collection
from app.dependencies import get_current_user, require_admin
from app.schemas import UserCreate, UserOut, UserPasswordReset, UserUpdate
from app.security import hash_password

router = APIRouter(prefix="/api/v1/users", tags=["Usuarios"])


def _user_to_out(user: dict) -> UserOut:
    return UserOut(
        id=str(user["_id"]),
        name=user["name"],
        email=user["email"],
        role=user.get("role", "user"),
        active=user.get("active", True),
        created_at=user.get("created_at"),
    )


async def _get_user_or_404(user_id: str) -> dict:
    try:
        oid = ObjectId(user_id)
    except InvalidId:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    user = await users_collection.find_one({"_id": oid})
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    return user


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
        "active": True,
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


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str, payload: UserUpdate, current_user: dict = Depends(require_admin)
):
    """Cambiar rol y/o activar-desactivar un usuario. Solo admin.
    Un usuario inactivo conserva su cuenta pero no puede iniciar sesión ni usar
    una sesión ya abierta (se valida en login y en get_current_user)."""
    user = await _get_user_or_404(user_id)

    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No enviaste nada para actualizar")

    is_self = str(user["_id"]) == str(current_user["_id"])
    if is_self and updates.get("active") is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No puedes desactivar tu propia cuenta")
    if is_self and updates.get("role") == "user":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "No puedes quitarte el rol de administrador a ti mismo"
        )

    await users_collection.update_one({"_id": user["_id"]}, {"$set": updates})

    # Si se desactiva, se cierran de una vez sus sesiones activas para que el
    # cambio surta efecto aunque su token todavia no haya expirado.
    if updates.get("active") is False:
        await sessions_collection.delete_many({"user_id": str(user["_id"])})

    user.update(updates)
    return _user_to_out(user)


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_user_password(
    user_id: str, payload: UserPasswordReset, current_user: dict = Depends(require_admin)
):
    """Un admin fija una contraseña nueva para otro usuario (ej. si la olvido).
    No requiere la contraseña anterior. Cierra sus sesiones activas para que
    tenga que volver a iniciar sesion con la contraseña nueva."""
    user = await _get_user_or_404(user_id)
    await users_collection.update_one(
        {"_id": user["_id"]}, {"$set": {"password_hash": hash_password(payload.new_password)}}
    )
    await sessions_collection.delete_many({"user_id": str(user["_id"])})
    return None
