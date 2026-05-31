import uuid
from fastapi import APIRouter, Depends, HTTPException
from typing import List

from src.auth.dependencies import get_current_user
from src.messaging.schemas import CreateGroupRequest, GroupResponse, AddMemberRequest
from src.common.database import get_pg_pool
from src.common.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/groups", tags=["groups"])


@router.post("", status_code=201)
async def create_group(data: CreateGroupRequest, current_user=Depends(get_current_user)):
    pool = get_pg_pool()
    group_id = str(uuid.uuid4())
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """INSERT INTO groups (group_id, group_name, description, created_by)
                   VALUES ($1, $2, $3, $4)""",
                group_id, data.group_name, data.description, current_user.user_id,
            )
            await conn.execute(
                "INSERT INTO group_members (group_id, user_id, role) VALUES ($1, $2, 'admin')",
                group_id, current_user.user_id,
            )
            for member_id in data.member_ids:
                if member_id != current_user.user_id:
                    try:
                        await conn.execute(
                            "INSERT INTO group_members (group_id, user_id) VALUES ($1, $2)",
                            group_id, member_id,
                        )
                    except Exception:
                        pass

    logger.info("group_created", group_id=group_id, creator=current_user.user_id)

    from src.messaging.websocket_manager import get_connection_manager
    manager = get_connection_manager()
    group_event = {
        "type": "group_added",
        "data": {
            "group_id": group_id,
            "group_name": data.group_name,
            "description": data.description,
            "member_count": len(data.member_ids) + 1,
        },
    }
    manager.join_group(current_user.user_id, group_id)
    await manager.send_to_user(current_user.user_id, group_event)
    for member_id in data.member_ids:
        manager.join_group(member_id, group_id)
        await manager.send_to_user(member_id, group_event)

    return {"group_id": group_id, "group_name": data.group_name, "message": "Group created"}


@router.get("/me")
async def my_groups(current_user=Depends(get_current_user)):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT g.group_id, g.group_name, g.description, g.avatar_url,
                      g.created_by, g.created_at,
                      COUNT(gm2.user_id) as member_count
               FROM groups g
               JOIN group_members gm ON g.group_id = gm.group_id AND gm.user_id = $1
               JOIN group_members gm2 ON g.group_id = gm2.group_id
               GROUP BY g.group_id, g.group_name, g.description, g.avatar_url,
                        g.created_by, g.created_at""",
            current_user.user_id,
        )
    return [
        {
            "group_id": str(r["group_id"]),
            "group_name": r["group_name"],
            "description": r["description"],
            "avatar_url": r["avatar_url"],
            "created_by": str(r["created_by"]),
            "member_count": r["member_count"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


@router.get("/{group_id}")
async def get_group(group_id: str, current_user=Depends(get_current_user)):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        member = await conn.fetchrow(
            "SELECT 1 FROM group_members WHERE group_id=$1 AND user_id=$2",
            group_id, current_user.user_id,
        )
        if not member:
            raise HTTPException(status_code=403, detail="Not a group member")

        group = await conn.fetchrow("SELECT * FROM groups WHERE group_id=$1", group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        members = await conn.fetch(
            """SELECT u.user_id, u.display_name, u.user_presence, u.avatar_url, gm.role
               FROM group_members gm JOIN users u ON gm.user_id = u.user_id
               WHERE gm.group_id=$1""",
            group_id,
        )

    return {
        "group_id": str(group["group_id"]),
        "group_name": group["group_name"],
        "description": group["description"],
        "avatar_url": group["avatar_url"],
        "created_by": str(group["created_by"]),
        "created_at": group["created_at"].isoformat() if group["created_at"] else None,
        "members": [
            {
                "user_id": str(m["user_id"]),
                "display_name": m["display_name"],
                "user_presence": m["user_presence"],
                "avatar_url": m["avatar_url"],
                "role": m["role"],
            }
            for m in members
        ],
    }


@router.post("/{group_id}/members")
async def add_member(
    group_id: str, data: AddMemberRequest, current_user=Depends(get_current_user)
):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        admin = await conn.fetchrow(
            "SELECT role FROM group_members WHERE group_id=$1 AND user_id=$2",
            group_id, current_user.user_id,
        )
        if not admin or admin["role"] != "admin":
            raise HTTPException(status_code=403, detail="Only admins can add members")

        count = await conn.fetchval("SELECT COUNT(*) FROM group_members WHERE group_id=$1", group_id)
        if count >= 100:
            raise HTTPException(status_code=400, detail="Group at max capacity (100)")

        group = await conn.fetchrow("SELECT group_name, description FROM groups WHERE group_id=$1", group_id)
        new_count = await conn.fetchval("SELECT COUNT(*)+1 FROM group_members WHERE group_id=$1", group_id)
        try:
            await conn.execute(
                "INSERT INTO group_members (group_id, user_id) VALUES ($1, $2)",
                group_id, data.user_id,
            )
        except Exception:
            raise HTTPException(status_code=409, detail="User already in group")

    from src.messaging.websocket_manager import get_connection_manager
    manager = get_connection_manager()
    manager.join_group(data.user_id, group_id)
    await manager.send_to_user(data.user_id, {
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
async def remove_member(
    group_id: str, user_id: str, current_user=Depends(get_current_user)
):
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


@router.put("/{group_id}")
async def update_group(group_id: str, data: dict, current_user=Depends(get_current_user)):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        admin = await conn.fetchrow(
            "SELECT role FROM group_members WHERE group_id=$1 AND user_id=$2",
            group_id, current_user.user_id,
        )
        if not admin or admin["role"] != "admin":
            raise HTTPException(status_code=403, detail="Only admins can edit the group")

        await conn.execute(
            "UPDATE groups SET group_name=$1, description=$2 WHERE group_id=$3",
            data.get("group_name", "").strip() or None,
            data.get("description", ""),
            group_id,
        )

    from src.messaging.websocket_manager import get_connection_manager
    manager = get_connection_manager()
    await manager.broadcast_to_group(group_id, {
        "type": "group_updated",
        "data": {"group_id": group_id, "group_name": data.get("group_name"), "description": data.get("description")},
    })
    return {"message": "Group updated"}


@router.delete("/{group_id}")
async def delete_group(group_id: str, current_user=Depends(get_current_user)):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        admin = await conn.fetchrow(
            "SELECT role FROM group_members WHERE group_id=$1 AND user_id=$2",
            group_id, current_user.user_id,
        )
        if not admin or admin["role"] != "admin":
            raise HTTPException(status_code=403, detail="Only admins can delete the group")

        member_ids = await conn.fetch(
            "SELECT user_id FROM group_members WHERE group_id=$1", group_id
        )
        async with conn.transaction():
            await conn.execute("DELETE FROM group_members WHERE group_id=$1", group_id)
            await conn.execute("DELETE FROM groups WHERE group_id=$1", group_id)

    from src.messaging.websocket_manager import get_connection_manager
    manager = get_connection_manager()
    for row in member_ids:
        await manager.send_to_user(str(row["user_id"]), {
            "type": "group_removed",
            "data": {"group_id": group_id},
        })
    logger.info("group_deleted", group_id=group_id, by=current_user.user_id)
    return {"message": "Group deleted"}


@router.put("/{group_id}/members/{user_id}/role")
async def set_member_role(
    group_id: str, user_id: str, data: dict, current_user=Depends(get_current_user)
):
    role = data.get("role", "member")
    if role not in ("admin", "member"):
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'member'")

    pool = get_pg_pool()
    async with pool.acquire() as conn:
        admin = await conn.fetchrow(
            "SELECT role FROM group_members WHERE group_id=$1 AND user_id=$2",
            group_id, current_user.user_id,
        )
        if not admin or admin["role"] != "admin":
            raise HTTPException(status_code=403, detail="Only admins can change roles")

        await conn.execute(
            "UPDATE group_members SET role=$1 WHERE group_id=$2 AND user_id=$3",
            role, group_id, user_id,
        )
    return {"message": f"Role set to {role}"}
