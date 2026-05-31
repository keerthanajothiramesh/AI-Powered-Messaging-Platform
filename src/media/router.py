from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path
from typing import Optional

from src.auth.dependencies import get_current_user
from src.media.service import upload_file
from src.common.logger import get_logger
from src.config import settings

logger = get_logger(__name__)
router = APIRouter(prefix="/media", tags=["media"])

MAX_FILE_SIZE = 50 * 1024 * 1024
ALLOWED_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "video/mp4", "video/webm",
    "audio/mpeg", "audio/wav", "audio/ogg", "audio/webm",
}


@router.post("/upload")
async def upload_media(
    file: UploadFile = File(...),
    group_id: Optional[str] = Form(None),
    description: str = Form(""),
    current_user=Depends(get_current_user),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"File type {file.content_type} not allowed")

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")

    record = await upload_file(
        file_data=data,
        filename=file.filename,
        content_type=file.content_type,
        uploader_id=current_user.user_id,
        group_id=group_id,
        description=description,
    )
    return {"media_id": record["media_id"], "url": record["url"], "media_type": record["media_type"]}


@router.get("/{media_id}")
async def get_media(media_id: str, current_user=Depends(get_current_user)):
    from src.common.database import get_mongo_db
    db = get_mongo_db()
    record = await db.media.find_one({"media_id": media_id})
    if not record:
        raise HTTPException(status_code=404, detail="Media not found")
    record.pop("_id", None)
    return record


@router.get("/file/{filename}")
async def serve_local_file(filename: str):
    path = Path(settings.LOCAL_UPLOADS_PATH) / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(path))
