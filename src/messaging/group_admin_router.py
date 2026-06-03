"""Group admin endpoints — add/remove members, change roles, update group info, and delete groups."""
from fastapi import APIRouter, Depends, HTTPException

from src.auth.dependencies import get_current_user
from src.common.database import get_pg_pool
from src.common.logger import get_logger
from src.messaging.websocket_manager import get_connection_manager

logger = get_logger(__name__)
router = APIRouter(prefix="/groups", tags=["groups"])


async def _require_admin(pool, group_id: str, user_id: str):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT role FROM group_members WHERE group_id=$1 AND user_id=$2",
            group_id, user_id,
        )
    if not row or row["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can perform this action")
    return row


@router.post("/{group_id}/members")
async def add_member(group_id: str, data: dict, current_user=Depends(get_current_user)):
    pool = get_pg_pool()
    await _require_admin(pool, group_id, current_user.user_id)
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM group_members WHERE group_id=$1", group_id)
        if count >= 100:
            raise HTTPException(status_code=400, detail="Group at max capacity (100)")
        group = await conn.fetchrow("SELECT group_name, description FROM groups WHERE group_id=$1", group_id)
        new_count = count + 1
        try:
            await conn.execute(
                "INSERT INTO group_members (group_id, user_id) VALUES ($1, $2)",
                group_id, data["user_id"],
            )
        except Exception:
            raise HTTPException(status_code=409, detail="User already in group")

    manager = get_connection_manager()
    manager.join_group(data["user_id"], group_id)
    await manager.send_to_user(data["user_id"], {
        "type": "group_added",
        "data": {
            "group_id": group_id,
            "group_name": group["group_name"] if group else "",
            "description": group["description"] if group else "",
            "member_count": new_count,
        },
    })
    return {"message": "Member added"}


@router.delete("/{group_id}/members/{user_id}")
async def remove_member(group_id: str, user_id: str, current_user=Depends(get_current_user)):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        admin = await conn.fetchrow(
            "SELECT role FROM group_members WHERE group_id=$1 AND user_id=$2",
            group_id, current_user.user_id,
        )
        if not admin or (admin["role"] != "admin" and current_user.user_id != user_id):
            raise HTTPException(status_code=403, detail="Not authorized")
        await conn.execute(
            "DELETE FROM group_members WHERE group_id=$1 AND user_id=$2", group_id, user_id
        )
    return {"message": "Member removed"}


@router.put("/{group_id}/members/{user_id}/role")
async def set_member_role(group_id: str, user_id: str, data: dict, current_user=Depends(get_current_user)):
    role = data.get("role", "member")
    if role not in ("admin", "member"):
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'member'")
    pool = get_pg_pool()
    await _require_admin(pool, group_id, current_user.user_id)
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE group_members SET role=$1 WHERE group_id=$2 AND user_id=$3",
            role, group_id, user_id,
        )
    return {"message": f"Role set to {role}"}


@router.put("/{group_id}")
async def update_group(group_id: str, data: dict, current_user=Depends(get_current_user)):
    pool = get_pg_pool()
    await _require_admin(pool, group_id, current_user.user_id)
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE groups SET group_name=$1, description=$2 WHERE group_id=$3",
            data.get("group_name", "").strip() or None, data.get("description", ""), group_id,
        )
    manager = get_connection_manager()
    await manager.broadcast_to_group(group_id, {
        "type": "group_updated",
        "data": {"group_id": group_id, "group_name": data.get("group_name"),
                 "description": data.get("description")},
    })
    return {"message": "Group updated"}


@router.delete("/{group_id}")
async def delete_group(group_id: str, current_user=Depends(get_current_user)):
    pool = get_pg_pool()
    await _require_admin(pool, group_id, current_user.user_id)
    async with pool.acquire() as conn:
        member_ids = await conn.fetch("SELECT user_id FROM group_members WHERE group_id=$1", group_id)
        async with conn.transaction():
            await conn.execute("DELETE FROM group_members WHERE group_id=$1", group_id)
            await conn.execute("DELETE FROM groups WHERE group_id=$1", group_id)

    manager = get_connection_manager()
    for row in member_ids:
        await manager.send_to_user(str(row["user_id"]), {"type": "group_removed", "data": {"group_id": group_id}})
    logger.info("group_deleted", group_id=group_id, by=current_user.user_id)
    return {"message": "Group deleted"}
