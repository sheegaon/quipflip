"""Meme Mint image-related Pydantic schemas."""
from pydantic import BaseModel
from datetime import datetime
from typing import Literal
from uuid import UUID
from backend.schemas.base import BaseSchema


class ImageSummary(BaseSchema):
    """Image summary for display."""
    image_id: UUID
    source_url: str
    thumbnail_url: str | None
    attribution_text: str | None
    tags: list[str] | None
    status: Literal["active", "disabled"]
    created_at: datetime


class ImageDetails(BaseSchema):
    """Detailed image information with statistics."""
    image_id: UUID
    source_url: str
    thumbnail_url: str | None
    attribution_text: str | None
    tags: list[str] | None
    status: Literal["active", "disabled"]
    created_at: datetime
    created_by_username: str | None
    # Statistics
    total_captions: int
    active_captions: int
    total_votes: int


class ImageListItem(BaseSchema):
    """Image item for list views."""
    image_id: UUID
    source_url: str
    thumbnail_url: str | None
    attribution_text: str | None
    tags: list[str] | None
    caption_count: int
    created_at: datetime


class ImageListResponse(BaseModel):
    """List of images with pagination."""
    images: list[ImageListItem]
    total: int
    page: int
    page_size: int
    has_more: bool


class CreateImageRequest(BaseModel):
    """Create image request (admin only)."""
    source_url: str
    thumbnail_url: str | None = None
    attribution_text: str | None = None
    tags: list[str] | None = None


class CreateImageResponse(BaseSchema):
    """Create image response."""
    image_id: UUID
    source_url: str
    thumbnail_url: str | None
    attribution_text: str | None
    tags: list[str] | None
    status: Literal["active"]
    created_at: datetime
