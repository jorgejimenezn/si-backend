from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.database import login_history_collection, sessions_collection, users_collection
from app.schemas import LoginRequest, TokenResponse, UserOut
from app.security import create_access_token, new_session_id, verify_password
from app.security import decode_access_token
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticación"])
bearer_scheme = HTTPBearer(auto_error=False)


async def _log_attempt(request: Request, email: str, success: bool, user_id: str | None = None):
    await login_history_collection.insert_one(
        {
            "email": email.lower(),
            "user_id": user_id,
            "success": success,
            "timestamp": datetime.now(timezone.utc),
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request):
    user = await users_collection.find_one({"email": payload.email.lower()})
    if user is None or not verify_password(payload.password, user["password_hash"]):
        await _log_attempt(request, payload.email, success=False)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email o contraseña incorrectos")

    if not user.get("active", True):
        await _log_attempt(request, payload.email, success=False, user_id=str(user["_id"]))
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Tu cuenta está inactiva. Contacta a un administrador."
        )

    await _log_attempt(request, payload.email, success=True, user_id=str(user["_id"]))

    session_id = new_session_id()
    now = datetime.now(timezone.utc)
    await sessions_collection.insert_one(
        {
            "session_id": session_id,
            "user_id": str(user["_id"]),
            "created_at": now,
            "last_activity": now,
        }
    )

    token = create_access_token(user_id=str(user["_id"]), session_id=session_id)

    return TokenResponse(
        access_token=token,
        expires_in_minutes=settings.session_inactivity_minutes,
        user=UserOut(
            id=str(user["_id"]),
            name=user["name"],
            email=user["email"],
            role=user.get("role", "user"),
        ),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if credentials is None:
        return
    payload = decode_access_token(credentials.credentials)
    if payload:
        await sessions_collection.delete_one({"session_id": payload.get("session_id")})
    return


@router.get("/login-history")
async def my_login_history(current_user: dict = Depends(get_current_user), limit: int = 20):
    """Historial de logeos del usuario autenticado (mas reciente primero)."""
    cursor = (
        login_history_collection.find({"user_id": str(current_user["_id"])})
        .sort("timestamp", -1)
        .limit(min(limit, 100))
    )
    history = await cursor.to_list(length=None)
    return [
        {
            "success": h["success"],
            "timestamp": h["timestamp"],
            "ip_address": h.get("ip_address"),
            "user_agent": h.get("user_agent"),
        }
        for h in history
    ]
