"""Pydantic schemas for messaging — send/edit requests, message and group response models."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class MediaType(str, Enum):
    text = "text"
    image = "image"
    voice = "voice"
    video = "video"
    none = "none"


class DeliveryStatus(str, Enum):
    sent = "sent"
    delivered = "delivered"
    failed = "failed"
    queued = "queued"


class ReadStatus(str, Enum):
    read = "read"
    unread = "unread"


class SendDirectMessageRequest(BaseModel):
    receiver_id: str = Field(..., description="Recipient user ID")
    content: str = Field(..., min_length=1, max_length=10000, description="Message content")
    media_type: MediaType = Field(default=MediaType.text)
    media_url: Optional[str] = Field(None, description="URL for media attachment")


class SendGroupMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000, description="Message content")
    media_type: MediaType = Field(default=MediaType.text)
    media_url: Optional[str] = Field(None)


class MessageResponse(BaseModel):
    message_id: str
    sender_id: str
    receiver_id: Optional[str]
    group_id: Optional[str]
    content: str
    media_type: str
    media_url: Optional[str]
    delivery_status: str
    read_status: str
    reactions: Dict[str, List[str]]
    read_by: List[str]
    language: str
    timestamp: datetime
    conversation_summary: Optional[str]


class CreateGroupRequest(BaseModel):
    group_name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    member_ids: List[str] = Field(default_factory=list)


class GroupResponse(BaseModel):
    group_id: str
    group_name: str
    description: Optional[str]
    avatar_url: Optional[str]
    created_by: str
    member_count: int
    created_at: datetime


class AddMemberRequest(BaseModel):
    user_id: str


class EditMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)


class PresenceUpdate(BaseModel):
    status: str = Field(..., pattern="^(online|offline|away)$")
