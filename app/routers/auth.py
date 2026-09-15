from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.database import sessions_collection, users_collection
from app.schemas import LoginRequest, TokenResponse, UserOut
from app.security import create_access_token, new_session_id, verify_password
from app.security import decode_access_token

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticación"])
bearer_scheme = HTTPBearer(auto_error=False)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    user = await users_collection.find_one({"email": payload.email.lower()})
    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email o contraseña incorrectos")

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
