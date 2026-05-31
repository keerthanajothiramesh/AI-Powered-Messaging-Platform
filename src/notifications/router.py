from fastapi import APIRouter, Depends
from src.auth.dependencies import get_current_user
from src.notifications.service import get_user_notifications, mark_notifications_read
from src.common.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/me")
async def my_notifications(current_user=Depends(get_current_user)):
    notifs = await get_user_notifications(current_user.user_id)
    return {"count": len(notifs), "notifications": notifs}


@router.put("/me/read")
async def mark_all_read(current_user=Depends(get_current_user)):
    count = await mark_notifications_read(current_user.user_id)
    return {"marked_read": count}
