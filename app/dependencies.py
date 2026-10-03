from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from bson import ObjectId

from app.config import settings
from app.database import sessions_collection, users_collection
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta el token de autenticación")

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado")

    session_id = payload.get("session_id")
    user_id = payload.get("sub")

    session = await sessions_collection.find_one({"session_id": session_id})
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión no encontrada, inicia sesión de nuevo")

    last_activity = session["last_activity"]
    if last_activity.tzinfo is None:
        last_activity = last_activity.replace(tzinfo=timezone.utc)

    inactive_minutes = (datetime.now(timezone.utc) - last_activity).total_seconds() / 60
    if inactive_minutes > settings.session_inactivity_minutes:
        await sessions_collection.delete_one({"session_id": session_id})
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            f"Sesión expirada por inactividad ({settings.session_inactivity_minutes} min). Inicia sesión de nuevo.",
        )

    # Sesion activa: actualizamos last_activity (sliding expiration)
    await sessions_collection.update_one(
        {"session_id": session_id},
        {"$set": {"last_activity": datetime.now(timezone.utc)}},
    )

    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario no encontrado")

    if not user.get("active", True):
        await sessions_collection.delete_one({"session_id": session_id})
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Tu cuenta está inactiva. Contacta a un administrador."
        )

    return user


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Dependencia para endpoints solo-admin: crear/administrar proyectos,
    subir documentos y repositorios. Por ahora el rol se asigna a mano en Mongo
    (users_collection.role = "admin"); no hay flujo de invitación."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Esta acción requiere permisos de administrador",
        )
    return current_user
