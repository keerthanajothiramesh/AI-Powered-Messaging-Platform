from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from pydantic import BaseModel
from src.auth.dependencies import get_current_user
from src.common.database import get_pg_pool
from src.common.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def get_me(current_user=Depends(get_current_user)):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", current_user.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
    return _user_to_dict(user)


@router.get("/search")
async def search_users(
    q: str = Query(..., min_length=1),
    current_user=Depends(get_current_user),
):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT user_id, display_name, user_presence, avatar_url, last_seen
               FROM users
               WHERE (display_name ILIKE $1 OR email ILIKE $1) AND user_id != $2
               LIMIT 20""",
            f"%{q}%", current_user.user_id,
        )
    return [
        {
            "user_id": str(r["user_id"]),
            "display_name": r["display_name"],
            "user_presence": r["user_presence"],
            "avatar_url": r["avatar_url"],
            "last_seen": r["last_seen"].isoformat() if r["last_seen"] else None,
        }
        for r in rows
    ]


@router.get("/{user_id}")
async def get_user(user_id: str, current_user=Depends(get_current_user)):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT user_id, display_name, user_presence, last_seen, avatar_url, status, email FROM users WHERE user_id=$1",
            user_id,
        )
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": str(user["user_id"]),
        "display_name": user["display_name"],
        "email": user["email"],
        "user_presence": user["user_presence"],
        "last_seen": user["last_seen"].isoformat() if user["last_seen"] else None,
        "avatar_url": user["avatar_url"],
        "status": user["status"],
    }


@router.put("/me/status")
async def update_status(
    status: str = Query(..., pattern="^(online|offline|away)$"),
    current_user=Depends(get_current_user),
):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET user_presence=$1, last_seen=NOW() WHERE user_id=$2",
            status, current_user.user_id,
        )
    return {"status": status}


class ResolveEmailsRequest(BaseModel):
    emails: List[str]


@router.post("/resolve-by-email")
async def resolve_users_by_email(
    data: ResolveEmailsRequest,
    current_user=Depends(get_current_user),
):
    emails = [e.strip().lower() for e in data.emails if e.strip()][:99]
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id, display_name, email FROM users WHERE lower(email) = ANY($1::text[])",
            emails,
        )
    found = {r["email"].lower(): r for r in rows}
    return [
        {
            "email": email,
            "user_id": str(found[email]["user_id"]) if email in found else None,
            "display_name": found[email]["display_name"] if email in found else None,
            "found": email in found,
        }
        for email in emails
    ]


def _user_to_dict(user) -> dict:
    return {
        "user_id": str(user["user_id"]),
        "email": user["email"],
        "display_name": user["display_name"],
        "user_presence": user["user_presence"],
        "last_seen": user["last_seen"].isoformat() if user["last_seen"] else None,
        "status": user["status"],
        "registration_date": str(user["registration_date"]) if user["registration_date"] else None,
        "timezone": user["timezone"],
        "language_preference": user["language_preference"],
        "avatar_url": user["avatar_url"],
    }
