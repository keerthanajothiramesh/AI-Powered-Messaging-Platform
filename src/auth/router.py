import uuid
from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone
from typing import Optional

from src.auth.schemas import UserRegisterRequest, UserLoginRequest, TokenResponse, UserResponse
from src.auth.service import hash_password, verify_password, create_access_token
from src.auth.dependencies import get_current_user
from src.common.database import get_pg_pool
from src.common.exceptions import ConflictError
from src.common.logger import get_logger
from src.config import settings

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(data: UserRegisterRequest):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT user_id FROM users WHERE email=$1", data.email)
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")

        user_id = str(uuid.uuid4())
        password_hash = hash_password(data.password)

        await conn.execute(
            """INSERT INTO users
               (user_id, email, display_name, password_hash, language_preference, timezone, user_presence)
               VALUES ($1, $2, $3, $4, $5, $6, 'online')""",
            user_id, data.email, data.display_name, password_hash,
            data.language_preference, data.timezone,
        )
        logger.info("user_registered", user_id=user_id, email=data.email)

    token = create_access_token(user_id, data.email)
    return TokenResponse(
        access_token=token,
        user_id=user_id,
        display_name=data.display_name,
        email=data.email,
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLoginRequest):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT user_id, email, display_name, password_hash, status FROM users WHERE email=$1",
            data.email,
        )
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if user["status"] == "banned":
            raise HTTPException(status_code=403, detail="Account suspended")
        if not verify_password(data.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        await conn.execute(
            "UPDATE users SET user_presence='online', last_seen=NOW() WHERE user_id=$1",
            user["user_id"],
        )
        logger.info("user_logged_in", user_id=str(user["user_id"]))

    token = create_access_token(str(user["user_id"]), user["email"])
    return TokenResponse(
        access_token=token,
        user_id=str(user["user_id"]),
        display_name=user["display_name"],
        email=user["email"],
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user=Depends(get_current_user)):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE user_id=$1", current_user.user_id
        )
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        user_id=str(user["user_id"]),
        email=user["email"],
        display_name=user["display_name"],
        user_presence=user["user_presence"],
        last_seen=user["last_seen"],
        status=user["status"],
        registration_date=str(user["registration_date"]) if user["registration_date"] else None,
        timezone=user["timezone"],
        language_preference=user["language_preference"],
        avatar_url=user["avatar_url"],
    )


@router.post("/google", response_model=TokenResponse)
async def google_auth(credential: str = Body(..., embed=True)):
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=501, detail="Google OAuth not configured")
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
        idinfo = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=10,
        )
    except Exception as e:
        logger.warning("google_token_invalid", error=str(e))
        raise HTTPException(status_code=401, detail="Invalid Google token")

    email: str = idinfo.get("email", "")
    display_name: str = idinfo.get("name") or email.split("@")[0]
    avatar_url: Optional[str] = idinfo.get("picture")

    if not email:
        raise HTTPException(status_code=400, detail="Google account has no email")

    pool = get_pg_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT user_id, display_name, email FROM users WHERE email=$1", email
        )
        if existing:
            user_id = str(existing["user_id"])
            name = existing["display_name"]
            await conn.execute(
                "UPDATE users SET user_presence='online', last_seen=NOW(), avatar_url=COALESCE(avatar_url,$1) WHERE user_id=$2",
                avatar_url, user_id,
            )
        else:
            user_id = str(uuid.uuid4())
            name = display_name
            await conn.execute(
                """INSERT INTO users
                   (user_id, email, display_name, password_hash, language_preference, timezone, user_presence, avatar_url)
                   VALUES ($1, $2, $3, $4, 'en', 'Asia/Kolkata', 'online', $5)""",
                user_id, email, display_name, f"google_oauth_{user_id}", avatar_url,
            )
            logger.info("google_user_created", user_id=user_id, email=email)

    token = create_access_token(user_id, email)
    return TokenResponse(
        access_token=token,
        user_id=user_id,
        display_name=name,
        email=email,
    )


@router.post("/logout")
async def logout(current_user=Depends(get_current_user)):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET user_presence='offline', last_seen=NOW() WHERE user_id=$1",
            current_user.user_id,
        )
    logger.info("user_logged_out", user_id=current_user.user_id)
    return {"message": "Logged out successfully"}
